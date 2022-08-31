"""The module with the :meth:`AdBotClient.initialize_user_service`."""

from contextlib import suppress
from typing import TYPE_CHECKING, Any, Iterable, Union

from pyrogram.errors.exceptions.bad_request_400 import (
    AdminsTooMuch,
    PeerIdInvalid,
)
from pyrogram.errors.rpc_error import RPCError
from pyrogram.raw.types.channel_participant_admin import (
    ChannelParticipantAdmin,
)
from pyrogram.raw.types.input_peer_user import InputPeerUser
from pyrogram.types.user_and_chats.chat_privileges import ChatPrivileges

from ...models.clients.user_model import UserModel

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class InitializeUserService(object):
    async def initialize_user_service(
        self: 'AdBotClient',
        user: UserModel,
        /,
        title: str = 'Сервис {user_id}',
        promote_users: Union[None, int, str, Iterable[Union[int, str]]] = (),
        *,
        demote_users: bool = True,
    ) -> None:
        """
        Initialize a service channel for the `user`.

        Checks for client's dialogs for the name matching `title`. If one is
        found, uses that channel as the user's service channel. Then checks for
        admins to be matching `promote_users` and promotes the unmatching ones.

        Args:
            user (``UserModel``):
                The user to initialize a service channel for.

            title (``str``, *optional*):
                The title of a service channel to set. Formats `user_id` to
                format in the string.

            promote_users (``Union[int, str, Iterable[Union[int, str]]]``):
                The one or many users to promote to admins in the user's
                service channel.

            demote_users (``bool``, *optional*):
                If the admins should be demoted in case there are too many
                admins in the service channel in order to `promote_users`.

        Returns:
            The user with filled service channel properties.
        """

        def is_iterable(_: Any, /) -> bool:
            return not isinstance(_, str) and isinstance(_, Iterable)

        if promote_users is not None and not is_iterable(promote_users):
            promote_users: Iterable[Union[int, str]] = (promote_users,)

        promote_user_ids: dict[int, InputPeerUser] = {}
        for promote_user in promote_users or ():
            with suppress(PeerIdInvalid):
                peer = await self.resolve_peer(promote_user)
                if isinstance(peer, InputPeerUser):
                    promote_user_ids[peer.user_id] = peer

        freshly_created: bool = False
        if user.service_id is None or not await self.check_chats(
            (user.service_id, user.service_invite)
        ):
            title = title.format(user_id=user.id)
            dialog = None
            async for dialog in self.iter_dialogs():
                if dialog.chat.title == title:
                    if dialog.chat.is_creator:
                        user.service_id = dialog.chat.id
                        if user.service_invite is None:
                            user.service_invite = dialog.chat.invite_link
                    break
            if dialog is None or (
                dialog.chat.title != title or not dialog.chat.is_creator
            ):
                freshly_created = True
                chat = await self.create_channel(title)
                user.service_id = chat.id
                user.service_invite = chat.invite_link
        if user.service_invite is None:
            user.service_invite = await self.export_chat_invite_link(
                user.service_id
            )

        promoted_participants: set[int] = set()
        demote_admins: list[ChannelParticipantAdmin] = []
        if promote_user_ids and not freshly_created:
            admin: ChannelParticipantAdmin
            async for admin in self.iter_channel_participants(
                user.service_id, 'admins'
            ):
                if admin.user_id in promote_user_ids:
                    promoted_participants.add(admin.user_id)
                elif isinstance(admin, ChannelParticipantAdmin) and (
                    not admin.is_self and demote_users
                ):
                    demote_admins.append(admin)

        demoted_admins: set[int] = set()
        for promote_id in promote_user_ids:
            if promote_id in promoted_participants:
                continue
            while True:
                try:
                    await self.promote_chat_member(
                        user.service_id,
                        promote_user_ids[promote_id],
                        privileges=ChatPrivileges(
                            can_manage_chat=True,
                            can_delete_messages=True,
                            can_restrict_members=True,
                            can_promote_members=True,
                            can_change_info=True,
                            can_post_messages=True,
                            can_edit_messages=True,
                            can_invite_users=True,
                            is_anonymous=False,
                        ),
                    )
                except AdminsTooMuch:
                    for admin in demote_admins:
                        if admin.user_id not in demoted_admins:
                            demoted_admins.add(admin.user_id)
                            with suppress(RPCError):
                                await self.promote_chat_member(
                                    user.service_id,
                                    admin.user_id,
                                    privileges=ChatPrivileges(
                                        can_manage_chat=True,
                                        can_delete_messages=True,
                                        can_restrict_members=True,
                                        can_promote_members=True,
                                        can_change_info=True,
                                        can_post_messages=True,
                                        can_edit_messages=True,
                                        can_invite_users=True,
                                        is_anonymous=False,
                                    ),
                                )
                                break
                    else:
                        raise
                else:
                    break

        return user
