"""The module that provides an `AdModel`."""

from datetime import datetime
from typing import TYPE_CHECKING, Final, List, Optional, Self, Type

from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.expression import ClauseElement, and_
from sqlalchemy.sql.schema import Column, ForeignKeyConstraint, CheckConstraint
from sqlalchemy.sql.sqltypes import Boolean, Integer, DateTime

from .._mixins import Timestamped
from ..base_interface import Base, TableArgs
from .bot_model import BotModel, UserModel

if TYPE_CHECKING:
    from .ad_chat_model import AdChatModel


class AdModel(Timestamped, Base):
    """
    The model that represents an advertisment.

    Parameters:
        bot_owner_id (``int``):
            The id of the owner of the bot which will be sending this ad.

        bot_id (``int``):
            The id of the bot which will be sending this ad.

        chat_id (``int``):
            The id of the service channel to copy this ad from.

        message_id (``int``):
            The id of the message in the service channel to copy this ad from.

        confirm_message_id (``Optional[int]``):
            The id of the current message that confirmes this bot in this bot
            owner's service channel.

        confirmed (``bool``):
            If this advertisment was confirmed by administrator.

        active (``bool``):
            If this advertisment is currently active for mailing.

        banned (``bool``):
            If this advertisment can be mailed at all. Can only be edited by
            administrator.

        corrupted (``bool``):
            If this advertisment's message was somehow corrupted.

        created_at (``datetime``):
            The date and time this model was added to the database.

        updated_at (``datetime``):
            The date and time of the last time this model was updated in the
            database.
    """

    bot_owner_id: Final = Column(
        BotModel.owner_id.type,
        nullable=False,
    )
    bot_id: Final = Column(
        BotModel.id.type,
        nullable=False,
    )
    chat_id: Final = Column(
        UserModel.service_id.type,
        primary_key=True,
    )
    message_id: Final = Column(
        Integer,
        CheckConstraint('message_id > 0'),
        primary_key=True,
    )
    confirm_message_id: Column[Optional[int]] = Column(
        Integer,
        CheckConstraint('confirm_message_id IS NULL OR confirm_message_id > 0'),
    )
    active: Column[bool] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
    )
    banned: Column[bool] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
    )
    corrupted: Column[bool] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
    )
    last_sent_at: Column[Optional[datetime]] = Column(DateTime(timezone=True))
    owner_bot: Mapped['RelationshipProperty[BotModel]'] = relationship(
        'BotModel',
        back_populates='ads',
        lazy='joined',
        cascade='save-update',
        uselist=False,
    )

    chats: Mapped['RelationshipProperty[List[AdChatModel]]'] = relationship(
        'AdChatModel',
        back_populates='ad',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )

    __table_args__: Final[TableArgs] = (
        ForeignKeyConstraint(
            [bot_owner_id, bot_id],
            [BotModel.owner_id, BotModel.id],
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
    )

    @hybrid_property
    def confirmed(self: Self, /) -> bool:
        """If this instance is marked as confirmed."""
        return self.confirm_message_id is None

    @confirmed.expression
    def confirmed(cls: Type[Self], /) -> ClauseElement:  # noqa: N805
        return cls.confirm_message_id.is_(None)

    @hybrid_property
    def valid(self: Self, /) -> bool:
        """If this instance is valid."""
        return (self.confirmed and self.active) and (
            not self.banned and not self.corrupted
        )

    @valid.expression
    def valid(cls: Type[Self], /) -> ClauseElement:  # noqa: N805
        return and_(cls.confirmed, cls.active, ~cls.banned, ~cls.corrupted)
