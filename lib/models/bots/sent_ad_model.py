"""The module that provides a `SentAdModel`."""

from datetime import datetime
from typing import Any, Dict, Final, Tuple, Union

from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import (
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    SchemaItem,
)
from sqlalchemy.sql.sqltypes import BigInteger, DateTime, Integer, String

from ..base_interface import Base
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

    ad_chat_id: Final[Column[int]] = Column(
        'AdChatId',
        BigInteger,
        nullable=False,
        key='ad_chat_id',
    )
    ad_message_id: Final[Column[int]] = Column(
        'AdMessageId',
        Integer,
        nullable=False,
        key='ad_message_id',
    )
    chat_id: Final[Column[int]] = Column(
        'ChatId',
        ChatModel.id.type,
        ForeignKey(ChatModel.id, onupdate='CASCADE', ondelete='NO ACTION'),
        primary_key=True,
        key='chat_id',
    )
    message_id: Final[Column[int]] = Column(
        'MessageId',
        Integer,
        primary_key=True,
        key='message_id',
    )
    link: Final[Column[str]] = Column(
        'Link',
        String(255),
        nullable=False,
        key='link',
    )
    timestamp: Final[Column[datetime]] = Column(
        'Timestamp',
        DateTime(timezone=True),
        nullable=False,
        key='timestamp',
    )
    ad: Final['RelationshipProperty[AdModel]'] = relationship(
        'AdModel',
        back_populates='sent_ads',
        lazy='joined',
        cascade='save-update',
        uselist=False,
    )
    chat: Final['RelationshipProperty[ChatModel]'] = relationship(
        'ChatModel',
        back_populates='sent_ads',
        lazy='joined',
        cascade='save-update',
        uselist=False,
    )

    __table_args__: Final[Tuple[Union[SchemaItem, Dict[str, Any]], ...]] = (
        ForeignKeyConstraint(
            [ad_chat_id, ad_message_id],
            [AdModel.chat_id, AdModel.message_id],
            onupdate='CASCADE',
            ondelete='NO ACTION',
        ),
    )
