"""The module that provides a `UserRole` and `UserModel`."""

from datetime import datetime, timedelta
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Final, Optional, Type

from dateutil.tz.tz import tzlocal
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.expression import ClauseElement, and_, or_
from sqlalchemy.sql.functions import now
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import BigInteger, DateTime, Enum, Integer, String
from typing_extensions import Self

from .._mixins import Timestamped
from ..base_interface import Base
from ..misc.subscription_model import SubscriptionModel

if TYPE_CHECKING:
    from .bot_model import BotModel


class UserRole(IntEnum):
    """The role of a `UserModel`."""

    USER: Final[int] = auto()
    SUPPORT: Final[int] = auto()
    ADMIN: Final[int] = auto()

    @property
    def name(self: Self, /) -> str:
        if self == self.ADMIN:
            return 'администратор'
        elif self == self.SUPPORT:
            return 'саппорт'
        else:
            return 'пользователь'


class UserModel(Timestamped, Base):
    """
    The model that represents a user.

    Parameters:
        id (``int``):
            The id of this user.

        role (``UserRole``):
            The role of this user.

        service_id (``int``, *optional*):
            The id of a chat for storing user service commands.

        service_invite (``str``, *optional*):
            The invite to the chat for storing user service commands.

        subscription_message_id (``int``, *optional*):
            The id of a message in the service chat which corresponds to
            user's subscription.

        help_message_id (``int``, *optional*):
            The id of a message in the service chat which contacts
            administration.

        subscription_from (``datetime``, *optional*):
            The date and time when user has bought a subscription.

        subscription_period (``datetime``, *optional*):
            The amount of time since `subscription_from` for subscription to be
            active.

        created_at (``datetime``):
            The date and time this model was added to the database.

        updated_at (``datetime``):
            The date and time of the last time this model was updated in the
            database.

        bots (``list[BotModel]``, *optional*):
            The bots that belong to this user. If any were fetched yet.
    """

    id: Final[Column[int]] = Column(
        'Id',
        BigInteger,
        primary_key=True,
        key='id',
    )
    role: Final[Column[UserRole]] = Column(
        'Role',
        Enum(UserRole),
        nullable=False,
        default=UserRole.USER,
        key='role',
    )
    service_id: Final[Column[Optional[int]]] = Column(
        'ServiceId',
        BigInteger,
        unique=True,
        key='service_id',
    )
    service_invite: Final[Column[Optional[str]]] = Column(
        'ServiceInvite',
        String,
        unique=True,
        key='service_invite',
    )
    subscription_message_id: Final[Column[Optional[int]]] = Column(
        'SubscriptionMessageId',
        Integer,
        key='subscription_message_id',
    )
    help_message_id: Final[Column[Optional[int]]] = Column(
        'HelpMessageId',
        Integer,
        key='help_message_id',
    )
    subscription_from: Final[Column[Optional[datetime]]] = Column(
        'SubscriptionFrom',
        DateTime(timezone=True),
        key='subscription_from',
    )
    subscription_period: Final[Column[Optional[timedelta]]] = Column(
        'SubscriptionPeriod',
        SubscriptionModel.period.type,
        ForeignKey(
            SubscriptionModel.period,
            onupdate='RESTRICT',
            ondelete='RESTRICT',
        ),
        key='subscription_period',
    )
    subscription: Final[
        'RelationshipProperty[Optional[SubscriptionModel]]'
    ] = relationship(
        'SubscriptionModel',
        back_populates='users',
        lazy='noload',
        cascade='save-update',
        uselist=False,
    )
    bots: Final['RelationshipProperty[list[BotModel]]'] = relationship(
        'BotModel',
        back_populates='owner',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )

    @hybrid_property
    def is_subscribed(self: Self, /) -> bool:
        """If this user has an active subscription."""
        return self.role >= UserRole.SUPPORT or (
            self.subscription_from is not None
            and self.subscription_period is not None
            and self.subscription_from
            > datetime.now(tzlocal()) - self.subscription_period
        )

    @is_subscribed.expression
    def is_subscribed(cls: Type[Self], /) -> ClauseElement:  # noqa: N805
        """Check that user :meth:`.is_subscribed`."""
        return or_(
            cls.role >= UserRole.SUPPORT,
            and_(
                cls.subscription_from.is_not(None),
                cls.subscription_period.is_not(None),
                cls.subscription_from > now() - cls.subscription_period,
            ),
        )
