from asyncio import sleep
from typing import Optional, Self

from pyrogram.connection.connection import Connection, log
from pyrogram.connection.transport import TCPAbridged


class AdBotConnection(Connection):
    async def connect(self: Self, /) -> None:
        for _ in range(self.MAX_RETRIES):
            self.protocol = self.mode(self.ipv6, self.proxy)

            try:
                log.info('Connecting...')
                await self.protocol.connect(self.address)
            except OSError as e:
                log.warning(f'Unable to connect due to network issues: {e}')
                await self.protocol.close()
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
