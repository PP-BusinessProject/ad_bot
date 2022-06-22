"""The module with the :meth:`AdBotClient.connect`."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient

from ...ad_bot_session import AdBotSession


class Connect(object):
    async def connect(self: 'AdBotClient', /) -> bool:
        """
        Connect the client to Telegram servers.

        Returns:
            ``bool``: On success, in case the passed-in session is authorized,
            True is returned. Otherwise, in case the session needs to be
            authorized, False is returned.

        Raises:
            ConnectionError: In case you try to connect an already connected
            client.
        """
        if self.is_connected:
            raise ConnectionError('Client is already connected.')

        await self.storage.open()
        session = await self.storage._get_session()
        self.session = AdBotSession(
            self,
            session.dc_id,
            session.test_mode,
            session.auth_key,
        )
        await self.session.start()
        self.is_connected = True
        return bool(await self.storage.user_id())
