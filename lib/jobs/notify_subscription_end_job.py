from contextlib import suppress
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from apscheduler.job import Job
from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.cron import CronTrigger
from dateutil.tz.tz import tzlocal
from pyrogram.types.messages_and_media.message import Message

from ..models.clients.user_model import UserModel

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient


class NotifySubscriptionEndJob(object):
    def notify_subscription_end_job_init(
        self: 'AdBotClient',
        user: UserModel,
        /,
        notify_before: timedelta,
    ) -> Optional[Job]:
        job_id = f'notify_subscription_end_job:{user.id}'
        if user.subscription_from is None or user.subscription_period is None:
            with suppress(JobLookupError):
                self.scheduler.remove_job(job_id)
            return None
        elif user.subscription_from.tzinfo is None:
            user.subscription_from = user.subscription_from.astimezone(
                tz=tzlocal()
            )

        end = user.subscription_from + user.subscription_period - notify_before
        if end > datetime.now(tzlocal()):
            return self.scheduler.add_job(
                self.storage.scoped(self.notify_subscription_end_job),
                CronTrigger(
                    *(end.year, end.month, end.day),
                    hour=end.hour,
                    minute=end.minute,
                    second=end.second,
                    jitter=min(
                        notify_before.total_seconds() / 2,
                        timedelta(minutes=30).total_seconds(),
                    ),
                ),
                args=(user,),
                id=job_id,
                max_instances=1,
                replace_existing=True,
            )

    async def notify_subscription_end_job(
        self: 'AdBotClient',
        user: UserModel,
        /,
    ) -> Message:
        subscription_end = user.subscription_from + user.subscription_period
        time_left = datetime.now(tzlocal()) - subscription_end
        time_left_text = self.morph.timedelta(time_left, case='gent')
        _text = f'Ваша подписка истекает через {time_left_text}.'
        return await self.send_message(user.id, _text)
