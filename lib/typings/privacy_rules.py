"""The module with typings for :meth:`AdBotClient.set_privacy`."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Literal, Type, Union

from pyrogram.raw.types.input_privacy_key_added_by_phone import (
    InputPrivacyKeyAddedByPhone,
)
from pyrogram.raw.types.input_privacy_key_chat_invite import (
    InputPrivacyKeyChatInvite,
)
from pyrogram.raw.types.input_privacy_key_forwards import (
    InputPrivacyKeyForwards,
)
from pyrogram.raw.types.input_privacy_key_phone_call import (
    InputPrivacyKeyPhoneCall,
)
from pyrogram.raw.types.input_privacy_key_phone_number import (
    InputPrivacyKeyPhoneNumber,
)
from pyrogram.raw.types.input_privacy_key_phone_p2_p import (
    InputPrivacyKeyPhoneP2P,
)
from pyrogram.raw.types.input_privacy_key_profile_photo import (
    InputPrivacyKeyProfilePhoto,
)
from pyrogram.raw.types.input_privacy_key_status_timestamp import (
    InputPrivacyKeyStatusTimestamp,
)
from pyrogram.raw.types.input_privacy_value_allow_all import (
    InputPrivacyValueAllowAll,
)
from pyrogram.raw.types.input_privacy_value_allow_chat_participants import (
    InputPrivacyValueAllowChatParticipants,
)
from pyrogram.raw.types.input_privacy_value_allow_contacts import (
    InputPrivacyValueAllowContacts,
)
from pyrogram.raw.types.input_privacy_value_allow_users import (
    InputPrivacyValueAllowUsers,
)
from pyrogram.raw.types.input_privacy_value_disallow_all import (
    InputPrivacyValueDisallowAll,
)
from pyrogram.raw.types.input_privacy_value_disallow_chat_participants import (
    InputPrivacyValueDisallowChatParticipants,
)
from pyrogram.raw.types.input_privacy_value_disallow_contacts import (
    InputPrivacyValueDisallowContacts,
)
from pyrogram.raw.types.input_privacy_value_disallow_users import (
    InputPrivacyValueDisallowUsers,
)

#
InputPrivacyKeyStr: Final = Literal[
    'added_by_phone',
    'chat_invite',
    'forwards',
    'phone_call',
    'phone_number',
    'phone_p2p',
    'profile_photo',
    'status_timestamp',
]


InputPrivacyKeyMap: Final[
    MappingProxyType[InputPrivacyKeyStr, Type[InputPrivacyKey]]
] = MappingProxyType(
    dict(
        added_by_phone=InputPrivacyKeyAddedByPhone,
        chat_invite=InputPrivacyKeyChatInvite,
        forwards=InputPrivacyKeyForwards,
        phone_call=InputPrivacyKeyPhoneCall,
        phone_number=InputPrivacyKeyPhoneNumber,
        phone_p2p=InputPrivacyKeyPhoneP2P,
        profile_photo=InputPrivacyKeyProfilePhoto,
        status_timestamp=InputPrivacyKeyStatusTimestamp,
    )
)


InputPrivacyKeyMapReversed: Final[
    MappingProxyType[Type[InputPrivacyKey], InputPrivacyKeyStr]
] = MappingProxyType(
    {
        InputPrivacyKeyAddedByPhone: 'added_by_phone',
        InputPrivacyKeyChatInvite: 'chat_invite',
        InputPrivacyKeyForwards: 'forwards',
        InputPrivacyKeyPhoneCall: 'phone_call',
        InputPrivacyKeyPhoneNumber: 'phone_number',
        InputPrivacyKeyPhoneP2P: 'phone_p2p',
        InputPrivacyKeyProfilePhoto: 'profile_photo',
        InputPrivacyKeyStatusTimestamp: 'status_timestamp',
    }
)


InputPrivacyKey: Final = Union[
    InputPrivacyKeyAddedByPhone,
    InputPrivacyKeyChatInvite,
    InputPrivacyKeyForwards,
    InputPrivacyKeyPhoneCall,
    InputPrivacyKeyPhoneNumber,
    InputPrivacyKeyPhoneP2P,
    InputPrivacyKeyProfilePhoto,
    InputPrivacyKeyStatusTimestamp,
]


InputPrivacyValueAllow: Final = Union[
    InputPrivacyValueAllowAll,
    InputPrivacyValueAllowChatParticipants,
    InputPrivacyValueAllowContacts,
    InputPrivacyValueAllowUsers,
]

InputPrivacyValueDisallow: Final = Union[
    InputPrivacyValueDisallowAll,
    InputPrivacyValueDisallowChatParticipants,
    InputPrivacyValueDisallowContacts,
    InputPrivacyValueDisallowUsers,
]
