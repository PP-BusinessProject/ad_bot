"""The module with the :meth:`AdBotClient.get_channel_participants`."""

from typing import TYPE_CHECKING, AsyncGenerator, Union

from pyrogram.raw.functions.channels.get_participants import GetParticipants
from pyrogram.raw.types.channels.channel_participants import (
    ChannelParticipants,
)
from pyrogram.raw.types.input_channel import InputChannel
from pyrogram.raw.types.input_peer_channel import InputPeerChannel

from ..typings.get_channel_participants import (
    ChannelParticipantsFilter,
    ChannelParticipantsFilterMap,
    ChannelParticipantsFilterMapReversed,
    ChannelParticipantsFilterStr,
    ChannelParticipantType,
)

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient


class IterChannelParticipants(object):
    async def iter_channel_participants(
        self: 'AdBotClient',
        channel_id: Union[int, str],
        /,
        filter: Union[
            ChannelParticipantsFilterStr,
            ChannelParticipantsFilter,
        ] = 'recent',
        offset: int = 0,
        limit: int = 0,
    ) -> AsyncGenerator[ChannelParticipantType, None]:
        """
        Return participant of the specified `channel_id` and `filter`.

        Args:
            channel_id (``Union[int, str]``):
                The link to channel peer to fetch.

            filter (``...``, *optional*):
                The filter of the participants to fetch. Defaults to `recent`.

            offset (``int``, *optional*):
                The offset to fetch participants from.

            limit (``int``, *optional*):
                The maximum count of participants to fetch.

        Returns:
            The asynchronous generator of the fetched participants.

        Raises:
            * ValueError, if the specified `channel_id` or `filter` is not
            valid.
        """
        peer: InputPeerChannel = await self.resolve_peer(channel_id)
        if not isinstance(peer, InputPeerChannel):
            raise ValueError(
                f'Specified channel_id `{channel_id}` does not link to a '
                'channel.'
            )

        if isinstance(filter, str) and filter in ChannelParticipantsFilterMap:
            filter = ChannelParticipantsFilterMap[filter]()
        if not isinstance(filter, tuple(ChannelParticipantsFilterMapReversed)):
            raise ValueError(f'Unknown users filter: {filter}.')

        current: int = 0
        total: int = limit or (1 << 31)
        limit: int = min(100, total)

        input_channel = InputChannel(
            channel_id=peer.channel_id,
            access_hash=peer.access_hash,
        )
        while True:
            response: ChannelParticipants = await self.send(
                GetParticipants(
                    channel=input_channel,
                    filter=filter,
                    offset=offset,
                    limit=limit,
                    hash=0,
                )
            )
            for participant in response.participants:
                yield participant
                if (current := current + 1) >= total:
                    break
            else:
                if len(response.participants) >= limit:
                    offset += len(response.participants)
                    continue
            break
