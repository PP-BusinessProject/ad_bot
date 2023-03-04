"""The module with the :meth:`AdBotClient.connect`."""

from logging import getLogger
from typing import TYPE_CHECKING

from pyrogram.errors.exceptions.unauthorized_401 import Unauthorized
from pyrogram.raw.functions.account.init_takeout_session import (
    InitTakeoutSession,
)
from pyrogram.raw.functions.updates.get_state import GetState

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient

log = getLogger(__name__)


class Start(object):
    async def start(self: 'AdBotClient', /) -> 'AdBotClient':
        """
        Start the client.

        This method connects the client to Telegram and, in case of new
        sessions, automatically manages the authorization process using an
        interactive prompt.

        Returns:
            :obj:`~pyrogram.Client`: The started client itself.

        Raises:
            ConnectionError: In case you try to start an already started
            client.

        Example:
            .. code-block:: python

                from pyrogram import Client

                app = Client("my_account")


                async def main():
                    await app.start()
                    ...  # Invoke API methods
                    await app.stop()


                app.run(main())
        """
        try:
            if not await self.connect():
                if self.bot_token:
                    return await self.sign_in_bot(self.bot_token)
                raise Unauthorized()

            if self.storage.is_nested and self.takeout:
                self.takeout_id = (await self.invoke(InitTakeoutSession())).id
                log.info(
                    '[%s] Takeout session %s initiated',
                    self.storage.phone_number,
                    self.takeout_id,
                )

            if not self.storage.is_nested:
                await self.invoke(GetState())
            await self.initialize()
            return self
        except BaseException as _:
            log.warning(
                '[%s] Client did not start!', self.storage.phone_number
            )
            await self.disconnect()
            raise
