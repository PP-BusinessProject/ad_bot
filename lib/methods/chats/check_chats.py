"""The module with the :meth:`AdBotClient.check_chats`."""

from contextlib import suppress
from time import monotonic
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Final,
    Generator,
    Iterable,
    Optional,
    Union,
    overload,
)

from pyrogram.errors.exceptions.bad_request_400 import (
    BadRequest,
    PeerIdInvalid,
    UserAlreadyParticipant,
)
from pyrogram.errors.exceptions.flood_420 import FloodWait
from pyrogram.errors.rpc_error import RPCError
from pyrogram.raw.types.input_peer_channel import InputPeerChannel
from pyrogram.raw.types.input_peer_chat import InputPeerChat
from pyrogram.raw.types.input_peer_user import InputPeerUser
from pyrogram.raw.types.rpc_error import RpcError
from pyrogram.types.user_and_chats.chat import Chat
from typing_extensions import Self

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient

from ...typings.check_chats import CheckChat
from ...utils.pyrogram import get_input_peer_id


class CheckChatsFloodWait(FloodWait):
    checked_chats: Final[dict[CheckChat, Chat]]

    def __init__(
        self: Self,
        checked_chats: dict[CheckChat, Chat],
        /,
        x: Union[int, str, RpcError] = None,
    ):
        super().__init__(x)
        self.checked_chats = checked_chats


class CheckChats(object):
    @overload
    async def check_chats(
        self: Self,
        chats: CheckChat,
        /,
    ) -> Optional[Chat]:
        pass

    @overload
    async def check_chats(
        self: Self,
        chats: Iterable[CheckChat],
        /,
    ) -> list[Optional[Chat]]:
        pass

    async def check_chats(
        self: 'AdBotClient',
        chats: Union[CheckChat, Iterable[CheckChat]],
        /,
    ) -> Union[Optional[Chat], list[Optional[Chat]]]:
        """
        Check if each of the chats is accesible by this client.

        Args:
            chats (``Union[CheckChat, Iterable[CheckChat]]``):
                The links to one or many chats that are must be accessible by
                the client.
                    Can optionally be a tuples of the chat link and chat
                    invite links to try and join if the chat is not accessible.

        Returns:
            The lif of the one or many chats that should be accessible by
            the client.

        Raises:
            * ValueError if the chats iterable is empty.
        """

        def is_iter(_: Any, /) -> bool:
            return not isinstance(_, str) and isinstance(_, Iterable) and _

        if isinstance(chats, AsyncGenerator):
            chats: Iterable[CheckChat] = [_ async for _ in chats]
        if not (is_iterable := is_iter(chats) and any(map(is_iter, chats))):
            chats = (chats,)

        agen = self.iter_check_chats(chats, yield_on_flood=False)
        if not is_iterable:
            return await anext(aiter(agen), None)
        return [_ async for _ in agen]

    async def iter_check_chats(
        self: 'AdBotClient',
        chats: Union[CheckChat, Iterable[CheckChat]],
        /,
        *,
        yield_on_flood: Optional[bool] = None,
    ) -> AsyncGenerator[Optional[Chat], None]:
        """
        Check if each of the chats is accesible by this client.

        Args:
            chats (``Union[CheckChat, Iterable[CheckChat]]``):
                The links to one or many chats that are must be accessible by
                the client.
                    Can optionally be a tuples of the chat link and chat
                    invite links to try and join if the chat is not accessible.

            yield_on_flood (``Optional[bool]``, *optional*):
                If the `FloodWait` exception should be yielded.
                    If it's value is False, the FloodWait is raised.

        Returns:
            The asynchronous generator of the one or many chats that should be
            accessible by the client.

        Raises:
            * ValueError, if the chats iterable is empty.
            * CheckChatsFloodWait, if `yield_on_flood` is True and `FloodWait`
            exception occured. This exception contains all of the already
            checked chats.
        """

        def is_iter(_: Any, /) -> bool:
            return not isinstance(_, str) and isinstance(_, Iterable)

        if isinstance(chats, AsyncGenerator):
            chats: Iterable[CheckChat] = [_ async for _ in chats]
        elif isinstance(chats, Generator):
            chats: Iterable[CheckChat] = list(chats)

        if is_iter(chats) and not any(map(is_iter, chats)):
            if not chats:
                raise ValueError('There are no chats to check.')
        elif not (is_iter(chats) and any(map(is_iter, chats))):
            chats = (chats,)
        else:
            for index, chat in enumerate(chats):
                if not chat:
                    raise ValueError(f'The chat with index #{index} is empty.')

        chats: dict[Union[int, str, Chat], Iterable[CheckChat]] = {
            next(iter(chat)) if is_iter(chat) else chat: chat for chat in chats
        }

        async def join(chat: CheckChat, /) -> Optional[Chat]:
            async def join(invite_link: Union[int, str], /) -> Optional[Chat]:
                if not invite_link:
                    return None
                try:
                    if self.is_bot:
                        raise UserAlreadyParticipant
                    return await self.join_chat(invite_link)
                except UserAlreadyParticipant:
                    return await self.get_chat(invite_link)
                except FloodWait:
                    raise
                except RPCError as _:
                    return None

            if not is_iter(chat):
                return None
            elif len(chat) == 1:
                return await join(next(iter(chat)))

            chat_iter = iter(chat)
            next(chat_iter)
            for chat_invites in chat_iter:
                if not is_iter(chat_invites):
                    if (chat := await join(chat_invites)) is not None:
                        return chat
                else:
                    for chat_link in chat_invites:
                        if (chat := await join(chat_link)) is not None:
                            return chat
            return None

        peers: dict[CheckChat, Union[InputPeerChat, InputPeerChannel]] = {}
        for chat_link in chats:
            if not isinstance(chat_link, str) or (
                not self.INVITE_LINK_RE.match(chat_link)
            ):
                with suppress(PeerIdInvalid):
                    peers[chat_link] = await self.resolve_peer(chat_link)

        dialog_chats: dict[str, Chat] = {}
        if peers and self.is_bot:
            for chat_link, chat in chats.items():
                if (peer := peers.get(chat_link)) is not None:
                    dialog_chats[chat_link] = await self.get_chat(peer)
        elif peers:
            for dialog in await self.get_peer_dialogs(peers.values()):
                if dialog.top_message is not None:
                    for chat_link, chat in chats.items():
                        if (peer := peers.get(chat_link)) is not None:
                            chat_id = get_input_peer_id(peer)
                            if chat_id == dialog.chat.id:
                                dialog_chats[chat_link] = dialog.chat
                                break

        flood: int = 0
        for chat_link, chat in chats.items():
            if chat_link in dialog_chats:
                yield dialog_chats[chat_link]
            elif monotonic() < flood or isinstance(
                peers.get(chat_link), InputPeerUser
            ):
                yield None
            else:
                while True:
                    try:
                        yield await join(chat)
                    except FloodWait as e:
                        if yield_on_flood:
                            _c = {chats[_]: c for _, c in dialog_chats.items()}
                            yield CheckChatsFloodWait(_c, e.value)
                        elif yield_on_flood is None:
                            flood = monotonic() + e.value
                            yield None
                            break
                        else:
                            raise
                    else:
                        break
