"""The module that provides a job for sending advertisments."""

from contextlib import suppress
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from apscheduler.job import Job
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.util import undefined
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
)
from pyrogram.errors.exceptions.bad_request_400 import (
    MessageIdInvalid,
    MsgIdInvalid,
)
from pyrogram.errors.rpc_error import RPCError
from pyrogram.types.user_and_chats.chat import Chat
from sqlalchemy.exc import IntegrityError, MissingGreenlet
from sqlalchemy.future import select
from sqlalchemy.orm import contains_eager, noload, with_parent
from sqlalchemy.sql.expression import exists, nullsfirst, or_, text, update
from sqlalchemy.sql.functions import max as sql_max
from sqlalchemy.sql.functions import now

from ..models.bots.chat_model import ChatDeactivatedCause, ChatModel
from ..models.bots.client_model import ClientModel
from ..models.bots.sent_ad_model import SentAdModel
from ..models.clients.ad_model import AdModel
from ..models.clients.bot_model import BotModel
from ..models.clients.user_model import UserModel
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
                            ),
                            folder_id=1,
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
            last_ad_chat_id: Optional[int]
            checked_empty_categories: set[int] = set()
            sent_ads_subquery = (
                select(
                    SentAdModel.ad_chat_id,
                    SentAdModel.ad_message_id,
                    SentAdModel.chat_id,
                    sql_max(SentAdModel.timestamp).label('Timestamp'),
                )
                .group_by(
                    SentAdModel.ad_chat_id,
                    SentAdModel.ad_message_id,
                    SentAdModel.chat_id,
                )
                .order_by(sql_max(SentAdModel.timestamp))
                .subquery()
                .alias()
            )
            async for ad, last_ad_chat_id in await self.storage.Session.stream(
                select(AdModel, sent_ads_subquery.c.chat_id)
                .join(sent_ads_subquery, isouter=True)
                .where(with_parent(bot, BotModel.ads) & AdModel.valid)
                .order_by(nullsfirst(sent_ads_subquery.c['Timestamp']))
                .options(noload(AdModel.owner_bot))
            ):
                if ad.category_id in checked_empty_categories:
                    continue

                _chat: Optional[Chat] = None
                sent_ad_chats_subquery = (
                    select(
                        SentAdModel.chat_id,
                        sql_max(SentAdModel.timestamp).label('Timestamp'),
                    )
                    .where(with_parent(ad, AdModel.sent_ads))
                    .group_by(SentAdModel.chat_id)
                    .order_by(sql_max(SentAdModel.timestamp))
                    .subquery()
                    .alias()
                )
                async for chat in await self.storage.Session.stream_scalars(
                    select(ChatModel)
                    .join(sent_ad_chats_subquery, isouter=True)
                    .filter(
                        ChatModel.active,
                        ad.category_id is None
                        or ChatModel.category_id == ad.category_id,
                        or_(
                            sent_ad_chats_subquery.c['Timestamp'].is_(None),
                            now() - sent_ad_chats_subquery.c['Timestamp']
                            > ChatModel.period,
                        ),
                    )
                    .order_by(
                        last_ad_chat_id is None
                        or ChatModel.id <= last_ad_chat_id,
                        nullsfirst(sent_ad_chats_subquery.c['Timestamp']),
                    )
                ):
                    try:
                        if _chat := await worker.check_chats(
                            (
                                chat.id,
                                chat.invite_link,
                                f'@{chat.username}' if chat.username else None,
                            ),
                            folder_id=1,
                        ):
                            break
                    except ValueError:
                        pass
                    except FloodWait:
                        break
                    except Unauthorized:
                        await revoke(worker)
                        break
                    except (
                        PeerIdInvalid,
                        SlowmodeWait,
                        ChannelBanned,
                        ChannelPrivate,
                        ChatAdminRequired,
                        ChatWriteForbidden,
                    ) as e:
                        chat.active = False
                        chat.deactivated_cause = (
                            ChatDeactivatedCause.from_exception(e)
                        )
                        await self.storage.Session.commit()
                    except RPCError as _:
                        continue

                if _chat is None:
                    if ad.category_id is not None:
                        checked_empty_categories.add(ad.category_id)
                    break

                try:
                    message = await worker.get_messages(
                        ad.chat_id, ad.message_id
                    )
                    sent_msg = await message.copy(_chat.id)
                    # sent_msg = await worker.send_message(
                    #     *(_chat.id, ad.chat_id, ad.message_id),
                    #     drop_author=True,
                    # )
                    sent_ad = SentAdModel(
                        ad_chat_id=ad.chat_id,
                        ad_message_id=ad.message_id,
                        chat_id=sent_msg.chat.id,
                        message_id=sent_msg.id,
                        link=sent_msg.link,
                        timestamp=sent_msg.date,
                    )
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
                    ChatRestricted,
                ) as e:
                    chat.active = False
                    chat.deactivated_cause = (
                        ChatDeactivatedCause.from_exception(e)
                    )
                    await self.storage.Session.commit()
                except Unauthorized:
                    await revoke(worker)
                except FloodWait:
                    pass
                break
