from asyncio import sleep
from typing import Optional

from pyrogram.connection.connection import Connection, log
from typing_extensions import Self


class AdBotConnection(Connection):
    async def connect(self: Self, /) -> None:
        for _ in range(self.MAX_RETRIES):
            self.protocol = self.mode(self.ipv6, self.proxy)

            try:
                log.info('Connecting...')
                await self.protocol.connect(self.address)
            except OSError as e:
                log.warning(f'Unable to connect due to network issues: {e}')
                self.protocol.close()
                await sleep(1)
            else:
                log.info(
                    'Connected! {} DC{}{} - IPv{} - {}'.format(
                        'Test' if self.test_mode else 'Production',
                        self.dc_id,
                        ' (media)' if self.media else '',
                        '6' if self.ipv6 else '4',
                        self.mode.__name__,
                    )
                )
                break
        else:
            log.warning('Connection failed! Trying again...')
            raise TimeoutError

    def close(self: Self, /) -> None:
        self.protocol.close()
        log.info('Disconnected')

    async def send(self: Self, data: bytes, /) -> None:
        return await self.protocol.send(data)

    async def recv(self: Self, /) -> Optional[bytes]:
        return await self.protocol.recv()
