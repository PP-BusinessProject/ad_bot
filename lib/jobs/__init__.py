"""The module with jobs for the :class:`AdBotClient`."""

from .notify_subscription_end_job import NotifySubscriptionEndJob
from .sender_job import SenderJob
from .warmup_job import WarmupJob
from .checker_job import CheckerJob


class Jobs(CheckerJob, NotifySubscriptionEndJob, SenderJob, WarmupJob):
    pass
