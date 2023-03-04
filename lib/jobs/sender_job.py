'''The module that provides a job for sending advertisments.'''

from asyncio import Lock
from contextlib import suppress
from datetime import datetime, timedelta
from logging import getLogger
from time import monotonic
from typing import TYPE_CHECKING, Dict, Final, Optional, Tuple

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
from pyrogram.types.user_and_chats.chat import Chat
from sqlalchemy.exc import IntegrityError, MissingGreenlet
from sqlalchemy.orm.strategy_options import contains_eager, joinedload, noload
from sqlalchemy.orm.util import with_parent
from sqlalchemy.sql.expression import nullsfirst, or_, select, update
from sqlalchemy.sql.functions import max as sql_max
from sqlalchemy.sql.functions import now
from sqlalchemy.sql.sqltypes import Integer

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
    _sender_lock: Final[Lock] = Lock()
    _active_senders: Final[Dict[Tuple[int, int], Optional[float]]] = {}

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

    async def sender_job(self: 'AdBotClient', /) -> None:
        # Следующий за последним бот в следующее за последним обьявление в
        # следующий за последним чат для этого обьявления
        sent_ads_subquery = (
            select(
                AdChatMessageModel.ad_chat_id,
                sql_max(AdChatMessageModel.timestamp).label('timestamp'),
            )
            .group_by(AdChatMessageModel.ad_chat_id)
            .order_by(sql_max(AdChatMessageModel.timestamp))
            .subquery()
            .alias()
        )
        bots = await self.storage.Session.execute(
            select(BotModel, PeerModel)
            .join(BotModel.owner)
            .join(
                PeerModel,
                (PeerModel.session_phone_number == BotModel.phone_number)
                & (PeerModel.id == UserModel.service_id),
                isouter=True,
            )
            .join(
                sent_ads_subquery,
                sent_ads_subquery.c.ad_chat_id == UserModel.service_id,
                isouter=True,
            )
            .filter(
                BotModel.confirmed,
                BotModel.phone_number.is_not(None),
                UserModel.is_subscribed,
                UserModel.service_id.is_not(None),
            )
            .order_by(nullsfirst(sent_ads_subquery.c.timestamp))
            .options(contains_eager(BotModel.owner))
            .execution_options(populate_existing=True)
        )
        if not (bots := bots.all()):
            return log.warning('No bots found for sending!')
        async with self._sender_lock:
            bots = sorted(
                bots,
                key=lambda bot: self._active_senders.get(
                    (bot[0].owner_id, bot[0].id),
                    -1,
                )
                or float('inf'),
            )
        for bot, service_peer in bots:
            key = bot.owner_id, bot.id
            async with self._sender_lock:
                if key in self._active_senders and (
                    self._active_senders[key] is None
                ):
                    continue
                self._active_senders[key] = None

            try:
                # Sometimes expires
                bot.phone_number
            except MissingGreenlet:
                log.info('Refreshing bot #%s instance...', bot.id)
                await self.storage.Session.refresh(bot)

            # phone_numbers = await self.storage.Session.scalars(
            #     select(ClientModel.phone_number)
            #     .filter(
            #         ClientModel.valid,
            #         (ClientModel.phone_number == bot.phone_number)
            #         | ~exists(text('NULL')).where(
            #             ClientModel.phone_number == BotModel.phone_number
            #         ),
            #         exists(text('NULL'))
            #         .where(
            #             SessionModel.phone_number == ClientModel.phone_number
            #         )
            #         .where(SessionModel.user_id.is_not(None)),
            #     )
            #     .order_by(
            #         (ClientModel.phone_number != bot.phone_number).cast(Integer)
            #     )
            # )
            # if not phone_numbers:
            #     log.info(f'No clients are found for {bot}!')
            #     continue

            # for phone_number in phone_numbers.all():

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
                        folder_id=1,
                        fetch_peers=service_peer is None,
                    ):
                        log.warning(
                            '[%s] has no access to service `%s`!',
                            bot.phone_number,
                            bot.owner.service_id,
                        )
                        continue
                    await self._sender_job(worker, bot, service_peer)
                    # elif phone_number == bot.phone_number:
                    #     await self._sender_job(worker, bot)
                    #     break
                    # await worker.apply_profile_settings(bot)
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
                async with self._sender_lock:
                    self._active_senders[key] = monotonic()

                # log.info(f'{bot} assigned client with number {phone_number}!')
                # bot.phone_number = phone_number
                # await self.storage.Session.commit()
                # await self._sender_job(worker, bot)
                # break
            # else:
            #     continue
            break
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
    ) -> None:
        ad: AdModel
        last_ad_chat_id: Optional[int]
        sent_ads_subquery = (
            select(
                AdChatMessageModel.ad_chat_id,
                AdChatMessageModel.ad_message_id,
                AdChatMessageModel.chat_id,
                sql_max(AdChatMessageModel.timestamp).label('timestamp'),
            )
            .group_by(
                AdChatMessageModel.ad_chat_id,
                AdChatMessageModel.ad_message_id,
                AdChatMessageModel.chat_id,
            )
            .order_by(sql_max(AdChatMessageModel.timestamp))
            .subquery()
            .alias()
        )
        ads = await self.storage.Session.execute(
            select(AdModel, sent_ads_subquery.c.chat_id)
            .join(
                sent_ads_subquery,
                (sent_ads_subquery.c.ad_chat_id == AdModel.chat_id)
                & (sent_ads_subquery.c.ad_message_id == AdModel.message_id),
                isouter=True,
            )
            .where(with_parent(bot, BotModel.ads) & AdModel.valid)
            .order_by(nullsfirst(sent_ads_subquery.c.timestamp))
            .options(noload(AdModel.owner_bot))
        )
        if not (ads := ads.all()):
            log.warning(
                '[%s] No ads found for bot #%s!',
                bot.phone_number,
                bot.id,
            )
        for ad, last_ad_chat_id in ads:
            _chat: Optional[Chat] = None
            sent_ad_chats_subquery = (
                select(
                    AdChatMessageModel.chat_id,
                    sql_max(AdChatMessageModel.timestamp).label('timestamp'),
                )
                .group_by(AdChatMessageModel.chat_id)
                .order_by(sql_max(AdChatMessageModel.timestamp))
                .subquery()
                .alias()
            )
            sent_ad_chats_query = (
                select(AdChatModel, PeerModel)
                .join(
                    PeerModel,
                    (PeerModel.session_phone_number == bot.phone_number)
                    & (PeerModel.id == AdChatModel.chat_id),
                    isouter=True,
                )
                .join(sent_ad_chats_subquery, isouter=True)
                .where(with_parent(ad, AdModel.chats))
                .filter(
                    AdChatModel.active,
                    or_(
                        AdChatModel.slowmode_wait.is_(None),
                        now() > AdChatModel.slowmode_wait,
                    ),
                    or_(
                        sent_ad_chats_subquery.c.timestamp.is_(None),
                        now() - sent_ad_chats_subquery.c.timestamp
                        > AdChatModel.period,
                    ),
                )
                .options(joinedload(AdChatModel.chat))
            )
            ad_chats = await self.storage.Session.execute(
                sent_ad_chats_query.order_by(
                    (AdChatModel.chat_id <= last_ad_chat_id).cast(Integer),
                    nullsfirst(sent_ad_chats_subquery.c.timestamp),
                )
                if last_ad_chat_id is not None
                else sent_ad_chats_query.order_by(
                    nullsfirst(sent_ad_chats_subquery.c.timestamp),
                )
            )
            if not (ad_chats := ad_chats.all()):
                log.warning(
                    '[%s] No chats found for ad #%s of bot #%s!',
                    bot.phone_number,
                    ad.message_id,
                    bot.id,
                )
            for ad_chat, peer in ad_chats:
                try:
                    _chat = await worker.check_chats(
                        (
                            peer or ad_chat.chat.id,
                            ad_chat.chat.invite_link,
                            f'@{ad_chat.chat.username}'
                            if ad_chat.chat.username
                            else None,
                        ),
                        folder_id=1,
                        fetch_peers=peer is None,
                    )
                    if _chat is None:
                        continue
                    sent_msg = await worker.forward_messages(
                        peer or _chat.id,
                        service_peer or ad.chat_id,
                        ad.message_id,
                        drop_author=True,
                    )
                    sent_ad = AdChatMessageModel(
                        ad_chat_id=ad.chat_id,
                        ad_message_id=ad.message_id,
                        chat_id=_chat.id,
                        message_id=sent_msg.id,
                        link=sent_msg.link,
                        timestamp=sent_msg.date,
                    )
                    log.info(
                        '[%s] Sent ad #%s of bot #%s to `%s`:%s.',
                        bot.phone_number,
                        ad.message_id,
                        bot.id,
                        ad_chat.chat.title,
                        sent_msg.id,
                    )
                    with suppress(IntegrityError):
                        self.storage.Session.add(sent_ad)
                        await self.storage.Session.commit()
                except (MessageIdInvalid, MsgIdInvalid):
                    ad.corrupted = True
                    await self.storage.Session.commit()
                except SlowmodeWait as e:
                    log.warning(
                        '[%s] `%s` slowmode for %s seconds!',
                        bot.phone_number,
                        ad_chat.chat.title,
                        e.value,
                    )
                    ad_chat.slowmode_wait = datetime.now(
                        tzlocal()
                    ) + timedelta(seconds=e.value)
                    await self.storage.Session.commit()
                    continue
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
                        bot.phone_number,
                        ad_chat.chat.title,
                        e.__class__.__name__,
                    )
                    ad_chat.active = False
                    ad_chat.deactivated_cause = (
                        ChatDeactivatedCause.from_exception(e)
                    )
                    await self.storage.Session.commit()
                    continue
                # break
            else:
                continue
            # break
