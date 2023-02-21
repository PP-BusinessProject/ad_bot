"""Utilities for working with Pyrogram."""

from asyncio import Lock
from contextlib import suppress
from functools import wraps
from logging import error
from re import IGNORECASE, RegexFlag, match
from traceback import extract_stack
from typing import (
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Concatenate,
    Coroutine,
    Final,
    Generator,
    Generic,
    Iterable,
    Optional,
    ParamSpec,
    Self,
    Type,
    TypeVar,
    Union,
)

from pyrogram.client import Client
from pyrogram.errors import RPCError
from pyrogram.filters import Filter, create
from pyrogram.raw.types.input_peer_channel import InputPeerChannel
from pyrogram.raw.types.input_peer_channel_from_message import (
    InputPeerChannelFromMessage,
)
from pyrogram.raw.types.input_peer_chat import InputPeerChat
from pyrogram.raw.types.input_peer_empty import InputPeerEmpty
from pyrogram.raw.types.input_peer_self import InputPeerSelf
from pyrogram.raw.types.input_peer_user import InputPeerUser
from pyrogram.raw.types.input_peer_user_from_message import (
    InputPeerUserFromMessage,
)
from pyrogram.types import CallbackQuery, Message, Update
from pyrogram.utils import get_channel_id

from ..models.sessions.peer_model import PeerModel
from .query import Query


def get_input_peer(
    peer: PeerModel,
    /,
) -> Union[InputPeerUser, InputPeerChat, InputPeerChannel]:
    """Return the input peer for the specified `peer_id` and `peer_type`."""
    if peer.type in {'user', 'bot'}:
        return InputPeerUser(user_id=peer.id, access_hash=peer.access_hash)
    elif peer.type == 'group':
        return InputPeerChat(chat_id=-peer.id)
    elif peer.type in {'channel', 'supergroup'}:
        return InputPeerChannel(
            channel_id=get_channel_id(peer.id),
            access_hash=peer.access_hash,
        )
    else:
        raise ValueError(f'Invalid peer type: {peer.type}')


def get_input_peer_id(
    peer: Union[
        InputPeerChannel,
        InputPeerChannelFromMessage,
        InputPeerChat,
        InputPeerEmpty,
        InputPeerSelf,
        InputPeerUser,
        InputPeerUserFromMessage,
    ]
) -> int:
    """Return the id of the :class:`pyrogram.raw.base.InputPeer`."""
    if isinstance(peer, (InputPeerChannel, InputPeerChannelFromMessage)):
        return get_channel_id(peer.channel_id)
    elif isinstance(peer, InputPeerChat):
        return -peer.chat_id
    elif isinstance(peer, (InputPeerUser, InputPeerUserFromMessage)):
        return peer.user_id
    else:
        raise ValueError(f'Unknown peer: {peer}.')


def get_hash(ids: Iterable[int], /) -> int:
    """Return the hash for Telegram."""
    hash: int = 0
    for id in ids:
        hash = (((hash ^ (id >> 21)) ^ (id << 35)) ^ (id >> 4)) + id
    return hash


"""The module that simplifies usage of the queries and provides decorators."""


_P = ParamSpec('_P')
_T = TypeVar('_T')
_Client = TypeVar('_Client', bound=Client, covariant=True)
_Update = TypeVar('_Update', bound=Update, covariant=True)


def regex_query(
    pattern: Union[str, Iterable[str]] = str(),
    /,
    chat_id: Optional[int] = None,
    *,
    private: bool = True,
    encoding: str = 'utf-8',
    flags: RegexFlag = IGNORECASE,
) -> Filter:
    """Match a ``CallbackQuery`` to contain this ``Query`` command."""

    def check(flt: Filter, client: Client, update: Update, /) -> bool:
        nonlocal pattern, chat_id, private, encoding, flags
        if not isinstance(update, CallbackQuery):
            return False
        elif chat_id is not None and update.message.chat.id != chat_id:
            return False
        elif private and update.message.chat.id != update.from_user.id:
            return False
        elif not isinstance(update.data, Query):
            update.data = Query.parse(update.data, encoding=encoding)

        if not isinstance(pattern, str) and isinstance(pattern, Iterable):

            def unpack(seq: Iterable[Any], /) -> Generator[str, None, None]:
                for _ in seq:
                    if isinstance(_, str):
                        yield _
                    elif isinstance(_, Iterable):
                        yield from unpack(_)

            pattern = '|'.join(f'{_}$' for _ in unpack(pattern))
        return bool(pattern and match(pattern, update.data.command, flags))

    return create(check)


def update_only(
    *whitelist: Type[_Update],
) -> Callable[
    [Callable[Concatenate[_Client, Update, _P], Awaitable[_T]]],
    Callable[Concatenate[_Client, _Update, _P], Awaitable[_T]],
]:
    """
    Decorate for checking `update's` type.

    Args:
        whitelist_types (``tuple[Type[Update], ...]``, *optional*):
            The update types that can be passed to the decorated `handler`.

    Returns:
        The decorated handler with checked `update's` type.
    """

    def handler(
        handler: Callable[Concatenate[_Client, Update, _P], Awaitable[_T]],
        /,
    ) -> Callable[Concatenate[_Client, _Update, _P], Awaitable[_T]]:
        @wraps(handler)
        async def wrapper(
            client: _Client,
            update: _Update,
            /,
            *args: _P.args,
            **kwargs: _P.kwargs,
        ) -> _T:
            if not any(isinstance(update, type) for type in whitelist):
                types = tuple(f'`{type.__name__}`' for type in whitelist)
                raise ValueError(
                    'This function does not work with {type}. It works only '
                    'with {types}.'.format(
                        type=f'`{update.__class__.__name__}`',
                        types=' and '.join(
                            _ for _ in (', '.join(types[:-1]), types[-1]) if _
                        ),
                    )
                )

            return await handler(client, update, *args, **kwargs)

        return wrapper

    return handler


def typing(
    action: Optional[str] = 'typing',
    /,
    stack_check_limit: int = 8,
) -> Callable[
    [Callable[Concatenate[_Client, _Update, _P], Awaitable[_T]]],
    Callable[Concatenate[_Client, _Update, _P], Awaitable[_T]],
]:
    """
    Decorate the function for showing activity on the client.

    Args:
        action (``Optional[str]``, *optional*):
            The action to send instead of `typing`.

        stack_check_limit (``int``, *optional*):
            The limit of stack items to check for instances of this decorator.

    Returns:
        The decorator function for showing activity on the client.
    """

    def handler(
        handler: Callable[Concatenate[_Client, _Update, _P], Awaitable[_T]],
        /,
    ) -> Callable[Concatenate[_Client, _Update, _P], Awaitable[_T]]:
        async def typing_wrapper(
            client: _Client,
            update: _Update,
            /,
            *args: _P.args,
            **kwargs: _P.kwargs,
        ) -> _T:
            args = client, update, *args
            message = getattr(update, 'message', update)
            from_user = getattr(message, 'from_user', None)
            if not action or not getattr(from_user, 'is_self', True):
                return await handler(*args, **kwargs)

            frames_count: int = 0
            for frame in extract_stack(limit=stack_check_limit):
                frames_count += int('typing_wrapper' in frame)
                if frames_count >= 2:
                    return await handler(*args, **kwargs)

            cancel: bool = False
            try:
                cancel = await client.send_chat_action(message.chat.id, action)
            except ValueError as e:
                raise
            except BaseException as e:
                error(e)

            try:
                return await handler(*args, **kwargs)
            finally:
                if cancel:
                    await client.send_chat_action(message.chat.id, 'cancel')

        return typing_wrapper

    return handler


def limit_calls(
    count: Optional[int] = 1,
    /,
    name: Optional[str] = None,
    *,
    replace: bool = False,
) -> Callable[
    [Callable[Concatenate[_Client, _Update, _P], Coroutine[Any, Any, _T]]],
    Callable[Concatenate[_Client, _Update, _P], Coroutine[Any, Any, _T]],
]:
    """
    Decorate for being called at most `count` times simultaneously.

    Args:
        count (``Optional[int]``, *optional*):
            The top most count of simultaneous calls of the `handler`.

        name (``Optional[str]``, *optional*):
            The custom name of the `handler` if any.

        replace (``bool``, *optional*):
            If the coroutines should be replaced and closed.

    Returns:
        The decorated handler with limited simultaneous calls.
    """

    def handler(
        handler: Callable[
            Concatenate[_Client, _Update, _P],
            Coroutine[Any, Any, _T],
        ],
        /,
    ) -> Callable[Concatenate[_Client, _Update, _P], Coroutine[Any, Any, _T]]:
        @wraps(handler)
        async def wrapper(
            client: _Client,
            update: _Update,
            /,
            *args: _P.args,
            **kwargs: _P.kwargs,
        ) -> _T:
            global UpdateFuncsDict
            if 'UpdateFuncsDict' not in globals():
                UpdateFuncsDict = dict[
                    str, dict[int, list[Coroutine[Any, Any, _T]]]
                ]()

            nonlocal name
            if not name:
                name = '.'.join((handler.__module__, handler.__name__))
            if name not in UpdateFuncsDict:
                UpdateFuncsDict[name] = {}

            message: Message = getattr(update, 'message', update)
            if message.chat.id not in UpdateFuncsDict[name]:
                UpdateFuncsDict[name][message.chat.id] = []
            if count and len(UpdateFuncsDict[name][message.chat.id]) >= count:
                if not replace:
                    time = 'time' if count == 1 else 'times'
                    raise OverflowError(
                        f'Function {name} is called more than {count} {time}!'
                    )
                with suppress(RuntimeError):
                    UpdateFuncsDict[name][message.chat.id].pop(0).close()

            coro = handler(client, update, *args, **kwargs)
            UpdateFuncsDict[name][message.chat.id].append(coro)
            try:
                return await coro
            finally:
                if message.chat.id is not None:
                    UpdateFuncsDict[name][message.chat.id].remove(coro)

        return wrapper

    return handler


def auto_answer(
    handler: Callable[Concatenate[_Client, _Update, _P], Awaitable[_T]],
    /,
) -> Callable[Concatenate[_Client, _Update, _P], Awaitable[_T]]:
    """Decorate for answering :class:`CallbackQuery` on `handler`."""

    @wraps(handler)
    async def wrapper(
        client: _Client,
        update: _Update,
        /,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _T:
        try:
            return await handler(client, update, *args, **kwargs)
        finally:
            if isinstance(update, CallbackQuery):
                with suppress(RPCError):
                    await update.answer()

    return wrapper


class auto_init(Generic[_Client]):
    """Automatically initialize and stop the :class:`Client` if needed."""

    _client: Final[_Client]
    _start: Final[bool]
    _stop: Final[Optional[bool]]
    _only_connect: Final[bool]
    _suppress: Final[bool]
    _is_initialized: Optional[bool] = None
    _locks: ClassVar[dict[Optional[str], Lock]] = {}

    def __init__(
        self,
        client: _Client,
        /,
        *,
        start: bool = True,
        stop: Optional[bool] = False,
        only_connect: bool = False,
        suppress: bool = False,
    ) -> None:
        """Initialize this class."""
        self._client, self._start, self._stop = client, start, stop
        self._only_connect, self._suppress = only_connect, suppress

    @property
    def client(self: Self, /) -> _Client:
        """Return the client that is being initialized."""
        return self._client

    @property
    def start(self: Self, /) -> bool:
        """If the `client` should be started if it has not been started yet."""
        return self._start

    @property
    def stop(self: Self, /) -> Optional[bool]:
        """If the `client` should be stopped on exit."""
        return self._stop

    @property
    def only_connect(self: Self, /) -> bool:
        """If the `client` should be only connected but not started."""
        return self._only_connect

    @property
    def suppress(self: Self, /) -> bool:
        """If the `client` start errors should be suppressed."""
        return self._suppress

    async def __aenter__(self: Self, /) -> _Client:
        if self._client.phone_number not in self._locks:
            self._locks[self._client.phone_number] = Lock()
        async with self._locks[self._client.phone_number]:
            if self._stop is None:
                self._is_initialized = not self._client.is_initialized
            if self._start and not self._client.is_initialized:
                try:
                    if not self._only_connect:
                        await self._client.start()
                    elif not self._client.is_connected:
                        await self._client.connect()
                except BaseException:
                    if not self._suppress:
                        raise
            return self._client

    async def __aexit__(self: Self, /, *_: Any) -> None:
        if self._client.phone_number not in self._locks:
            self._locks[self._client.phone_number] = Lock()
        async with self._locks[self._client.phone_number]:
            if self._stop or self._stop is None and self._is_initialized:
                if self._client.is_initialized:
                    await self._client.stop()
                elif self._client.is_connected:
                    await self._client.disconnect()
