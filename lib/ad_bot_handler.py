from asyncio import CancelledError
from contextlib import suppress
from enum import Enum
from re import DOTALL, IGNORECASE, RegexFlag, match
from sqlite3 import OperationalError
from traceback import print_exc
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Final,
    Generator,
    Generic,
    Iterable,
    Optional,
    Self,
    TypeVar,
    Union,
)

from pyrogram.client import Client
from pyrogram.enums.chat_action import ChatAction
from pyrogram.errors.rpc_error import RPCError
from pyrogram.handlers.handler import Handler
from pyrogram.raw.functions.messages.read_history import ReadHistory
from pyrogram.types.messages_and_media.message import Message
from sqlalchemy.sql.expression import exists, select, text
from sqlalchemy.sql.sqltypes import String

from .models.clients.user_model import UserModel, UserRole
from .models.misc.input_model import InputModel
from .utils.anyfunction import anycorofunction
from .utils.query import Query

if TYPE_CHECKING:
    from .ad_bot_client import AdBotClient

#
T = TypeVar('T')


class AdBotHandler(Generic[T], Handler):
    pattern: Final[Union[str, Iterable[str]]]
    chat_id: Final[Optional[int]]
    check_user: Final[Optional[UserRole]]
    calls_count: Final[Optional[int]]
    action: Final[Optional[ChatAction]]
    replace: Final[bool]
    private: Final[bool]
    is_query: Final[Optional[bool]]
    flags: Final[RegexFlag]

    def __init__(
        self: Self,
        callback: Callable[..., T],
        /,
        pattern: Union[str, Iterable[str]] = str(),
        chat_id: Optional[int] = None,
        check_user: Optional[UserRole] = None,
        calls_count: Optional[int] = 1,
        action: Optional[ChatAction] = ChatAction.TYPING,
        *,
        replace: bool = False,
        private: bool = True,
        is_query: Optional[bool] = None,
        flags: RegexFlag = IGNORECASE | DOTALL,
    ) -> None:
        def unpack(iterable: Iterable[Any], /) -> Generator[str, None, None]:
            for _ in iterable:
                if isinstance(_, str):
                    yield _.value if isinstance(_, Enum) else _
                elif isinstance(_, Iterable):
                    yield from unpack(_)

        def format_str(string: str, /) -> str:
            return '^' + f'{string}'.removeprefix('^').removesuffix('$') + '$'

        super().__init__(callback)
        if not isinstance(pattern, str) and isinstance(pattern, Iterable):
            pattern = '|'.join(map(format_str, unpack(pattern)))
        elif isinstance(pattern, Enum):
            pattern = format_str(pattern.value)
        elif pattern:
            pattern = format_str(pattern)
        else:
            pattern = None

        self.pattern = pattern
        self.chat_id = chat_id
        self.check_user = check_user
        self.calls_count = calls_count
        self.action = action
        self.replace = replace
        self.private = private
        self.is_query = is_query
        self.flags = flags

    @property
    def callback_name(self: Self, /) -> str:
        return ':'.join((self.callback.__module__, self.callback.__qualname__))

    async def check(
        self: Self,
        client: Client,
        /,
        chat_id: int,
        data: str,
        query_id: Optional[int] = None,
        *,
        is_private: bool,
    ) -> bool:
        if self.is_query is True and query_id is None:
            return False
        elif self.is_query is False and query_id is not None:
            return False

        if self.private and not is_private:
            return False
        if self.chat_id is not None and chat_id != self.chat_id:
            return False
        if self.pattern and not match(self.pattern, data, self.flags):
            return False

        if self.calls_count and not self.replace:
            chats = client.__class__.Registry.get(
                client.storage.phone_number, {}
            )
            tasks = chats.get(chat_id, {}).get(self.callback_name, [])
            if len(tasks) >= self.calls_count:
                return False

        return True

    async def __call__(
        self: Self,
        client: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> T:
        if isinstance(chat_id, InputModel):
            input, chat_id = chat_id, chat_id.chat_id
        if self.calls_count and self.replace:
            chats = client.__class__.Registry.get(
                client.storage.phone_number, {}
            )
            tasks = chats.get(chat_id, {}).get(self.callback_name, [])
            if len(tasks) - 1 >= self.calls_count:
                with suppress(RuntimeError):
                    (task := tasks.pop(0)).cancel()
                with suppress(OperationalError, RuntimeError, KeyError):
                    r = client.storage.Session.registry
                    r.registry[r.scopefunc()] = r.registry.pop(task)

        if self.check_user is not None and (
            await client.storage.Session.scalar(
                select(
                    ~exists(text('NULL'))
                    .where(UserModel.id == chat_id)
                    .where(
                        UserModel.is_subscribed
                        if self.check_user
                        not in {UserRole.SUPPORT, UserRole.ADMIN}
                        else UserModel.role.cast(String).in_(
                            list(UserRole.__members__)[
                                list(UserRole.__members__).index(
                                    self.check_user.value
                                ) :
                            ]
                        )
                    )
                )
            )
        ):
            input = await client.storage.Session.get(InputModel, chat_id)
            if input is not None:
                await client.input_message(
                    *(input, message_id),
                    data=Query(client.INPUT.CANCEL),
                    query_id=query_id,
                )
            await client.answer_edit_send(
                *(query_id, chat_id),
                text='Для того чтобы пользоваться функционалом '
                'оформите подписку.'
                if self.check_user not in {UserRole.SUPPORT, UserRole.ADMIN}
                else 'У вас недостаточно прав для выполнения этой функции.',
            )
            return await client.storage.Session.remove()

        cancel: bool = False
        chat_peer: Optional[Any] = None
        try:
            if self.action is not None:
                chat_peer = await client.resolve_peer(chat_id)
                with suppress(RPCError):
                    cancel = await client.send_chat_action(
                        chat_peer, self.action
                    )
            return await anycorofunction(
                self.callback.__func__
                if hasattr(self.callback, '__self__')
                else self.callback,
                client,
                chat_id=chat_id,
                message_id=message_id,
                data=data,
                query_id=query_id,
            )
        except CancelledError:
            cancel = False
            print_exc()
        except BaseException:
            print_exc()
        finally:
            if query_id is not None:
                with suppress(RPCError):
                    await client.answer_callback_query(query_id)
            if message_id is not None and client.storage.is_nested:
                with suppress(RPCError):
                    if chat_peer is None:
                        chat_peer = await client.resolve_peer(chat_id)
                    await client.invoke(
                        ReadHistory(
                            peer=chat_peer,
                            max_id=message_id
                            if isinstance(message_id, int)
                            else message_id.id,
                        ),
                        no_updates=True,
                    )
            if cancel:
                with suppress(RPCError):
                    await client.send_chat_action(
                        chat_peer or chat_id, ChatAction.CANCEL
                    )
            await client.storage.Session.remove()
