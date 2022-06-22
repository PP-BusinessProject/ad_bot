"""The model of a user reply."""

from datetime import datetime
from typing import Final, Optional

from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
)

from .._constraints import MAX_NAME_LENGTH, MAX_USERNAME_LENGTH
from ..base_interface import Base
from .client_model import ClientModel


class ReplyModel(Base):
    """The model to store user replies to :class:`ClientModel`."""

    client_phone_number: Final[Column[int]] = Column(
        'ClientPhoneNumber',
        ClientModel.phone_number.type,
        ForeignKey(
            ClientModel.phone_number,
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
        primary_key=True,
        key='client_phone_number',
    )
    chat_id: Final[Column[int]] = Column(
        'ChatId',
        BigInteger,
        primary_key=True,
        key='chat_id',
    )
    message_id: Final[Column[int]] = Column(
        'MessageId',
        Integer,
        primary_key=True,
        key='message_id',
    )
    replied: Final[Column[bool]] = Column(
        'Replied',
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
        key='replied',
    )
    first_name: Final[Column[str]] = Column(
        'FirstName',
        String(MAX_NAME_LENGTH),
        nullable=False,
        key='first_name',
    )
    last_name: Final[Column[Optional[str]]] = Column(
        'LastName',
        String(MAX_NAME_LENGTH),
        key='last_name',
    )
    username: Final[Column[Optional[str]]] = Column(
        'Username',
        String(MAX_USERNAME_LENGTH),
        key='username',
    )
    phone_number: Final[Column[Optional[int]]] = Column(
        'PhoneNumber',
        BigInteger,
        key='phone_number',
    )
    timestamp: Final[Column[datetime]] = Column(
        'Timestamp',
        DateTime(timezone=True),
        nullable=False,
        key='timestamp',
    )
    sender_client: Final['RelationshipProperty[ClientModel]'] = relationship(
        'ClientModel',
        back_populates='user_replies',
        lazy='noload',
        cascade='save-update',
        uselist=False,
    )
