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
from pyrogram.types.user_and_chats.chat import Chat
from sqlalchemy.exc import IntegrityError, MissingGreenlet
from sqlalchemy.orm.strategy_options import contains_eager, joinedload, noload
from sqlalchemy.orm.util import with_parent
from sqlalchemy.sql.expression import exists, or_, select, update
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
            )
            .order_by(BotModel.last_sent_at.nullsfirst(), BotModel.created_at)
            .options(contains_eager(BotModel.owner))
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
                    if not await self._sender_job(worker, bot, service_peer):
                        continue
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

                # log.info(f'{bot} assigned client with number {phone_number}!')
                # bot.phone_number = phone_number
                # await self.storage.Session.commit()
                # await self._sender_job(worker, bot)
                # break
            # else:
            #     continue
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
            .where(with_parent(bot, BotModel.ads) & AdModel.valid)
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
            try:
                ad_chats = await self.storage.Session.execute(
                    select(AdChatModel, PeerModel)
                    .join(
                        PeerModel,
                        (PeerModel.session_phone_number == bot.phone_number)
                        & (PeerModel.id == AdChatModel.chat_id),
                        isouter=True,
                    )
                    .where(with_parent(ad, AdModel.chats))
                    .filter(
                        AdChatModel.active,
                        or_(
                            AdChatModel.slowmode_wait.is_(None),
                            now() > AdChatModel.slowmode_wait,
                        ),
                        or_(
                            AdChatModel.last_sent_at.is_(None),
                            now() - AdChatModel.last_sent_at
                            > AdChatModel.period,
                        ),
                    )
                    .order_by(
                        AdChatModel.last_sent_at.nullsfirst(),
                        AdChatModel.created_at,
                    )
                    .options(joinedload(AdChatModel.chat))
                )
                if not (ad_chats := ad_chats.all()):
                    log.warning(
                        '[%s] No chats found for ad #%s of bot #%s!',
                        bot.phone_number,
                        ad.message_id,
                        bot.id,
                    )
                    continue
                for ad_chat, chat_peer in ad_chats:
                    await self._sender_chat_job(
                        worker, ad_chat, service_peer, chat_peer
                    )
            finally:
                log.info(
                    '[%s] Finished sending ad #%s of bot #%s%s!',
                    bot.phone_number,
                    ad.message_id,
                    bot.id,
                    ' in %s chat%s'
                    % (len(ad_chats), 's' if len(ad_chats) > 1 else '')
                    if isinstance(ad_chats, Iterable) and ad_chats
                    else '',
                )
                ad.last_sent_at = datetime.now(tzlocal())
                await self.storage.Session.commit()
        return True

    async def _sender_chat_job(
        self: 'AdBotClient',
        worker: 'AdBotClient',
        ad_chat: AdChatModel,
        /,
        service_peer: Optional[PeerModel] = None,
        chat_peer: Optional[PeerModel] = None,
    ) -> bool:
        try:
            _chat = await worker.check_chats(
                (
                    chat_peer or ad_chat.chat.id,
                    ad_chat.chat.invite_link,
                    f'@{ad_chat.chat.username}'
                    if ad_chat.chat.username
                    else None,
                ),
                folder_id=1,
                fetch_peers=chat_peer is None,
            )
            if _chat is None:
                return False
            sent_msg = await worker.forward_messages(
                chat_peer or _chat.id,
                service_peer or ad_chat.ad_chat_id,
                ad_chat.ad_message_id,
                drop_author=True,
            )
            sent_ad = AdChatMessageModel(
                ad_chat_id=ad_chat.ad_chat_id,
                ad_message_id=ad_chat.ad_message_id,
                chat_id=_chat.id,
                message_id=sent_msg.id,
                link=sent_msg.link,
                timestamp=sent_msg.date,
            )
            log.info(
                '[%s] Sent ad #%s of bot #%s to `%s`:%s.',
                ad_chat.ad.owner_bot.phone_number,
                ad_chat.ad_message_id,
                ad_chat.ad.owner_bot.id,
                ad_chat.chat.title,
                sent_msg.id,
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
