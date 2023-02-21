"""The module that provides an `AdModel`."""

from typing import TYPE_CHECKING, Final, List, Optional, Self, Type

from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.expression import ClauseElement, and_, or_
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import BigInteger, Boolean

from .._mixins import Timestamped
from ..base_interface import Base

if TYPE_CHECKING:
    from ..clients.bot_model import BotModel
    from .reply_model import ReplyModel


class ClientModel(Timestamped, Base):
    """
    The model of a client used for sending advertisment messages.

    Parameters:
        phone_number (``int``):
            The unique phone number of this client.

        restricted (``bool``, *optional*):
            If this client is restricted by Telegram.

        scam (``bool``, *optional*):
            If this client is marked as scam by Telegram.

        fake (``bool``, *optional*):
            If this client is marked as fake by Telegram.

        deleted (``bool``, *optional*):
            If this client is marked as deleted by Telegram.

        warmup (``bool``):
            If this bot is currently getting ready for sending.
                For example, joining sender chats, etc.

        active (``bool``):
            If this bot is currently available for sending.

        created_at (``datetime``):
            The date and time this model was added to the database.

        updated_at (``datetime``):
            The date and time of the last time this model was updated in the
            database.
    """

    phone_number: Final[Column[int]] = Column(BigInteger, primary_key=True)
    restricted: Final[Column[Optional[bool]]] = Column(
        Boolean(create_constraint=True)
    )
    scam: Final[Column[Optional[bool]]] = Column(
        Boolean(create_constraint=True)
    )
    fake: Final[Column[Optional[bool]]] = Column(
        Boolean(create_constraint=True),
    )
    deleted: Final[Column[Optional[bool]]] = Column(
        Boolean(create_constraint=True),
    )
    warmup: Final[Column[bool]] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
    )
    active: Final[Column[bool]] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
    )
    owner_bot: Mapped['RelationshipProperty[BotModel]'] = relationship(
        'BotModel',
        back_populates='sender_client',
        lazy='joined',
        cascade='save-update',
        uselist=False,
    )
    user_replies: Mapped[
        'RelationshipProperty[List[ReplyModel]]'
    ] = relationship(
        'ReplyModel',
        back_populates='sender_client',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )

    @hybrid_property
    def invalid(self: Self, /) -> bool:
        """Check if this client is invalid for sending advertisments."""
        return self.restricted or self.scam or self.fake or self.deleted

    @invalid.expression
    def invalid(cls: Type[Self], /) -> ClauseElement:  # noqa: N805
        return or_(
            *(cls.restricted.is_(True), cls.scam.is_(True)),
            *(cls.fake.is_(True), cls.deleted.is_(True)),
        )

    @hybrid_property
    def valid(self: Self, /) -> bool:
        """Check if this client is valid for sending advertisments."""
        return not self.invalid and self.active

    @valid.expression
    def valid(cls: Type[Self], /) -> ClauseElement:  # noqa: N805
        return and_(~cls.invalid, cls.active)
