"""The module that provides a `ClientChatModel`."""

from datetime import datetime, timedelta
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Final, List, Optional, Self, Type

from pyrogram.errors.exceptions.bad_request_400 import (
    ChannelBanned,
    ChannelInvalid,
    ChannelPrivate,
    ChatAdminRequired,
    ChatRestricted,
    PeerIdInvalid,
    UserBannedInChannel,
)
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column, ForeignKey, ForeignKeyConstraint
from sqlalchemy.sql.sqltypes import Boolean, DateTime, Enum, Interval

from .._mixins import Timestamped
from ..base_interface import Base, TableArgs
from .ad_model import AdModel
from .chat_model import ChatModel

if TYPE_CHECKING:
    from .ad_chat_message_model import AdChatMessageModel


class ChatDeactivatedCause(IntEnum):
    """The cause of the deactivation of the sender chat."""

    UNKNOWN: Final[int] = 0
    PEER_INVALID: Final[int] = auto()
    INVALID: Final[int] = auto()
    CHANNEL_BANNED: Final[int] = auto()
    PRIVATE: Final[int] = auto()
    ADMIN_REQUIRED: Final[int] = auto()
    WRITE_FORBIDDEN: Final[int] = auto()
    RESTRICTED: Final[int] = auto()
    USER_BANNED: Final[int] = auto()

    @classmethod
    def from_exception(cls: Type[Self], exception: BaseException, /) -> Self:
        """Return this cause from probable exception."""
        if isinstance(exception, PeerIdInvalid):
            return cls.PEER_INVALID
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
        elif isinstance(exception, ChatRestricted):
            return cls.RESTRICTED
        elif isinstance(exception, UserBannedInChannel):
            return cls.USER_BANNED
        else:
            return cls.UNKNOWN


class AdChatModel(Timestamped, Base):
    ad_chat_id: Final = Column(
        AdModel.chat_id.type,
        primary_key=True,
    )
    ad_message_id: Final = Column(
        AdModel.message_id.type,
        primary_key=True,
    )
    chat_id: Final = Column(
        ChatModel.id.type,
        ForeignKey(ChatModel.id, onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True,
    )
    period: Final[Column[timedelta]] = Column(
        Interval(second_precision=0),
        nullable=False,
        default=timedelta(minutes=20),
    )
    active: Final[Column[bool]] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
    )
    last_sent_at: Column[Optional[datetime]] = Column(DateTime(timezone=True))
    deactivated_cause: Final[Column[Optional[ChatDeactivatedCause]]] = Column(
        Enum(ChatDeactivatedCause),
    )
    slowmode_wait: Final[Column[Optional[datetime]]] = Column(
        DateTime(timezone=True)
    )

    __table_args__: Final[TableArgs] = (
        ForeignKeyConstraint(
            [ad_chat_id, ad_message_id],
            [AdModel.chat_id, AdModel.message_id],
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
    )

    ad: Mapped['RelationshipProperty[AdModel]'] = relationship(
        'AdModel',
        back_populates='chats',
        lazy='joined',
        cascade='save-update',
        uselist=False,
    )
    chat: Mapped['RelationshipProperty[ChatModel]'] = relationship(
        'ChatModel',
        back_populates='ads',
        lazy='joined',
        cascade='save-update',
        uselist=False,
    )
    messages: Mapped[
        'RelationshipProperty[List[AdChatMessageModel]]'
    ] = relationship(
        'AdChatMessageModel',
        back_populates='ad_chat',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
