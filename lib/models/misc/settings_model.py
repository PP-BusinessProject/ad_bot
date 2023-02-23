from datetime import timedelta
from typing import Final, Literal

from sqlalchemy.sql.schema import CheckConstraint, Column
from sqlalchemy.sql.sqltypes import Boolean, Interval, SmallInteger

from ..base_interface import Base


class SettingsModel(Base):
    __tablename__: Final[str] = 'settings'

    id: Final[Column[Literal[True]]] = Column(
        Boolean(create_constraint=True),
        CheckConstraint('id'),
        primary_key=True,
        default=True,
    )
    page_list_size: Final[Column[int]] = Column(
        SmallInteger,
        CheckConstraint('page_list_size > 0'),
        nullable=False,
        default=10,
    )
    bots_per_user: Final[Column[int]] = Column(
        SmallInteger,
        CheckConstraint('bots_per_user > 0'),
        nullable=False,
        default=3,
    )
    ads_per_bot: Final[Column[int]] = Column(
        SmallInteger,
        CheckConstraint('ads_per_bot > 0'),
        nullable=False,
        default=5,
    )
    send_interval: Final[Column[timedelta]] = Column(
        Interval(second_precision=0),
        CheckConstraint("send_interval > INTERVAL '0 days'"),
        nullable=False,
        default=timedelta(seconds=30),
    )
    warmup_interval: Final[Column[timedelta]] = Column(
        Interval(second_precision=0),
        CheckConstraint("warmup_interval > INTERVAL '0 days'"),
        nullable=False,
        default=timedelta(hours=1),
    )
    notify_subscription_end: Final[Column[timedelta]] = Column(
        Interval(second_precision=0),
        CheckConstraint("notify_subscription_end > INTERVAL '0 days'"),
        nullable=False,
        default=timedelta(hours=2),
    )
    replies_per_chat: Final[Column[int]] = Column(
        SmallInteger,
        CheckConstraint("replies_per_chat > 0"),
        nullable=False,
        default=1,
    )
