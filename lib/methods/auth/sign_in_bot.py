"""The module with the :meth:`AdBotClient.sign_in_bot`."""

from pyrogram.errors import UserMigrate
from pyrogram.raw.functions.auth.import_bot_authorization import (
    ImportBotAuthorization,
)
from pyrogram.session import Auth
from pyrogram.types.user_and_chats.user import User

from typing import TYPE_CHECKING
from ...ad_bot_session import AdBotSession

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class SignInBot(object):
    async def sign_in_bot(self: 'AdBotClient', bot_token: str, /) -> User:
        """
        Authorize a bot using its `bot_token` generated by `BotFather`.

        Parameters:
            bot_token (``str``):
                The bot token generated by `BotFather`.

        Returns:
            On success, the bot identity is returned in form of a user object.

        Raises:
            BadRequest: In case the bot token is invalid.
        """
        while True:
            try:
                r = await self.invoke(
                    ImportBotAuthorization(
                        flags=0,
                        api_id=self.api_id,
                        api_hash=self.api_hash,
                        bot_auth_token=bot_token,
                    )
                )
            except UserMigrate as e:
                await self.session.stop()
                await self.storage.dc_id(e.value)
                test_mode = await self.storage.test_mode()
                await self.storage.auth_key(
                    await Auth(self, e.value, test_mode).create()
                )
                self.session = AdBotSession(
                    self,
                    await self.storage.dc_id(),
                    await self.storage.test_mode(),
                    await self.storage.auth_key(),
                )
                await self.session.start()
            else:
                await self.storage.user_id(r.user.id)
                await self.storage.is_bot(True)
                return User._parse(self, r.user)
