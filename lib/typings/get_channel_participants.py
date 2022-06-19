"""The module with typings for :meth:`AdBotClient.get_channel_participants`."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Literal, Type, Union

from pyrogram.raw.types.channel_participant import ChannelParticipant
from pyrogram.raw.types.channel_participant_admin import (
    ChannelParticipantAdmin,
)
from pyrogram.raw.types.channel_participant_banned import (
    ChannelParticipantBanned,
)
from pyrogram.raw.types.channel_participant_creator import (
    ChannelParticipantCreator,
)
from pyrogram.raw.types.channel_participant_left import ChannelParticipantLeft
from pyrogram.raw.types.channel_participant_self import ChannelParticipantSelf
from pyrogram.raw.types.channel_participants_admins import (
    ChannelParticipantsAdmins,
)
from pyrogram.raw.types.channel_participants_banned import (
    ChannelParticipantsBanned,
)
from pyrogram.raw.types.channel_participants_bots import (
    ChannelParticipantsBots,
)
from pyrogram.raw.types.channel_participants_contacts import (
    ChannelParticipantsContacts,
)
from pyrogram.raw.types.channel_participants_kicked import (
    ChannelParticipantsKicked,
)
from pyrogram.raw.types.channel_participants_mentions import (
    ChannelParticipantsMentions,
)
from pyrogram.raw.types.channel_participants_recent import (
    ChannelParticipantsRecent,
)
from pyrogram.raw.types.channel_participants_search import (
    ChannelParticipantsSearch,
)

#
# ChannelParticipantsRecent	    Fetch only recent participants
# ChannelParticipantsAdmins	    Fetch only admin participants
# ChannelParticipantsKicked	    Fetch only kicked participants
# ChannelParticipantsBots	    Fetch only bot participants
# ChannelParticipantsBanned	    Fetch only banned participants
# ChannelParticipantsSearch	    Query participants by name
# ChannelParticipantsContacts	Fetch only participants that are also contacts
# ChannelParticipantsMentions	This filter is used when looking for members
#                               to mention.

ChannelParticipantsFilterStr: Final = Literal[
    'recent',
    'admins',
    'kicked',
    'bots',
    'banned',
    'search',
    'contacts',
    'mentions',
]


ChannelParticipantsFilterMap: Final[
    MappingProxyType[
        ChannelParticipantsFilterStr, Type[ChannelParticipantsFilter]
    ]
] = MappingProxyType(
    dict(
        recent=ChannelParticipantsRecent,
        admins=ChannelParticipantsAdmins,
        kicked=ChannelParticipantsKicked,
        bots=ChannelParticipantsBots,
        banned=ChannelParticipantsBanned,
        search=ChannelParticipantsSearch,
        contacts=ChannelParticipantsContacts,
        mentions=ChannelParticipantsMentions,
    )
)


ChannelParticipantsFilterMapReversed: Final[
    MappingProxyType[
        Type[ChannelParticipantsFilter], ChannelParticipantsFilterStr
    ]
] = MappingProxyType(
    {
        ChannelParticipantsRecent: 'recent',
        ChannelParticipantsAdmins: 'admins',
        ChannelParticipantsKicked: 'kicked',
        ChannelParticipantsBots: 'bots',
        ChannelParticipantsBanned: 'banned',
        ChannelParticipantsSearch: 'search',
        ChannelParticipantsContacts: 'contacts',
        ChannelParticipantsMentions: 'mentions',
    }
)

ChannelParticipantsFilter: Final = Union[
    ChannelParticipantsRecent,
    ChannelParticipantsAdmins,
    ChannelParticipantsKicked,
    ChannelParticipantsBots,
    ChannelParticipantsBanned,
    ChannelParticipantsSearch,
    ChannelParticipantsContacts,
    ChannelParticipantsMentions,
]


# СhannelParticipant	    Channel/supergroup participant
# СhannelParticipantSelf	Myself
# СhannelParticipantCreator	Channel/supergroup creator
# СhannelParticipantAdmin	Admin
# СhannelParticipantBanned	Banned/kicked user
# СhannelParticipantLeft	A participant that left the channel/supergroup


ChannelParticipantType: Final = Union[
    ChannelParticipant,
    ChannelParticipantSelf,
    ChannelParticipantCreator,
    ChannelParticipantAdmin,
    ChannelParticipantBanned,
    ChannelParticipantLeft,
]
