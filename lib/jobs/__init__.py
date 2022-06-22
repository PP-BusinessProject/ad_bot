"""The module with jobs for the :class:`AdBotClient`."""

from .notify_subscription_end_job import NotifySubscriptionEndJob
from .sender_job import SenderJob
from .warmup_job import WarmupJob


class Jobs(NotifySubscriptionEndJob, SenderJob, WarmupJob):
    pass
