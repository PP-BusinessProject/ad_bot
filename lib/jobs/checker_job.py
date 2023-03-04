from asyncio import Lock
from contextlib import suppress
from datetime import datetime, timedelta
from logging import getLogger
from typing import TYPE_CHECKING, Dict, Final, Set, Tuple

from apscheduler.job import Job
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.util import undefined
from pyrogram.enums.chat_type import ChatType
from pyrogram.errors import FloodWait, Unauthorized
from pyrogram.errors.rpc_error import RPCError
from pyrogram.types.user_and_chats.dialog import Dialog
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.orm import contains_eager
from sqlalchemy.sql.expression import nullsfirst, select, update
from sqlalchemy.sql.functions import max as sql_max

from ..models.bots.client_model import ClientModel
from ..models.bots.reply_model import ReplyModel
from ..models.clients.bot_model import BotModel
from ..models.clients.user_model import UserModel

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient

log = getLogger(__name__)


class CheckerJob(object):
    _checker_lock: Final[Lock] = Lock()
    _active_checkers: Final[Set[Tuple[int, int]]] = set()

    def checker_job_init(
        self: 'AdBotClient',
        /,
        interval: timedelta,
        *,
        run_now: bool = False,
    ) -> Job:
        if (job := self.scheduler.get_job('checker_job')) is not None:
            return job
        return self.scheduler.add_job(
            self.storage.scoped(self.checker_job),
            IntervalTrigger(seconds=interval.total_seconds()),
            id='checker_job',
            max_instances=10,
            replace_existing=False,
            next_run_time=datetime.now() if run_now else undefined,
        )

    async def checker_job(self: 'AdBotClient', /) -> None:
        replies_subquery = (
            select(
                ReplyModel.client_phone_number,
                sql_max(ReplyModel.created_at).label('created_at'),
            )
            .group_by(ReplyModel.client_phone_number)
            .order_by(sql_max(ReplyModel.created_at))
            .subquery()
            .alias()
        )
        bots = await self.storage.Session.scalars(
            select(BotModel)
            .join(BotModel.owner)
            .join(
                replies_subquery,
                replies_subquery.c.client_phone_number
                == BotModel.phone_number,
                isouter=True,
            )
            .filter(
                BotModel.confirmed,
                BotModel.phone_number.is_not(None),
                UserModel.is_subscribed,
                UserModel.service_id.is_not(None),
            )
            .order_by(nullsfirst(replies_subquery.c.created_at))
            .options(contains_eager(BotModel.owner))
            .execution_options(populate_existing=True)
        )
        if not (bots := bots.all()):
            return log.warning('No bots found for checking!')
        for bot in bots:
            key = bot.owner_id, bot.id
            async with self._checker_lock:
                if key in self._active_checkers and (
                    self._active_checkers[key] is None
                ):
                    continue
                self._active_checkers[key] = None

            try:
                # Sometimes expires
                bot.phone_number
            except MissingGreenlet:
                log.info('Refreshing bot #%s instance...', bot.id)
                await self.storage.Session.refresh(bot)

            replied_chat_ids = set(
                await self.storage.Session.scalars(
                    select(ReplyModel.chat_id)
                    .where(ReplyModel.client_phone_number == bot.phone_number)
                    .distinct()
                )
            )
            chats_to_reply: Dict[int, Dialog] = {}
            try:
                async with self.worker(bot.phone_number) as worker:
                    if not await worker.check_chats(
                        (bot.owner.service_id, bot.owner.service_invite)
                    ):
                        log.warning(
                            '[%s] Client has no service access to bot #%s:%s!',
                            bot.phone_number,
                            bot.owner_id,
                            bot.id,
                        )
                        continue

                    async for dialog in worker.iter_dialogs(
                        exclude_pinned=True, folder_id=0
                    ):
                        if dialog.chat.id in {42777, bot.forward_to_id}:
                            pass
                        elif dialog.chat.type == ChatType.PRIVATE and (
                            dialog.chat.id not in replied_chat_ids
                        ):
                            chats_to_reply[dialog.chat.id] = dialog
                    if not chats_to_reply:
                        continue

                    for dialog in chats_to_reply.values():
                        reply_message: None = None
                        with suppress(RPCError):
                            reply_message = await self.forward_messages(
                                getattr(dialog, 'peer', dialog.chat.id),
                                bot.owner.service_id,
                                bot.reply_message_id,
                                drop_author=True,
                            )
                        self.storage.Session.add(
                            ReplyModel(
                                client_phone_number=bot.phone_number,
                                chat_id=dialog.chat.id,
                                reply_message_id=reply_message.id
                                if reply_message is not None
                                else None,
                                first_name=dialog.chat.first_name,
                                last_name=dialog.chat.last_name,
                                username=dialog.chat.username,
                            )
                        )
                        await self.storage.Session.commit()
            except Unauthorized as _:
                try:
                    if bot.phone_number is not None:
                        await self.storage.Session.execute(
                            update(ClientModel)
                            .values(active=False)
                            .filter_by(phone_number=bot.phone_number)
                        )
                        await self.storage.Session.commit()
                finally:
                    async with self.worker(
                        bot.phone_number, start=False, stop=False
                    ) as worker:
                        await worker.storage.delete()
                continue
            except FloodWait as e:
                log.warning(
                    '[%s] raised FloodWait for %s seconds!',
                    bot.phone_number,
                    e.value,
                )
                continue
            except OSError:
                async with self.worker(
                    bot.phone_number, start=False, stop=True
                ):
                    continue
            finally:
                log.info(
                    '[%s] Finished checking chats for bot #%s!',
                    bot.phone_number,
                    bot.id,
                )
                async with self._checker_lock:
                    with suppress(KeyError):
                        self._active_checkers.remove(key)
