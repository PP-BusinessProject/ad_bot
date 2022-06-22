"""The module with the :meth:`AdBotClient.apply_profile_settings`."""

from contextlib import suppress
from typing import TYPE_CHECKING

from pyrogram.errors.rpc_error import RPCError
from sqlalchemy.sql.expression import select

from ...models.clients.bot_model import BotModel
from ...models.clients.user_model import UserModel, UserRole

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class ApplyProfileSettings(object):
    async def apply_profile_settings(
        self: 'AdBotClient',
        bot: BotModel,
        /,
    ) -> None:
        """
        Set the profile of the `self` as is in the `bot`.

        Args:
            self (``Client``):
                The self to set the profile of.

            bot (``BotModel``):
                The bot to set the profile of the `self` from.

            only_confirmed (``bool``, *optional*):
                If the settings should be applied only if `bot` is confirmed.

        Returns:
            Nothing.
        """
        await self.set_privacy(
            ('added_by_phone', 'forwards', 'phone_number'),
            'contacts',
        )
        await self.set_privacy(
            ('status_timestamp', 'chat_invite', 'phone_call', 'phone_p2p'),
            None,
        )

        with suppress(RPCError):
            _ = 'Владелец'
            await self.add_contact(bot.owner.id, _, share_phone_number=True)
        if bot.owner.role < UserRole.ADMIN:
            role: UserRole
            async for user_id, role in await self.storage.Session.stream(
                select(UserModel.id, UserModel.role)
                .where(UserModel.role >= UserRole.SUPPORT)
                .where(UserModel.id != bot.owner.id)
            ):
                _ = ' '.join((role.name.capitalize(), str(user_id)))
                await self.add_contact(user_id, _, share_phone_number=True)

        with suppress(RPCError):
            await self.update_profile(
                first_name=bot.first_name,
                last_name=bot.last_name or '',
                bio=bot.about or '',
            )
        with suppress(RPCError):
            await self.set_username(bot.username)
