"""The module with the :meth:`AdBotClient.set_privacy`."""

from typing import TYPE_CHECKING, Iterable, Optional, Union, overload

from pyrogram.raw.functions.account.set_privacy import (
    SetPrivacy as RawSetPrivacy,
)
from pyrogram.raw.types.input_peer_channel import InputPeerChannel
from pyrogram.raw.types.input_peer_chat import InputPeerChat
from pyrogram.raw.types.input_peer_user import InputPeerUser
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
from pyrogram.raw.types.input_user import InputUser
from pyrogram.raw.types.input_user_self import InputUserSelf
from typing_extensions import Self

from ...typings.privacy_rules import (
    InputPrivacyKey,
    InputPrivacyKeyMap,
    InputPrivacyKeyMapReversed,
    InputPrivacyKeyStr,
    InputPrivacyValueAllow,
    InputPrivacyValueDisallow,
)
from ...utils.pyrogram import get_input_peer_id

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class SetPrivacy(object):
    @overload
    async def set_privacy(
        self: Self,
        key: Union[InputPrivacyKeyStr, InputPrivacyKey],
        /,
        allow: Optional[
            Union[
                int,
                str,
                InputPrivacyValueAllow,
                Iterable[Union[int, str, InputPrivacyValueAllow]],
            ]
        ] = (),
        disallow: Optional[
            Union[
                int,
                str,
                InputPrivacyValueDisallow,
                Iterable[Union[int, str, InputPrivacyValueDisallow]],
            ]
        ] = None,
    ) -> list[Union[InputPrivacyValueAllow, InputPrivacyValueDisallow]]:
        pass

    @overload
    async def set_privacy(
        self: Self,
        key: Iterable[Union[InputPrivacyKeyStr, InputPrivacyKey]],
        /,
        allow: Optional[
            Union[
                int,
                str,
                InputPrivacyValueAllow,
                Iterable[Union[int, str, InputPrivacyValueAllow]],
            ]
        ] = (),
        disallow: Optional[
            Union[
                int,
                str,
                InputPrivacyValueDisallow,
                Iterable[Union[int, str, InputPrivacyValueDisallow]],
            ]
        ] = None,
    ) -> dict[
        str,
        list[Union[InputPrivacyValueAllow, InputPrivacyValueDisallow]],
    ]:
        pass

    async def set_privacy(
        self: 'AdBotClient',
        key: Union[
            InputPrivacyKeyStr,
            InputPrivacyKey,
            Iterable[Union[InputPrivacyKeyStr, InputPrivacyKey]],
        ],
        /,
        allow: Optional[
            Union[
                int,
                str,
                InputPrivacyValueAllow,
                Iterable[Union[int, str, InputPrivacyValueAllow]],
            ]
        ] = (),
        disallow: Optional[
            Union[
                int,
                str,
                InputPrivacyValueDisallow,
                Iterable[Union[int, str, InputPrivacyValueDisallow]],
            ]
        ] = None,
    ) -> Union[
        list[Union[InputPrivacyValueAllow, InputPrivacyValueDisallow]],
        dict[
            InputPrivacyKeyStr,
            list[Union[InputPrivacyValueAllow, InputPrivacyValueDisallow]],
        ],
    ]:
        """
        Set the privacy setting for specified :class:`InputPrivacyKey`.

        Args:
            key (``...``):
                The one or many keys to set the rules for.
                    The string values are set like specified in
                    :object:`InputPrivacyKeyMap`.

            allow (``...``, *optional*):
                The properties to allow for `key`.
                    If empty, sets the rules to `InputPrivacyValueAllowAll`.
                    User or chat links to allow can also be specified.

            disallow (``...``, *optional*):
                The properties to disallow for `key`.
                    If empty or None and `allow` is None, sets the rules to
                    `InputPrivacyValueDisallowAll`.
                    User or chat links to disallow can also be specified.

        Returns:
            The privacy rules that were defined for a single key or a
            dictionary of key and privacy rules pairs for multiple keys.

        Raises:
            * 400 ``PRIVACY_KEY_INVALID``:
                The privacy key is invalid.

            * 400 ``PRIVACY_TOO_LONG``:
                Too many privacy rules were specified, current limit is 1000.

            * 400 ``PRIVACY_VALUE_INVALID``:
                The specified privacy rule combination is invalid.
        """

        def get_key(key: Union[str, InputPrivacyKey]) -> InputPrivacyKey:
            if isinstance(key, str):
                if (_key := InputPrivacyKeyMap.get(key.strip())) is not None:
                    return _key()
            if not isinstance(key, InputPrivacyKey):
                raise ValueError(f'Unknown key: `{key}`.')
            return key

        keys: list[InputPrivacyKey] = []
        if isinstance(key, (str, InputPrivacyKey)):
            is_iterable = False
            keys.append(get_key(key))
        elif isinstance(key, Iterable):
            is_iterable = True
            for key in key:
                keys.append(get_key(key))
        if not keys:
            raise ValueError(f'Unknown key: `{key}`.')

        rules: list = []
        if allow is None:
            if disallow is None:
                rules.append(InputPrivacyValueDisallowAll())
        elif isinstance(allow, InputPrivacyValueAllow):
            rules.append(allow)
        elif isinstance(allow, (int, str)):
            if isinstance(allow, str) and (allow := allow.strip()) == 'all':
                rules.append(InputPrivacyValueAllowAll())
            elif isinstance(allow, str) and allow == 'contacts':
                rules.append(InputPrivacyValueAllowContacts())
            else:
                rules.append(await self.resolve_peer(allow))
        elif isinstance(allow, Iterable):
            if not allow:
                rules.append(InputPrivacyValueAllowAll())
            else:
                user_peers = list[InputUserSelf, InputPeerUser]()
                chat_peers = list[Union[InputPeerChat, InputPeerChannel]]()
                for peer in allow:
                    if isinstance(peer, InputPrivacyValueAllow):
                        rules.append(peer)
                        continue
                    peer = await self.resolve_peer(peer)
                    if isinstance(peer, (InputUserSelf, InputPeerUser)):
                        user_peers.append(peer)
                    elif isinstance(peer, (InputPeerChat, InputPeerChannel)):
                        chat_peers.append(peer)
                if user_peers:
                    rules.append(
                        InputPrivacyValueAllowUsers(
                            users=[
                                InputUser(
                                    user_id=peer.user_id,
                                    access_hash=peer.access_hash,
                                )
                                if isinstance(peer, InputPeerUser)
                                else peer
                                for peer in user_peers
                            ]
                        )
                    )
                if chat_peers:
                    rules.append(
                        InputPrivacyValueAllowChatParticipants(
                            chats=list(map(get_input_peer_id, chat_peers))
                        )
                    )

        if isinstance(disallow, InputPrivacyValueDisallow):
            rules.append(disallow)
        elif isinstance(disallow, (int, str)):
            if isinstance(disallow, str) and (
                (disallow := disallow.strip()) == 'all'
            ):
                rules.append(InputPrivacyValueDisallowAll())
            elif isinstance(disallow, str) and disallow == 'contacts':
                rules.append(InputPrivacyValueDisallowContacts())
            else:
                rules.append(await self.resolve_peer(disallow))
        elif isinstance(disallow, Iterable):
            if not disallow:
                rules.append(InputPrivacyValueDisallowAll())
            else:
                user_peers = list[InputUserSelf, InputPeerUser]()
                chat_peers = list[Union[InputPeerChat, InputPeerChannel]]()
                for peer in disallow:
                    if isinstance(peer, InputPrivacyValueDisallow):
                        rules.append(peer)
                        continue
                    peer = await self.resolve_peer(peer)
                    if isinstance(peer, (InputUserSelf, InputPeerUser)):
                        user_peers.append(peer)
                    elif isinstance(peer, (InputPeerChat, InputPeerChannel)):
                        chat_peers.append(peer)
                if user_peers:
                    rules.append(
                        InputPrivacyValueDisallowUsers(
                            users=[
                                InputUser(
                                    user_id=peer.user_id,
                                    access_hash=peer.access_hash,
                                )
                                if isinstance(peer, InputPeerUser)
                                else peer
                                for peer in user_peers
                            ]
                        )
                    )
                if chat_peers:
                    rules.append(
                        InputPrivacyValueDisallowChatParticipants(
                            chats=list(map(get_input_peer_id, chat_peers))
                        )
                    )

        if not rules:
            raise ValueError(
                f'No rules were specified for key `{keys[0]}`.'
                if len(keys) == 1
                else f'No rules were specified for keys `{keys}`.'
            )
        responses: dict[
            str,
            list[Union[InputPrivacyValueAllow, InputPrivacyValueDisallow]],
        ] = {
            InputPrivacyKeyMapReversed[key.__class__]: (
                await self.invoke(RawSetPrivacy(key=key, rules=rules))
            ).rules
            for key in keys
        }
        if not is_iterable:
            return next(iter(responses.values()), None)
        return responses
