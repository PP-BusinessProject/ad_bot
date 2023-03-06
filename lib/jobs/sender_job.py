'''The module that provides a job for sending advertisments.'''

from asyncio import Lock
from contextlib import suppress
from datetime import datetime, timedelta
from logging import getLogger
from typing import TYPE_CHECKING, ClassVar, Iterable, Optional, Set, Tuple

from apscheduler.job import Job
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.util import undefined
from dateutil.tz.tz import tzlocal
from pyrogram.errors import (
    ChannelBanned,
    ChannelPrivate,
    ChatAdminRequired,
    ChatRestricted,
    ChatWriteForbidden,
    FloodWait,
    PeerIdInvalid,
    SlowmodeWait,
    Unauthorized,
    UserBannedInChannel,
)
from pyrogram.errors.exceptions.bad_request_400 import (
    MessageIdInvalid,
    MsgIdInvalid,
)
from pyrogram.utils import get_channel_id
from sqlalchemy.exc import IntegrityError, MissingGreenlet
from sqlalchemy.orm.strategy_options import contains_eager, joinedload
from sqlalchemy.orm.util import with_parent
from sqlalchemy.sql.expression import or_, select, update
from sqlalchemy.sql.functions import count
from sqlalchemy.sql.functions import max as sql_max
from sqlalchemy.sql.functions import now

from ..models.bots.client_model import ClientModel
from ..models.clients.ad_chat_message_model import AdChatMessageModel
from ..models.clients.ad_chat_model import AdChatModel, ChatDeactivatedCause
from ..models.clients.ad_model import AdModel
from ..models.clients.bot_model import BotModel
from ..models.clients.user_model import UserModel
from ..models.sessions.peer_model import PeerModel

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient

log = getLogger(__name__)


class SenderJob(object):
    _sender_lock: ClassVar[Lock] = Lock()
    _active_senders: ClassVar[Set[Tuple[int, int]]] = set()

    def sender_job_init(
        self: 'AdBotClient',
        /,
        interval: timedelta,
        *,
        run_now: bool = False,
    ) -> Job:
        if (job := self.scheduler.get_job('sender_job')) is not None:
            return job
        return self.scheduler.add_job(
            self.storage.scoped(self.sender_job),
            IntervalTrigger(seconds=interval.total_seconds()),
            id='sender_job',
            max_instances=10,
            replace_existing=False,
            next_run_time=datetime.now() if run_now else undefined,
        )

    async def sender_job(self: 'AdBotClient', /) -> bool:
        # Следующий за последним бот в следующее за последним обьявление в
        # следующий за последним чат для этого обьявления
        bots = await self.storage.Session.execute(
            select(BotModel, PeerModel)
            .join(BotModel.owner)
            .join(BotModel.sender_client)
            .join(
                PeerModel,
                (PeerModel.session_phone_number == BotModel.phone_number)
                & (PeerModel.id == UserModel.service_id),
                isouter=True,
            )
            .filter(
                UserModel.is_subscribed,
                UserModel.service_id.is_not(None),
                BotModel.confirmed,
                BotModel.phone_number.is_not(None),
                ClientModel.active,
                ClientModel.restricted.is_(None) | ~ClientModel.restricted,
                ClientModel.deleted.is_(None) | ~ClientModel.deleted,
            )
            .order_by(BotModel.last_sent_at.nullsfirst(), BotModel.created_at)
            .options(
                contains_eager(BotModel.owner),
                contains_eager(BotModel.sender_client),
            )
            .execution_options(populate_existing=True)
        )
        if not (bots := bots.all()):
            log.warning('No bots found for sending!')
            return False
        for bot, service_peer in bots:
            async with (cls := self.__class__)._sender_lock:
                if (key := (bot.owner_id, bot.id)) in cls._active_senders:
                    continue
                cls._active_senders.add(key)

            try:
                # Sometimes expires
                bot.phone_number
            except MissingGreenlet:
                log.info('Refreshing bot #%s instance...', bot.id)
                await self.storage.Session.refresh(bot)

            try:
                async with self.worker(bot.phone_number) as worker:
                    if bot.owner.service_invite is None:
                        log.info(
                            '[%s] Exporting chat invite for bot #%s...',
                            bot.phone_number,
                            bot.id,
                        )
                        invite_link = await self.export_chat_invite_link(
                            bot.owner.service_id
                        )
                        bot.owner.service_invite = invite_link.invite_link
                        await self.storage.Session.commit()

                    if not await worker.check_chats(
                        (
                            service_peer or bot.owner.service_id,
                            bot.owner.service_invite,
                        ),
                        fetch_peers=service_peer is None,
                    ):
                        log.warning(
                            '[%s] has no access to service `%s`!',
                            bot.phone_number,
                            bot.owner.service_id,
                        )
                        continue
                    if not await self._sender_job(worker, bot, service_peer):
                        continue
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
                break
            except OSError as _:
                async with self.worker(
                    bot.phone_number, start=False, stop=True
                ):
                    continue
            finally:
                log.info(
                    '[%s] Finished sending ads for bot #%s!',
                    bot.phone_number,
                    bot.id,
                )
                bot.last_sent_at = datetime.now(tzlocal())
                await self.storage.Session.commit()
                async with cls._sender_lock:
                    cls._active_senders.remove(key)
            return True
        else:
            if len(bots) > 1:
                log.info('All %s bots are already working!', len(bots))
            else:
                log.info('Bot is already working!')

    async def _sender_job(
        self: 'AdBotClient',
        worker: 'AdBotClient',
        bot: BotModel,
        /,
        service_peer: Optional[PeerModel] = None,
    ) -> bool:
        ads = await self.storage.Session.scalars(
            select(AdModel)
            .filter(with_parent(bot, BotModel.ads), AdModel.valid)
            .order_by(AdModel.last_sent_at.nullsfirst(), AdModel.created_at)
        )
        if not (ads := ads.all()):
            log.warning(
                '[%s] No ads found for bot #%s!',
                bot.phone_number,
                bot.id,
            )
            return False
        for ad in ads:
            ad_chats = None
            successful_chats = 0
            try:
                ad_chats_messages = (
                    select(
                        AdChatMessageModel.ad_chat_id,
                        AdChatMessageModel.ad_message_id,
                        AdChatMessageModel.chat_id,
                        count().label('scheduled_count'),
                        sql_max(AdChatMessageModel.timestamp).label(
                            'last_sent_at'
                        ),
                    )
                    .filter(
                        AdChatMessageModel.ad_chat_id == ad.chat_id,
                        AdChatMessageModel.ad_message_id == ad.message_id,
                        AdChatMessageModel.scheduled,
                    )
                    .group_by(
                        AdChatMessageModel.ad_chat_id,
                        AdChatMessageModel.ad_message_id,
                        AdChatMessageModel.chat_id,
                    )
                    .subquery()
                )
                ad_chats = await self.storage.Session.execute(
                    select(
                        AdChatModel,
                        PeerModel,
                        ad_chats_messages.c.scheduled_count,
                        ad_chats_messages.c.last_sent_at,
                    )
                    .join(
                        ad_chats_messages,
                        (
                            AdChatModel.ad_chat_id
                            == ad_chats_messages.c.ad_chat_id
                        )
                        & (
                            AdChatModel.ad_message_id
                            == ad_chats_messages.c.ad_message_id
                        )
                        & (AdChatModel.chat_id == ad_chats_messages.c.chat_id),
                        isouter=True,
                    )
                    .join(
                        PeerModel,
                        (PeerModel.session_phone_number == bot.phone_number)
                        & (PeerModel.id == AdChatModel.chat_id),
                        isouter=True,
                    )
                    .where(
                        with_parent(ad, AdModel.chats),
                        AdChatModel.active,
                        or_(
                            ad_chats_messages.c.scheduled_count.is_(None),
                            ad_chats_messages.c.scheduled_count
                            < AdChatModel.max_scheduled_count,
                        ),
                        or_(
                            AdChatModel.slowmode_wait.is_(None),
                            now() > AdChatModel.slowmode_wait,
                        ),
                        # or_(
                        #     AdChatModel.last_sent_at.is_(None),
                        #     now() - AdChatModel.last_sent_at
                        #     > AdChatModel.period,
                        # ),
                    )
                    .order_by(
                        ad_chats_messages.c.last_sent_at.nullsfirst(),
                        AdChatModel.created_at,
                    )
                    .options(joinedload(AdChatModel.chat))
                )
                if not (ad_chats := list(ad_chats.all())):
                    log.warning(
                        '[%s] No chats found for ad #%s of bot #%s!',
                        bot.phone_number,
                        ad.message_id,
                        bot.id,
                    )
                    continue
                for (
                    ad_chat,
                    chat_peer,
                    scheduled_count,
                    last_sent_at,
                ) in ad_chats:
                    _now = last_sent_at or datetime.now(tzlocal())
                    for index in range(
                        1, ad_chat.max_scheduled_count - (scheduled_count or 0)
                    ):
                        if not await self._sender_chat_job(
                            worker,
                            ad_chat,
                            schedule_date=_now + ad_chat.period * index,
                            service_peer=service_peer,
                            chat_peer=chat_peer,
                        ):
                            log.warning(
                                '[%s] Chat `%s` is not accessible for sending '
                                'an ad #%s of bot #%s!',
                                bot.phone_number,
                                ad_chat.chat.title,
                                ad.message_id,
                                bot.id,
                            )
                            break
                    else:
                        successful_chats += 1
            finally:
                log.info(
                    '[%s] Finished sending ad #%s of bot #%s '
                    'in %s chat%s (%s error%s)!',
                    bot.phone_number,
                    ad.message_id,
                    bot.id,
                    successful_chats,
                    '' if successful_chats == 1 else 's',
                    len(ad_chats) - successful_chats,
                    '' if len(ad_chats) - successful_chats == 1 else 's',
                )
                ad.last_sent_at = datetime.now(tzlocal())
                await self.storage.Session.commit()
        return True

    async def _sender_chat_job(
        self: 'AdBotClient',
        worker: 'AdBotClient',
        ad_chat: Iterable[AdChatModel],
        /,
        schedule_date: Optional[datetime] = None,
        service_peer: Optional[PeerModel] = None,
        chat_peer: Optional[PeerModel] = None,
    ) -> bool:
        try:
            while True:
                try:
                    sent_msg = await worker.forward_messages(
                        chat_peer or ad_chat.chat_id,
                        service_peer or ad_chat.ad_chat_id,
                        ad_chat.ad_message_id,
                        drop_author=True,
                        schedule_date=schedule_date.timestamp().__ceil__()
                        if schedule_date is not None
                        else None,
                    )
                except PeerIdInvalid:
                    if not (ad_chat.chat.invite_link or ad_chat.chat.username):
                        raise
                    await worker.join_chat(
                        ad_chat.chat.invite_link or f'@{ad_chat.chat.username}'
                    )
                    continue
                else:
                    break
            sent_ad = AdChatMessageModel(
                ad_chat_id=ad_chat.ad_chat_id,
                ad_message_id=ad_chat.ad_message_id,
                chat_id=ad_chat.chat_id,
                message_id=sent_msg.id,
                link=sent_msg.link
                if sent_msg.chat is not None
                else f'https://t.me/c/%s/{sent_msg.id}'
                % (ad_chat.username or get_channel_id(ad_chat.chat_id)),
                timestamp=sent_msg.date
                or schedule_date
                or datetime.now(tzlocal()),
            )
            log.info(
                '[%s] %s ad #%s of bot #%s to `%s`:%s%s.',
                ad_chat.ad.owner_bot.phone_number,
                'Sent' if schedule_date is None else 'Scheduled',
                ad_chat.ad_message_id,
                ad_chat.ad.owner_bot.id,
                ad_chat.chat.title,
                sent_msg.id,
                ' at %s' % schedule_date if schedule_date is not None else '',
            )
            self.storage.Session.add(sent_ad)
            return True
        except (MessageIdInvalid, MsgIdInvalid):
            ad_chat.ad.corrupted = True
        except SlowmodeWait as e:
            log.warning(
                '[%s] `%s` slowmode for %s seconds!',
                ad_chat.ad.owner_bot.phone_number,
                ad_chat.chat.title,
                e.value,
            )
            ad_chat.slowmode_wait = datetime.now(tzlocal()) + timedelta(
                seconds=e.value
            )
        except (
            PeerIdInvalid,
            ChannelBanned,
            ChannelPrivate,
            ChatAdminRequired,
            ChatWriteForbidden,
            ChatRestricted,
            UserBannedInChannel,
        ) as e:
            log.warning(
                '[%s] `%s` banned with `%s`!',
                ad_chat.ad.owner_bot.phone_number,
                ad_chat.chat.title,
                e.__class__.__name__,
            )
            ad_chat.active = False
            ad_chat.deactivated_cause = ChatDeactivatedCause.from_exception(e)
        finally:
            with suppress(IntegrityError):
                ad_chat.last_sent_at = datetime.now(tzlocal())
                await self.storage.Session.commit()
        return False
