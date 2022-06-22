"""The module that provides an `AdModel`."""

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Final,
    Optional,
    Tuple,
    Type,
    Union,
)

from sqlalchemy import ForeignKey
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.expression import ClauseElement, and_
from sqlalchemy.sql.schema import Column, ForeignKeyConstraint, SchemaItem
from sqlalchemy.sql.sqltypes import Boolean, Integer
from typing_extensions import Self

from .._mixins import Timestamped
from ..base_interface import Base
from ..misc.category_model import CategoryModel
from .bot_model import BotModel, UserModel

if TYPE_CHECKING:
    from ..bots.sent_ad_model import SentAdModel


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

    bot_owner_id: Final[Column[int]] = Column(
        'BotOwnerId',
        BotModel.owner_id.type,
        nullable=False,
        key='bot_owner_id',
    )
    bot_id: Final[Column[int]] = Column(
        'BotId',
        BotModel.id.type,
        nullable=False,
        key='bot_id',
    )
    chat_id: Final[Column[int]] = Column(
        'ChatId',
        UserModel.service_id.type,
        primary_key=True,
        key='chat_id',
    )
    message_id: Final[Column[int]] = Column(
        'MessageId',
        Integer,
        primary_key=True,
        key='message_id',
    )
    category_id: Final[Column[Optional[int]]] = Column(
        'CategoryId',
        CategoryModel.id.type,
        ForeignKey(CategoryModel.id, onupdate='CASCADE', ondelete='SET NULL'),
        key='category_id',
    )
    confirm_message_id: Column[Optional[int]] = Column(
        'ConfirmMessageId',
        Integer,
        key='confirm_message_id',
    )
    active: Column[bool] = Column(
        'Active',
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
        key='active',
    )
    banned: Column[bool] = Column(
        'Banned',
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
        key='banned',
    )
    corrupted: Column[bool] = Column(
        'Corrupted',
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
        key='corrupted',
    )
    owner_bot: Final['RelationshipProperty[BotModel]'] = relationship(
        'BotModel',
        back_populates='ads',
        lazy='joined',
        cascade='save-update',
        uselist=False,
    )
    category: Final[
        'RelationshipProperty[Optional[CategoryModel]]'
    ] = relationship(
        'CategoryModel',
        back_populates='ads',
        lazy='noload',
        cascade='save-update',
        uselist=False,
    )
    sent_ads: Final['RelationshipProperty[list[SentAdModel]]'] = relationship(
        'SentAdModel',
        back_populates='ad',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )

    __table_args__: Final[Tuple[Union[SchemaItem, Dict[str, Any]], ...]] = (
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
