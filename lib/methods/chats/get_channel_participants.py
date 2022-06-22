from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Iterable,
    Optional,
    Union,
    overload,
)

from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.raw.functions.channels.get_participant import GetParticipant
from pyrogram.raw.types.input_channel import InputChannel
from pyrogram.raw.types.input_peer_channel import InputPeerChannel
from typing_extensions import Self

from ...typings.get_channel_participants import ChannelParticipantType

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class GetChannelParticipants(object):
    @overload
    async def get_channel_participants(
        self: Self,
        chats: Union[int, str],
        /,
    ) -> Optional[ChannelParticipantType]:
        pass

    @overload
    async def get_channel_participants(
        self: Self,
        chats: Iterable[Union[int, str]],
        /,
    ) -> list[Union[ChannelParticipantType, None]]:
        pass

    async def get_channel_participants(
        self: 'AdBotClient',
        channel_id: Union[int, str],
        /,
        users: Union[int, str, Iterable[Union[int, str]]],
    ) -> list[Union[ChannelParticipantType, None]]:
        """
        Return participants of the specified `channel_id` with `filter`.

        Args:
            channel_id (``Union[int, str]``):
                The link to channel peer to fetch participants from.

            users (``Union[int, str, Iterable[Union[int, str]]]``):
                The one or many users to fetch as participants from
                `channel_id`.

        Returns:
            The list of the fetched participants or a single participant.
            Returns None if specified user is not a participant.

        Raises:
            * ValueError, if the specified `channel_id` or `users` are not
            valid.
        """

        def is_iterable(_: Any, /) -> bool:
            return not isinstance(_, str) and isinstance(_, Iterable)

        if not users:
            raise ValueError(f'Specified users are invalid: {users}.')
        elif not (is_iter := is_iterable(users)):
            users: Iterable[Union[int, str]] = (users,)

        agen = self.iter_get_channel_participants(channel_id, users)
        return [_ async for _ in agen] if is_iter else await anext(agen, None)

    async def iter_get_channel_participants(
        self: Self,
        channel_id: Union[int, str],
        /,
        users: Union[int, str, Iterable[Union[int, str]]],
    ) -> AsyncGenerator[ChannelParticipantType, None]:
        """
        Return participants of the specified `channel_id` with `filter`.

        Args:
            channel_id (``Union[int, str]``):
                The link to channel peer to fetch participants from.

            users (``Union[int, str, Iterable[Union[int, str]]]``):
                The one or many users to fetch as participants from
                `channel_id`.

        Returns:
            The asynchronous generator of the fetched participants. Yields None
            if specified user is not a participant.

        Raises:
            * ValueError, if the specified `channel_id` or `users` are not
            valid.
        """

        def is_iterable(_: Any, /) -> bool:
            return not isinstance(_, str) and isinstance(_, Iterable)

        if not users:
            raise ValueError(f'Specified users are invalid: {users}.')
        elif not is_iterable(users):
            users: Iterable[Union[int, str]] = (users,)

        channel_peer: InputPeerChannel = await self.resolve_peer(channel_id)
        if not isinstance(channel_peer, InputPeerChannel):
            raise ValueError(f'Specified channel is invalid: {channel_peer}.')

        channel = InputChannel(
            channel_id=channel_peer.channel_id,
            access_hash=channel_peer.access_hash,
        )
        for user in users:
            peer = await self.resolve_peer(user)
            try:
                response = await self.invoke(
                    GetParticipant(channel=channel, participant=peer)
                )
                yield response.participant
            except UserNotParticipant:
                yield None
