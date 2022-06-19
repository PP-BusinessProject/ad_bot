"""The module with the :meth:`AdBotClient.disconnect`."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient


class Disconnect(object):
    async def disconnect(self: 'AdBotClient', /) -> None:
        """
        Disconnect the client from Telegram servers.

        Raises:
            ConnectionError: In case you try to disconnect an already
            disconnected client or in case you try to disconnect a client
            that needs to be terminated first.
        """
        if not self.is_connected:
            raise ConnectionError('Client is already disconnected.')
        elif self.is_initialized:
            raise ConnectionError("Can't disconnect an initialized client.")

        await self.session.stop()
        await self.storage.close()
        self.is_connected = False
