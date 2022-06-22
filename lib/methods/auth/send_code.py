"""The module with the :meth:`AdBotClient.send_code`."""

from pyrogram.errors import NetworkMigrate, PhoneMigrate
from pyrogram.raw.functions.auth.send_code import SendCode as RawSendCode
from pyrogram.raw.types.code_settings import CodeSettings
from pyrogram.session import Auth
from pyrogram.types.authorization.sent_code import SentCode

from typing import TYPE_CHECKING
from ...ad_bot_session import AdBotSession

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class SendCode(object):
    async def send_code(self: 'AdBotClient', phone_number: str, /) -> SentCode:
        """
        Send the confirmation code to the given phone number.

        Parameters:
            phone_number (``str``):
                Phone number in international format (includes the country
                prefix).

        Returns:
            On success, an object containing information on the sent
            confirmation code is returned.

        Raises:
            BadRequest: In case the phone number is invalid.
        """
        while True:
            try:
                r = await self.invoke(
                    RawSendCode(
                        phone_number=phone_number.strip(' +'),
                        api_id=self.api_id,
                        api_hash=self.api_hash,
                        settings=CodeSettings(),
                    )
                )
            except (PhoneMigrate, NetworkMigrate) as e:
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
                return SentCode._parse(r)
