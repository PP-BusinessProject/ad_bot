from datetime import timedelta
from typing import Final, Literal

from sqlalchemy.sql.schema import CheckConstraint, Column
from sqlalchemy.sql.sqltypes import Boolean, Interval, SmallInteger

from ..base_interface import Base


class SettingsModel(Base):
    __tablename__: Final[str] = 'Settings'

    id: Final[Column[Literal[True]]] = Column(
        'Id',
        Boolean(create_constraint=True),
        CheckConstraint('"Id"'),
        primary_key=True,
        default=True,
        key='id',
    )
    page_list_size: Final[Column[int]] = Column(
        'PageListSize',
        SmallInteger,
        nullable=False,
        default=10,
        key='page_list_size',
    )
    bots_per_user: Final[Column[int]] = Column(
        'BotsPerUser',
        SmallInteger,
        nullable=False,
        default=3,
        key='bots_per_user',
    )
    ads_per_bot: Final[Column[int]] = Column(
        'AdsPerBot',
        SmallInteger,
        nullable=False,
        default=5,
        key='ads_per_bot',
    )
    send_interval: Final[Column[timedelta]] = Column(
        'SendInterval',
        Interval(second_precision=True),
        nullable=False,
        default=timedelta(seconds=10),
        key='send_interval',
    )
    warmup_interval: Final[Column[timedelta]] = Column(
        'WarmupInterval',
        Interval(second_precision=True),
        nullable=False,
        default=timedelta(hours=1),
        key='warmup_interval',
    )
    notify_subscription_end: Final[Column[timedelta]] = Column(
        'NotifySubscriptionEnd',
        Interval(second_precision=True),
        nullable=False,
        default=timedelta(hours=2),
        key='notify_subscription_end',
    )
    replies_per_chat: Final[Column[int]] = Column(
        'RepliesPerChat',
        SmallInteger,
        nullable=False,
        default=1,
        key='replies_per_chat',
    )
