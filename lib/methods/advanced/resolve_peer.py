"""The module with the :meth:`AdBotClient.resolve_peer`."""

from re import sub
from typing import TYPE_CHECKING, Union

from pyrogram.errors.exceptions.bad_request_400 import (
    ChannelInvalid,
    PeerIdInvalid,
)
from pyrogram.raw.functions.channels.get_channels import GetChannels
from pyrogram.raw.functions.contacts.resolve_username import ResolveUsername
from pyrogram.raw.functions.messages.get_chats import GetChats
from pyrogram.raw.functions.users.get_users import GetUsers
from pyrogram.raw.types.channel import Channel as RawChannel
from pyrogram.raw.types.chat import Chat as RawChat
from pyrogram.raw.types.input_channel import InputChannel
from pyrogram.raw.types.input_peer_channel import InputPeerChannel
from pyrogram.raw.types.input_peer_chat import InputPeerChat
from pyrogram.raw.types.input_peer_self import InputPeerSelf
from pyrogram.raw.types.input_peer_user import InputPeerUser
from pyrogram.raw.types.input_user import InputUser
from pyrogram.raw.types.peer_channel import PeerChannel
from pyrogram.raw.types.peer_chat import PeerChat
from pyrogram.raw.types.peer_user import PeerUser
from pyrogram.raw.types.user import User as RawUser
from pyrogram.types.user_and_chats.chat import Chat
from pyrogram.types.user_and_chats.user import User
from pyrogram.utils import get_channel_id, get_peer_type

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class ResolvePeer(object):
    async def resolve_peer(
        self: 'AdBotClient',
        peer_id: Union[int, str],
        /,
        *,
        fetch: bool = True,
        force: bool = False,
    ) -> Union[InputPeerChannel, InputPeerChat, InputPeerUser]:
        """
        Get the InputPeer of a known peer id.

        .. note::

            This is a utility method intended to be used **only** when working
            with raw :obj:`functions <pyrogram.api.functions>` (i.e: a Telegram
            API method you wish to use which is not available yet in the Client
            class as an easy-to-use method).

        Parameters:
            peer_id (``int`` | ``str``):
                The peer id you want to extract the InputPeer from.
                Can be a direct id (int), a username (str) or a phone number
                (str).

        Returns:
            On success, the resolved peer id is returned in form
            of an `InputPeer` object.

        Raises:
            KeyError: In case the peer doesn't exist in the internal database.
        """
        if isinstance(
            peer_id,
            (InputPeerChannel, InputPeerChat, InputPeerUser),
        ):
            return peer_id
        elif isinstance(peer_id, InputChannel):
            return InputPeerChannel(
                channel_id=peer_id.channel_id,
                access_hash=peer_id.access_hash,
            )
        elif isinstance(peer_id, InputUser):
            return InputPeerUser(
                user_id=peer_id.user_id,
                access_hash=peer_id.access_hash,
            )

        elif isinstance(peer_id, (User, Chat, RawUser)):
            peer_id = peer_id.id
        elif isinstance(peer_id, RawChat):
            peer_id = -peer_id.id
        elif isinstance(peer_id, RawChannel):
            peer_id = get_channel_id(peer_id.id)

        elif isinstance(peer_id, PeerUser):
            peer_id = peer_id.user_id
        elif isinstance(peer_id, PeerChat):
            peer_id = -peer_id.chat_id
        elif isinstance(peer_id, PeerChannel):
            peer_id = get_channel_id(peer_id.channel_id)

        if isinstance(peer_id, int):
            try:
                if force:
                    raise KeyError
                return await self.storage.get_peer_by_id(peer_id)
            except KeyError as e:
                if not force and not fetch:
                    raise PeerIdInvalid from e

                peer_type = get_peer_type(peer_id)
                if peer_type == 'user':
                    user = InputUser(user_id=peer_id, access_hash=0)
                    await self.fetch_peers(
                        await self.invoke(GetUsers(id=[user]))
                    )
                elif peer_type == 'chat':
                    await self.invoke(GetChats(id=[-peer_id]))
                else:
                    channel = InputChannel(
                        channel_id=get_channel_id(peer_id),
                        access_hash=0,
                    )
                    try:
                        await self.invoke(GetChannels(id=[channel]))
                    except ChannelInvalid:
                        raise PeerIdInvalid from e

                try:
                    return await self.storage.get_peer_by_id(peer_id)
                except KeyError as e:
                    raise PeerIdInvalid from e

        elif isinstance(peer_id, str):
            if peer_id in {'self', 'me'}:
                return InputPeerSelf()

            peer_id = sub(r'[@+\s]', '', peer_id.lower())
            try:
                int(peer_id)
            except ValueError as e:
                try:
                    if force:
                        raise KeyError from e
                    return await self.storage.get_peer_by_username(peer_id)
                except KeyError as e:
                    if not force and not fetch:
                        raise PeerIdInvalid from e

                    await self.invoke(ResolveUsername(username=peer_id))
                    try:
                        return await self.storage.get_peer_by_username(peer_id)
                    except KeyError as e:
                        raise PeerIdInvalid from e
            else:
                try:
                    return await self.storage.get_peer_by_phone_number(peer_id)
                except KeyError as e:
                    raise PeerIdInvalid from e

        else:
            raise PeerIdInvalid
