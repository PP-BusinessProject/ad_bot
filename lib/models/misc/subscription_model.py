from datetime import timedelta
from typing import TYPE_CHECKING, Final, List

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import Interval, String

from ..base_interface import Base

if TYPE_CHECKING:
    from ..clients.user_model import UserModel


class SubscriptionModel(Base):
    period: Final[Column[timedelta]] = Column(
        Interval(second_precision=0),
        CheckConstraint("period > INTERVAL '0 days'"),
        primary_key=True,
    )
    name: Final[Column[str]] = Column(
        String(255),
        CheckConstraint("name <> ''"),
        nullable=False,
    )

    users: Mapped['RelationshipProperty[List[UserModel]]'] = relationship(
        'UserModel',
        back_populates='subscription',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
