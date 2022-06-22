"""The module with the :meth:`AdBotClient.initialize`."""


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class Initialize(object):
    async def initialize(self: 'AdBotClient', /) -> None:
        """
        Initialize the client by starting up workers.

        This method will start updates and download workers.
        It will also load plugins and start the internal dispatcher.

        Raises:
            ConnectionError: In case you try to initialize a disconnected
            client or in case you try to initialize an already initialized
            client.
        """
        if not self.is_connected:
            raise ConnectionError("Can't initialize a disconnected client.")
        elif self.is_initialized:
            raise ConnectionError('Client is already initialized.')

        self.load_plugins()

        me = await self.get_me()
        self.username, self.is_bot = me.username, me.is_bot
        self.is_initialized = True
