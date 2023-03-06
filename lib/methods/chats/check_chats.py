"""The module with the :meth:`AdBotClient.check_chats`."""

from contextlib import suppress
from time import monotonic
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Dict,
    Final,
    Generator,
    Iterable,
    List,
    Optional,
    Self,
    Union,
    overload,
)

from pyrogram.errors.exceptions.bad_request_400 import (
    PeerIdInvalid,
    UserAlreadyParticipant,
)
from pyrogram.errors.exceptions.flood_420 import FloodWait
from pyrogram.errors.exceptions.not_acceptable_406 import NotAcceptable
from pyrogram.errors.rpc_error import RPCError
from pyrogram.raw.types.input_peer_channel import InputPeerChannel
from pyrogram.raw.types.input_peer_chat import InputPeerChat
from pyrogram.raw.types.input_peer_user import InputPeerUser
from pyrogram.raw.types.rpc_error import RpcError
from pyrogram.types.user_and_chats.chat import Chat

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
        value: Union[int, str, RpcError] = None,
    ):
        super().__init__(value)
        self.checked_chats = checked_chats


class CheckChats(object):
    @overload
    async def check_chats(
        self: Self,
        chats: CheckChat,
        /,
        *,
        fetch_peers: bool = True,
    ) -> Optional[Chat]:
        pass

    @overload
    async def check_chats(
        self: Self,
        chats: Iterable[CheckChat],
        /,
        *,
        fetch_peers: bool = True,
    ) -> list[Optional[Chat]]:
        pass

    async def check_chats(
        self: 'AdBotClient',
        chats: Union[CheckChat, Iterable[CheckChat]],
        /,
        *,
        fetch_peers: bool = True,
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

        agen = self.iter_check_chats(
            chats,
            fetch_peers=fetch_peers,
            yield_on_flood=False,
            yield_on_exception=False,
        )
        if not is_iterable:
            return await anext(aiter(agen), None)
        return [_ async for _ in agen]

    async def iter_check_chats(
        self: 'AdBotClient',
        chats: Union[CheckChat, Iterable[CheckChat]],
        /,
        *,
        fetch_peers: bool = True,
        yield_on_flood: Optional[bool] = None,
        yield_on_exception: Optional[bool] = None,
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

        if chats is None:
            raise ValueError('There are no chats to check.')
        elif isinstance(chats, AsyncGenerator):
            chats: Iterable[CheckChat] = [_ async for _ in chats]
        elif isinstance(chats, Generator):
            chats: Iterable[CheckChat] = list(chats)
        elif not (is_iter(chats) and any(map(is_iter, chats))):
            chats = (chats,)

        if not chats:
            raise ValueError('There are no chats to check.')
        for index, chat_links in enumerate(chats):
            if chat_links is None or is_iter(chat_links):
                if not chat_links:
                    raise ValueError(
                        f'There are no links at chat with index #{index}.'
                    )
            else:
                chats[index] = (chat_links,)

        async def join(invite_link: Union[int, str], /) -> Optional[Chat]:
            if not isinstance(invite_link, str) or not invite_link:
                return None
            try:
                try:
                    if self.is_bot:
                        raise RPCError
                    return await self.join_chat(invite_link)
                except UserAlreadyParticipant:
                    return await self.get_chat(invite_link)
            except FloodWait:
                raise

        peers: List[Union[None, InputPeerChat, InputPeerChannel]] = []
        for chat_links in chats:
            for chat_link in chat_links:
                if not (
                    isinstance(chat_link, str)
                    and self.INVITE_LINK_RE.match(chat_link)
                ):
                    with suppress(PeerIdInvalid):
                        peer = await self.resolve_peer(chat_link, fetch=False)
                        if peer is not None:
                            peers.append(peer)
                            break
            else:
                peers.append(None)

        dialog_chats: Dict[int, Optional[Chat]] = {}
        if self.is_bot:
            for chat_links, peer in zip(chats, peers):
                if peer is not None:
                    dialog_chats[
                        get_input_peer_id(peer)
                    ] = await self.get_chat(peer)
        else:
            with suppress(NotAcceptable):
                for dialog, peer in zip(
                    await self.get_peer_dialogs(
                        _peers := [_ for _ in peers if _ is not None],
                        fetch_peers=fetch_peers,
                    ),
                    _peers,
                ):
                    if dialog.top_message is not None:
                        dialog_chats[get_input_peer_id(peer)] = dialog.chat

        flood: int = 0
        for chat_links, peer in zip(chats, peers):
            success = False
            for chat_link in chat_links:
                if peer is not None and (
                    get_input_peer_id(peer) in dialog_chats
                ):
                    yield dialog_chats[get_input_peer_id(peer)]
                    break
                elif monotonic() < flood or isinstance(peer, InputPeerUser):
                    yield None
                    break
                elif not isinstance(chat_link, str) or not chat_link:
                    continue

                while True:
                    try:
                        yield await join(chat_link)
                        success = True
                    except FloodWait as e:
                        if yield_on_flood:
                            _c = {
                                chat_links: dialog_chats[
                                    get_input_peer_id(peer)
                                ]
                                for chat_links, peer in zip(chats, peers)
                                if peer is not None
                                and get_input_peer_id(peer) in dialog_chats
                            }
                            yield CheckChatsFloodWait(_c, e.value)
                            continue
                        elif yield_on_flood is None:
                            flood = monotonic() + e.value
                        else:
                            raise
                    except RPCError as exception:
                        if yield_on_exception:
                            yield exception
                            continue
                        elif yield_on_exception is not None:
                            raise
                    break
                if success:
                    break
            else:
                yield None
