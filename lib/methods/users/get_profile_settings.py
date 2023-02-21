"""The module with the :meth:`AdBotClient.get_profile_settings`."""

from typing import TYPE_CHECKING, Optional

from pyrogram.errors import RPCError, UsernameNotOccupied
from pyrogram.raw.functions.users import GetFullUser
from pyrogram.raw.types.users.user_full import UserFull
from pyrogram.types import InputMediaPhoto, User

from ...models._constraints import MAX_USERNAME_LENGTH
from ...models.clients.bot_model import BotModel

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class GetProfileSettings(object):
    async def get_profile_settings(
        self: 'AdBotClient',
        bot: BotModel,
        /,
        user_id: Optional[int] = None,
        *,
        force: bool = False,
    ) -> None:
        """
        Set the profile of the `bot` as is in the `user`.

        Args:
            bot (``BotModel``):
                The bot to update from.

            user_id (``Optional[int]``, *optional*):
                The link to the user to use as the profile for bot instead of
                bot's owner.

        Returns:
            Nothing, just updates the `bot's` arguments.
        """
        user_peer = await self.resolve_peer(user_id or bot.owner_id)
        user_full: UserFull = await self.invoke(GetFullUser(id=user_peer))
        if user_full.full_user.about:
            bot.about = user_full.full_user.about
        elif force:
            bot.about = None

        user: User = next(iter(user_full.users))
        bot.first_name = user.first_name
        if force or user.last_name:
            bot.last_name = user.last_name

        if force and not user.username:
            bot.username = None
        elif user.username:
            username = f'{user.username}_helper'
            if len(username) > MAX_USERNAME_LENGTH:
                username = f'{user.username}_h'
            if len(username) <= MAX_USERNAME_LENGTH:
                _user: Optional[User] = None
                try:
                    _user = await self.get_users(username)
                except (UsernameNotOccupied, IndexError):
                    bot.username = username.removeprefix('@')
                except RPCError:
                    pass
                finally:
                    if _user and _user.phone_number == str(bot.phone_number):
                        bot.username = username.removeprefix('@')
                    elif force:
                        bot.username = None

        avatars: list[InputMediaPhoto] = [
            InputMediaPhoto(photo.file_id)
            async for photo in self.get_chat_photos(user_id or bot.owner.id)
        ]
        if not avatars:
            if force and bot.avatar_message_id is not None:
                # await self.delete_service_avatar(bot)
                bot.avatar_message_id = None

        elif len(avatars) == 1:
            # if bot.avatar_message_id is not None:
            #     await self.delete_service_avatar(bot)
            if await self.check_chats(
                (bot.owner.service_id, bot.owner.service_invite)
            ):
                avatar_message = await self.send_cached_media(
                    bot.owner.service_id,
                    next(iter(avatars)).media,
                )
                bot.avatar_message_id = avatar_message.id

        elif await self.check_chats(
            (bot.owner.service_id, bot.owner.service_invite)
        ):
            avatar_messages = await self.send_media_group(
                bot.owner.service_id, avatars
            )
            bot.avatar_message_id = avatar_messages[0].id
