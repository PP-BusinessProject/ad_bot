from typing import Final

from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import String

from ..base_interface import Base
from .._types import TimeDelta


class SubscriptionModel(Base):
    period: Final[Column[int]] = Column(
        'Period',
        TimeDelta,
        primary_key=True,
        key='period',
    )
    name: Final[Column[str]] = Column(
        'Name',
        String(255),
        nullable=False,
        key='name',
    )
