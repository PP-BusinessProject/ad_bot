"""The module that provides a `ChatModel`."""

from datetime import timedelta
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Final, Optional, Type

from pyrogram.errors.exceptions.flood_420 import (
    SlowmodeWait,
)
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.expression import ClauseElement
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import BigInteger, Boolean, String, Interval, Enum
from typing_extensions import Self
from pyrogram.errors.exceptions.bad_request_400 import (
    PeerIdInvalid,
    ChannelBanned,
    ChannelInvalid,
    ChannelPrivate,
    ChatAdminRequired,
)
from .._mixins import Timestamped
from ..base_interface import Base
from ..misc.category_model import CategoryModel

if TYPE_CHECKING:
    from .sent_ad_model import SentAdModel


class ChatDeactivatedCause(IntEnum):
    """The cause of the deactivation of the sender chat."""

    UNKNOWN: Final[int] = 0
    PEER_INVALID: Final[int] = auto()
    SLOWMODE: Final[int] = auto()
    INVALID: Final[int] = auto()
    BANNED: Final[int] = auto()
    PRIVATE: Final[int] = auto()
    ADMIN_REQUIRED: Final[int] = auto()
    WRITE_FORBIDDEN: Final[int] = auto()

    @classmethod
    def from_exception(cls: Type[Self], exception: BaseException, /) -> Self:
        """Return this cause from probable exception."""
        if isinstance(exception, PeerIdInvalid):
            return cls.PEER_INVALID
        elif isinstance(exception, SlowmodeWait):
            return cls.SLOWMODE
        elif isinstance(exception, ChannelInvalid):
            return cls.INVALID
        elif isinstance(exception, ChannelBanned):
            return cls.BANNED
        elif isinstance(exception, ChannelPrivate):
            return cls.PRIVATE
        elif isinstance(exception, ChatAdminRequired):
            return cls.ADMIN_REQUIRED
        elif isinstance(exception, ChatWriteForbidden):
            return cls.WRITE_FORBIDDEN
        else:
            return cls.UNKNOWN


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

        category (``CategoryModel``, *optional*):
            The category of this chat.

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
        'Id',
        BigInteger,
        primary_key=True,
        key='id',
    )
    title: Final[Column[str]] = Column(
        'Title',
        String,
        nullable=False,
        key='title',
    )
    description: Final[Column[Optional[str]]] = Column(
        'Description',
        String,
        key='description',
    )
    username: Final[Column[Optional[str]]] = Column(
        'Username',
        String,
        unique=True,
        key='username',
    )
    invite_link: Final[Column[Optional[str]]] = Column(
        'InviteLink',
        String,
        unique=True,
        key='invite_link',
    )
    category_id: Final[Column[Optional[int]]] = Column(
        'CategoryId',
        CategoryModel.id.type,
        ForeignKey(CategoryModel.id, onupdate='CASCADE', ondelete='SET NULL'),
        key='category_id',
    )
    period: Final[Column[timedelta]] = Column(
        'Period',
        Interval(second_precision=True),
        nullable=False,
        default=timedelta(minutes=20),
        key='period',
    )
    active: Final[Column[bool]] = Column(
        'Active',
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
        key='active',
    )
    deactivated_cause: Final[Column[Optional[ChatDeactivatedCause]]] = Column(
        'DeactivatedCause',
        Enum(ChatDeactivatedCause),
        key='deactivated_cause',
    )
    category: Final[
        'RelationshipProperty[Optional[CategoryModel]]'
    ] = relationship(
        'CategoryModel',
        back_populates='chats',
        lazy='noload',
        cascade='save-update',
        uselist=False,
    )
    sent_ads: Final['RelationshipProperty[list[SentAdModel]]'] = relationship(
        'SentAdModel',
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
