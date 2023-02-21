"""The module that provides a `SentAdModel`."""

from datetime import datetime
from typing import Final

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column, ForeignKey, ForeignKeyConstraint
from sqlalchemy.sql.sqltypes import DateTime, String

from ..base_interface import Base, TableArgs
from ..clients.ad_model import AdModel
from .chat_model import ChatModel


class SentAdModel(Base):
    """
    The model of an already sent message of the advertisment.

    Parameters:
        ad_chat_id (``int``):
            The id of the chat where initial ad message belongs to.

        ad_message_id (``int``):
            The id of the initial ad message in the `ad_chat_id`.

        chat_id (``int``):
            The id of the sent message with the ad.

        message_id (``int``):
            The id of the sent message with the ad.

        link (``str``):
            The link to the sent message with the ad.

        timestamp (``datetime``):
            The date and time the sent message with the ad was sent.
    """

    ad_chat_id: Final = Column(
        AdModel.chat_id.type,
        nullable=False,
    )
    ad_message_id: Final = Column(
        AdModel.message_id.type,
        nullable=False,
    )
    chat_id: Final = Column(
        ChatModel.id.type,
        ForeignKey(ChatModel.id, onupdate='CASCADE', ondelete='NO ACTION'),
        primary_key=True,
    )
    message_id: Final[Column[int]] = Column(
        AdModel.message_id.type,
        CheckConstraint('message_id > 0'),
        primary_key=True,
    )
    link: Final[Column[str]] = Column(
        String(255),
        CheckConstraint("link <> ''"),
        nullable=False,
    )
    timestamp: Final[Column[datetime]] = Column(
        DateTime(timezone=True),
        nullable=False,
    )
    ad: Mapped['RelationshipProperty[AdModel]'] = relationship(
        'AdModel',
        back_populates='sent_ads',
        lazy='joined',
        cascade='save-update',
        uselist=False,
    )
    chat: Mapped['RelationshipProperty[ChatModel]'] = relationship(
        'ChatModel',
        back_populates='sent_ads',
        lazy='joined',
        cascade='save-update',
        uselist=False,
    )

    __table_args__: Final[TableArgs] = (
        ForeignKeyConstraint(
            [ad_chat_id, ad_message_id],
            [AdModel.chat_id, AdModel.message_id],
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
    )
