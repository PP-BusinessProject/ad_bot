from contextlib import suppress
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from apscheduler.job import Job
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.util import undefined
from pyrogram.errors import RPCError, Unauthorized
from pyrogram.errors.exceptions.bad_request_400 import PeerIdInvalid
from pyrogram.types.user_and_chats.chat import Chat
from sqlalchemy.future import select
from sqlalchemy.sql.expression import exists, text, update

from ..models.bots.chat_model import ChatModel
from ..models.bots.client_model import ClientModel
from ..models.sessions.session_model import SessionModel
from ..utils.pyrogram import auto_init, get_input_peer_id

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient


class WarmupJob(object):
    def warmup_job_init(
        self: 'AdBotClient',
        /,
        interval: timedelta,
        *,
        run_now: bool = False,
    ) -> Job:
        if (job := self.scheduler.get_job('warmup_job')) is not None:
            return job
        return self.scheduler.add_job(
            self.storage.scoped(self.warmup_job),
            IntervalTrigger(seconds=interval.total_seconds()),
            id='warmup_job',
            max_instances=1,
            replace_existing=False,
            next_run_time=datetime.now() if run_now else undefined,
        )

    async def warmup_job(self: 'AdBotClient', /) -> None:
        """
        Process the job that sends every `ad` from `service_id`.

        The ads are send in order one by one.

        Steps:
        1. Process all the dependencies.
        2. Get the next chat for sending from the `SENDER_CHATS`.
            1. Check the active status of the each chat.
            2. Check category of the each chat.
            3. Get the chat with the biggest last sent time.
            4. Set the chat's last sent time to current time.
        3. Try to send an `ad` to the found chat.

        Returns:
            Nothing.
        """
        sender_chats: list[ChatModel] = await self.storage.Session.scalars(
            select(ChatModel).where(ChatModel.valid)
        )
        if not (sender_chats := sender_chats.all()):
            return

        phone_numbers = await self.storage.Session.scalars(
            select(ClientModel.phone_number).filter(
                ClientModel.warmup,
                ~ClientModel.invalid,
                ~ClientModel.active,
                exists(text('NULL'))
                .where(SessionModel.phone_number == ClientModel.phone_number)
                .where(SessionModel.user_id.is_not(None)),
            )
        )
        for phone_number in phone_numbers.all():
            async with auto_init(self.get_worker(phone_number)) as worker:
                try:
                    chats: dict[int, Chat] = {
                        chat.id: chat
                        async for chat in worker.iter_check_chats(
                            (
                                chat.id,
                                chat.invite_link,
                                f'@{chat.username}' if chat.username else None,
                            )
                            for chat in sender_chats
                        )
                    }
                except Unauthorized:
                    try:
                        await self.storage.Session.execute(
                            update(ClientModel)
                            .values(warmup=False)
                            .filter_by(phone_number=phone_number)
                        )
                        await self.storage.Session.commit()
                    finally:
                        await worker.storage.delete()
                    continue
                except RPCError:
                    continue

                folder = await worker.get_folder_by_title('SenderChats')
                folder_ids: set[int] = {
                    peer_id
                    for peer in folder.include_peers
                    if (peer_id := get_input_peer_id(peer)) is not None
                }
                folder.include_peers = [
                    await worker.resolve_peer(chat_id)
                    for chat_id, chat in chats.items()
                    if chat is not None
                ]
                with suppress(PeerIdInvalid):
                    _ = await worker.resolve_peer(await self.storage.user_id())
                    folder.include_peers.insert(0, _)

                if folder_ids != {
                    peer_id
                    for peer in folder.include_peers
                    if (peer_id := get_input_peer_id(peer)) is not None
                }:
                    await worker.update_folder(folder)
