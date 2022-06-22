from datetime import timedelta
from typing import TYPE_CHECKING, Final

from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import Interval, String

from ..base_interface import Base

if TYPE_CHECKING:
    from ..clients.user_model import UserModel


class SubscriptionModel(Base):
    period: Final[Column[timedelta]] = Column(
        'Period',
        Interval(second_precision=True),
        primary_key=True,
        key='period',
    )
    name: Final[Column[str]] = Column(
        'Name',
        String(255),
        nullable=False,
        key='name',
    )

    users: Final['RelationshipProperty[list[UserModel]]'] = relationship(
        'UserModel',
        back_populates='subscription',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
