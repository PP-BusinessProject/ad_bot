"""The module that provides a job for sending advertisments."""

from contextlib import suppress
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from apscheduler.job import Job
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.util import undefined
from dateutil.tz.tz import tzlocal
from pyrogram.errors import (
    ChannelBanned,
    ChannelPrivate,
    ChatAdminRequired,
    ChatWriteForbidden,
    FloodWait,
    PeerIdInvalid,
    SlowmodeWait,
    Unauthorized,
)
from pyrogram.errors.exceptions.bad_request_400 import (
    MessageIdInvalid,
    MsgIdInvalid,
)
from sqlalchemy.exc import IntegrityError, MissingGreenlet
from sqlalchemy.future import select
from sqlalchemy.orm import contains_eager, selectinload, with_parent
from sqlalchemy.sql.expression import exists, or_, text, update
from sqlalchemy.sql.functions import now

from ..models.bots.chat_model import ChatDeactivatedCause, ChatModel
from ..models.bots.client_model import ClientModel
from ..models.bots.sent_ad_model import SentAdModel
from ..models.clients.ad_model import AdModel
from ..models.clients.bot_model import BotModel
from ..models.clients.user_model import UserModel
from ..models.misc.category_model import CategoryModel
from ..models.sessions.session_model import SessionModel
from ..utils.pyrogram import auto_init

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient


class SenderJob(object):
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
            max_instances=1,
            replace_existing=False,
            next_run_time=datetime.now() if run_now else undefined,
        )

    async def sender_job(self: 'AdBotClient', /) -> None:
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
        # TODO Следующее за последним обьявление в следующий за последним чат
        # для этого обьявления
        bot: BotModel
        async for bot in await self.storage.Session.stream_scalars(
            select(BotModel)
            .join(BotModel.owner)
            .filter(
                BotModel.confirmed,
                UserModel.is_subscribed,
                UserModel.service_id.is_not(None),
            )
            .options(contains_eager(BotModel.owner))
            .execution_options(populate_existing=True)
        ):

            async def revoke(worker: 'AdBotClient', /) -> None:
                try:
                    if bot.phone_number is not None:
                        await self.storage.Session.execute(
                            update(ClientModel)
                            .values(active=False)
                            .filter_by(phone_number=bot.phone_number)
                        )
                        await self.storage.Session.commit()
                finally:
                    async with auto_init(worker, start=False, stop=True):
                        await worker.storage.delete()

            try:
                # Sometimes expires
                bot.phone_number
            except MissingGreenlet:
                await self.storage.Session.refresh(bot)

            phone_number: int
            async for phone_number in (
                await self.storage.Session.stream_scalars(
                    select(ClientModel.phone_number)
                    .filter(
                        ClientModel.valid,
                        (ClientModel.phone_number == bot.phone_number)
                        | ~exists(text('NULL')).where(
                            ClientModel.phone_number == BotModel.phone_number
                        ),
                        exists(text('NULL'))
                        .where(
                            SessionModel.phone_number
                            == ClientModel.phone_number
                        )
                        .where(SessionModel.user_id.is_not(None)),
                    )
                    .order_by(ClientModel.phone_number != bot.phone_number)
                )
            ):
                worker = self.get_worker(phone_number)
                async with auto_init(worker, stop=False):
                    try:
                        if not await worker.check_chats(
                            (
                                bot.owner.service_id,
                                bot.owner.service_invite,
                            )
                        ):
                            continue
                        elif phone_number == bot.phone_number:
                            break
                        await worker.apply_profile_settings(bot)
                    except Unauthorized:
                        await revoke(worker)
                        continue
                    except FloodWait:
                        continue

                    bot.phone_number = phone_number
                    await self.storage.Session.commit()
                    break

            else:
                continue

            if bot.owner.service_invite is None:
                invite_link = await self.export_chat_invite_link(
                    bot.owner.service_id
                )
                bot.owner.service_invite = invite_link.invite_link
                await self.storage.Session.commit()

            ad: AdModel
            checked_empty_categories: set[CategoryModel] = set()
            async for ad in await self.storage.Session.stream_scalars(
                select(AdModel)
                .where(with_parent(bot, BotModel.ads) & AdModel.valid)
                .order_by(
                    AdModel.message_id
                    <= select(SentAdModel.ad_message_id)
                    .join(SentAdModel.ad)
                    .where(with_parent(bot, BotModel.ads) & AdModel.valid)
                    .order_by(SentAdModel.timestamp.desc())
                    .limit(1)
                    .scalar_subquery()
                )
                .options(
                    selectinload(AdModel.owner_bot).selectinload(
                        BotModel.owner
                    )
                )
            ):
                if ad.category in checked_empty_categories:
                    continue
                chat_query = (
                    select(ChatModel)
                    .join(SentAdModel, isouter=True)
                    .filter(
                        ChatModel.valid,
                        or_(
                            SentAdModel.ad_chat_id.is_(None),
                            SentAdModel.ad_message_id.is_(None),
                            with_parent(ad, AdModel.sent_ads),
                        ),
                        or_(
                            SentAdModel.timestamp.is_(None),
                            now() - SentAdModel.timestamp > ChatModel.period,
                        ),
                    )
                    .order_by(
                        ChatModel.id
                        <= select(SentAdModel.chat_id)
                        .where(with_parent(ad, AdModel.sent_ads))
                        .order_by(SentAdModel.timestamp.desc())
                        .limit(1)
                        .scalar_subquery(),
                        SentAdModel.timestamp,
                    )
                )
                if ad.category is not None:
                    chat_query = chat_query.filter_by(category=ad.category)

                try:
                    async for chat in worker.iter_check_chats(
                        (
                            chat.id,
                            chat.invite_link,
                            f'@{chat.username}' if chat.username else None,
                        )
                        async for chat in (
                            await self.storage.Session.stream_scalars(
                                chat_query
                            )
                        )
                    ):
                        if chat is not None:
                            break
                    else:
                        if ad.category is None:
                            break
                        checked_empty_categories.add(ad.category)
                        continue
                except ValueError:
                    continue
                except FloodWait:
                    break
                except Unauthorized:
                    await revoke(worker)
                    break

                try:
                    sent_msg = await worker.forward_messages(
                        *(chat.id, ad.chat_id, ad.message_id),
                        drop_author=True,
                    )
                    sent_ad = SentAdModel(
                        ad_chat_id=ad.chat_id,
                        ad_message_id=ad.message_id,
                        chat_id=sent_msg.chat.id,
                        message_id=sent_msg.id,
                        link=sent_msg.link,
                        timestamp=sent_msg.date.replace(tzinfo=tzlocal()),
                    )
                    # print(
                    #     f'{sent_ad.ad_chat_id}:{sent_ad.ad_message_id}',
                    #     f'{chat.title}',
                    #     sep=' => ',
                    # )
                    with suppress(IntegrityError):
                        self.storage.Session.add(sent_ad)
                        await self.storage.Session.commit()
                except (MessageIdInvalid, MsgIdInvalid):
                    ad.corrupted = True
                    await self.storage.Session.commit()
                except (
                    PeerIdInvalid,
                    SlowmodeWait,
                    ChannelBanned,
                    ChannelPrivate,
                    ChatAdminRequired,
                    ChatWriteForbidden,
                ) as e:
                    deactivated = ChatDeactivatedCause.from_exception(e)
                    values = dict(active=False, deactivated_cause=deactivated)
                    await self.storage.Session.execute(
                        update(ChatModel, ChatModel.id == chat.id, values)
                    )
                    await self.storage.Session.commit()
                except Unauthorized:
                    await revoke(worker)
                except FloodWait:
                    pass
                break