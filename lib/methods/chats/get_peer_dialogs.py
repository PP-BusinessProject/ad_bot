from typing import TYPE_CHECKING, Iterable, Optional, Self, Union, overload

from pyrogram.raw.functions.messages.get_peer_dialogs import (
    GetPeerDialogs as RawGetPeerDialogs,
)
from pyrogram.raw.types.input_dialog_peer import InputDialogPeer
from pyrogram.raw.types.message_empty import MessageEmpty
from pyrogram.raw.types.messages.peer_dialogs import PeerDialogs
from pyrogram.types.messages_and_media.message import Message
from pyrogram.types.user_and_chats.chat import Chat
from pyrogram.types.user_and_chats.dialog import Dialog
from pyrogram.utils import get_peer_id

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class GetPeerDialogs(object):
    @overload
    async def get_peer_dialogs(
        self: Self,
        chats: Union[int, str, Chat],
        /,
        *,
        fetch_peers: bool = True,
    ) -> Optional[Dialog]:
        pass

    @overload
    async def get_peer_dialogs(
        self: Self,
        chats: Iterable[Union[int, str, Chat]],
        /,
        *,
        fetch_peers: bool = True,
    ) -> list[Dialog]:
        pass

    async def get_peer_dialogs(
        self: 'AdBotClient',
        chats: Union[int, str, Chat, Iterable[Union[int, str, Chat]]],
        /,
        *,
        fetch_peers: bool = True,
    ) -> Union[Optional[Dialog], list[Dialog]]:
        """
        Return the list of dialogs for the specified `chats`.

        Args:
            chats (``Union[int, str, Chat, Iterable[Union[int, str, Chat]]]``):
                The links to one or many chats to get dialogs for.

        Returns:
            The list of dialogs for the specified `chats` or a single dialog
            if only one chat was specified.

        Raises:
            * 400 CHANNEL_INVALID	The provided channel is invalid.
            * 400 CHANNEL_PRIVATE	You haven't joined this channel/supergroup.
            * 400 MSG_ID_INVALID	Invalid message ID provided.
            * 400 PEER_ID_INVALID	The provided peer id is invalid.
        """
        is_iter = isinstance(chats, Iterable) and not isinstance(chats, str)
        chat_peers = [
            InputDialogPeer(
                peer=await self.resolve_peer(
                    chat.id if isinstance(chat, Chat) else chat,
                )
            )
            for chat in (chats if is_iter else (chats,))
        ]

        response: PeerDialogs = await self.invoke(
            RawGetPeerDialogs(peers=chat_peers),
            fetch_peers=fetch_peers,
        )
        users = {user.id: user for user in response.users}
        chats = {chat.id: chat for chat in response.chats}
        messages = {
            get_peer_id(message.peer_id): await Message._parse(
                self, message, users, chats, replies=0
            )
            for message in response.messages
            if not isinstance(message, MessageEmpty)
        }
        dialogs = [
            Dialog._parse(self, dialog, messages, users, chats)
            for dialog in response.dialogs
        ]
        return dialogs if is_iter else next(iter(dialogs), None)
