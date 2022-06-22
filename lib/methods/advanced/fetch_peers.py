"""The module with the :meth:`AdBotClient.fetch_peers`."""

from typing import TYPE_CHECKING, Union

from pyrogram.raw.types.channel import Channel
from pyrogram.raw.types.channel_forbidden import ChannelForbidden
from pyrogram.raw.types.chat import Chat
from pyrogram.raw.types.chat_forbidden import ChatForbidden
from pyrogram.raw.types.user import User
from pyrogram.utils import get_channel_id

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class FetchPeers(object):
    async def fetch_peers(
        self: 'AdBotClient',
        peers: list[Union[User, Chat, Channel]],
        /,
    ) -> bool:
        parsed_peers: list[tuple[int, int, str, str, str]] = []
        is_min: bool = False
        for peer in peers:
            if getattr(peer, 'min', False):
                is_min = True
                continue

            if (phone_number := getattr(peer, 'phone', None)) is not None:
                phone_number = int(phone_number.removeprefix('+'))
            if (username := getattr(peer, 'username', None)) is not None:
                username = username.lower()

            if isinstance(peer, User):
                peer_id = peer.id
                access_hash = peer.access_hash
                peer_type = 'bot' if peer.bot else 'user'
            elif isinstance(peer, (Chat, ChatForbidden)):
                peer_id = -peer.id
                access_hash = 0
                peer_type = 'group'
            elif isinstance(peer, (Channel, ChannelForbidden)):
                peer_id = get_channel_id(peer.id)
                access_hash = peer.access_hash
                peer_type = 'channel' if peer.broadcast else 'supergroup'
            else:
                continue

            parsed_peers.append(
                (peer_id, access_hash, peer_type, username, phone_number)
            )
        await self.storage.update_peers(parsed_peers)
        return is_min

    # async def fetch_peers(
    #     self: Self,
    #     peers: list[Union[User, Chat, Channel]],
    #     /,
    # ) -> bool:
    #     is_min: bool = False
    #     for peer in peers:
    #         if getattr(peer, 'min', False):
    #             is_min = True
    #             continue

    #         if (username := getattr(peer, 'username', None)) is not None:
    #             username = username.lower()

    #         if isinstance(peer, User):
    #             peer = PeerModel(
    #                 session_name=self.storage.name,
    #                 id=peer.id,
    #                 access_hash=peer.access_hash,
    #                 type='bot' if peer.bot else 'user',
    #                 username=username,
    #                 phone_number=peer.phone,
    #             )
    #         elif isinstance(peer, (Chat, ChatForbidden)):
    #             peer = PeerModel(
    #                 session_name=self.storage.name,
    #                 id=-peer.id,
    #                 access_hash=0,
    #                 type='group',
    #             )
    #         elif isinstance(peer, (Channel, ChannelForbidden)):
    #             peer = PeerModel(
    #                 session_name=self.storage.name,
    #                 id=get_channel_id(peer.id),
    #                 access_hash=peer.access_hash,
    #                 type='channel' if peer.broadcast else 'supergroup',
    #                 username=username,
    #             )
    #         else:
    #             continue
    #     peer = await self.storage.update_peers(peer)
    #     await self.storage.Session.commit()
    #     return is_min
