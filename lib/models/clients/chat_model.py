"""The module that provides a `ChatModel`."""

from typing import TYPE_CHECKING, Final, List, Optional, Self, Type

from sqlalchemy import CheckConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.expression import ClauseElement
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import BigInteger, String

from .._constraints import MAX_USERNAME_LENGTH
from .._mixins import Timestamped
from ..base_interface import Base

if TYPE_CHECKING:
    from .ad_chat_model import AdChatModel


class ChatModel(Timestamped, Base):
    """
    The model of a chat where messages are sent to.

    Parameters:
        id (``int``):
            The unique id of this client.

        title (``str``):
            The title of this chat.

        description (``str``, *optional*):
            The description of this chat.

        username (``str``, *optional*):
            The username of this chat.

        invite_link (``str``, *optional*):
            The invite link of this chat.

        active (``bool``):
            If this chat is currently available for sending.

        deactivated_cause (``ChatDeactivatedCause``, *optional*):
            The last cause why this chat was automatically deactivated.

        created_at (``datetime``):
            The date and time this model was added to the database.

        updated_at (``datetime``):
            The date and time of the last time this model was updated in the
            database.
    """

    id: Final[Column[int]] = Column(
        BigInteger,
        primary_key=True,
    )
    title: Final[Column[str]] = Column(
        String(255),
        CheckConstraint("title <> ''"),
        nullable=False,
    )
    description: Final[Column[Optional[str]]] = Column(
        String(1023),
        CheckConstraint("description <> ''"),
    )
    username: Final[Column[Optional[str]]] = Column(
        String(MAX_USERNAME_LENGTH),
        CheckConstraint("username <> ''"),
        unique=True,
    )
    invite_link: Final[Column[Optional[str]]] = Column(
        String(1023),
        CheckConstraint("invite_link <> ''"),
        unique=True,
    )

    ads: Mapped['RelationshipProperty[List[AdChatModel]]'] = relationship(
        'AdChatModel',
        back_populates='chat',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )

    @hybrid_property
    def valid(self: Self, /) -> bool:
        """If this user has an active subscription."""
        return self.active and self.deactivated_cause is None

    @valid.expression
    def valid(cls: Type[Self], /) -> ClauseElement:  # noqa: N805
        """Check that user :meth:`.is_subscribed`."""
        return cls.active & cls.deactivated_cause.is_(None)
