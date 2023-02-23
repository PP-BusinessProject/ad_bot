"""The module with the :meth:`AdBotClient.apply_profile_settings`."""

from contextlib import suppress
from typing import TYPE_CHECKING

from pyrogram.errors.rpc_error import RPCError
from pyrogram.types.messages_and_media.message import Message
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
            users = await self.storage.Session.execute(
                select(UserModel.id, UserModel.role)
                .where(UserModel.role >= UserRole.SUPPORT)
                .where(UserModel.id != bot.owner.id)
            )
            for user_id, role in users.all():
                _ = ' '.join((role.name.capitalize(), str(user_id)))
                await self.add_contact(user_id, _, share_phone_number=True)

        with suppress(RPCError):
            await self.update_profile(
                first_name=bot.first_name,
                last_name=bot.last_name or '',
                bio=bot.about or '',
            )
        if self.username != bot.username:
            with suppress(RPCError):
                await self.set_username(bot.username)
                self.username = bot.username

        photos = [_.file_id async for _ in self.get_chat_photos('me')]
        if bot.avatar_message_id is not None:
            photos_messages: list[Message] = [
                message
                for message in await self.get_messages(
                    bot.owner.service_id,
                    range(
                        bot.avatar_message_id,
                        bot.avatar_message_id + 10,
                    ),
                )
                if message.photo is not None
            ]
            avatar_message = next(iter(photos_messages), None)
            photos_messages = (
                [
                    message
                    for message in photos_messages
                    if message.media_group_id == avatar_message.media_group_id
                ]
                if avatar_message and avatar_message.media_group_id
                else photos_messages[:1]
            )

            photos_to_delete: list[str] = []
            for index, message in reversed(tuple(enumerate(photos_messages))):
                if index < len(photos):
                    if not photos_to_delete and (
                        photos[index] == message.photo.file_id
                    ):
                        continue
                    photos_to_delete.append(photos[index])

                await self.set_profile_photo(
                    photo=await message.download(in_memory=True)
                )
        else:
            photos_to_delete = photos

        if photos_to_delete:
            with suppress(RPCError):
                await self.delete_profile_photos(photos_to_delete)
