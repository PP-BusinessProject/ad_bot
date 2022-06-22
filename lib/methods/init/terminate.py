"""The module with the :meth:`AdBotClient.terminate`."""

from typing import TYPE_CHECKING

from pyrogram.methods.auth.terminate import log
from pyrogram.raw.functions.account.finish_takeout_session import (
    FinishTakeoutSession,
)

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class Terminate(object):
    async def terminate(self: 'AdBotClient', /) -> None:
        """
        Terminate the client by shutting down workers.

        This method does the opposite of :meth:`~pyrogram.Client.initialize`.
        It will stop the dispatcher and shut down updates and download workers.

        Raises:
            ConnectionError: In case you try to terminate a client that is
            already terminated.
        """
        if not self.is_initialized:
            raise ConnectionError("Client is already terminated")
        elif self.takeout_id:
            await self.invoke(FinishTakeoutSession())
            log.warning(f"Takeout session {self.takeout_id} finished")

        for media_session in self.media_sessions.values():
            await media_session.stop()
        self.media_sessions.clear()
        self.is_initialized = False
