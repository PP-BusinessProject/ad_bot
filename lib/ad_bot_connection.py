from asyncio import sleep as asleep
from logging import getLogger
from typing import TYPE_CHECKING, Final, Optional, Self

from pyrogram.connection.transport import TCP, TCPAbridged
from pyrogram.session.internals import DataCenter

if TYPE_CHECKING:
    from .ad_bot_client import AdBotClient

log = getLogger(__name__)


class AdBotConnection(object):
    MAX_CONNECTION_ATTEMPTS: Final[int] = 1

    def __init__(
        self: Self,
        client: 'AdBotClient',
        address: DataCenter,
        /,
    ):
        self.client, self.address = client, address
        self.protocol: TCP = None

    async def connect(self: Self, /):
        for _ in range(self.MAX_CONNECTION_ATTEMPTS):
            self.protocol = TCPAbridged(self.client.ipv6, self.client.proxy)
            try:
                log.debug('[%s] Connecting...', self.client.phone_number)
                await self.protocol.connect(self.address)
            except OSError as e:
                log.warning(
                    '[%s] Unable to connect due to network issues: %s',
                    self.client.phone_number,
                    e,
                )
                await self.protocol.close()
                await asleep(1)
            else:
                break
        else:
            log.warning(
                '[%s] Connection failed! Trying again...',
                self.client.phone_number,
            )
            raise ConnectionError

    async def close(self: Self, /) -> None:
        await self.protocol.close()
        log.debug('[%s] Disconnected', self.client.phone_number)

    async def send(self: Self, data: bytes, /) -> None:
        await self.protocol.send(data)

    async def recv(self: Self, /) -> Optional[bytes]:
        return await self.protocol.recv()
