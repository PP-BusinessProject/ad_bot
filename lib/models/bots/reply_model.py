"""The model of a user reply."""

from datetime import datetime
from typing import Final, Optional

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
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

    client_phone_number: Final = Column(
        ClientModel.phone_number.type,
        ForeignKey(
            ClientModel.phone_number,
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
        primary_key=True,
    )
    chat_id: Final[Column[int]] = Column(
        BigInteger,
        primary_key=True,
    )
    message_id: Final[Column[int]] = Column(
        Integer,
        CheckConstraint('message_id > 0'),
        primary_key=True,
    )
    replied: Final[Column[bool]] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
    )
    first_name: Final[Column[str]] = Column(
        String(MAX_NAME_LENGTH),
        CheckConstraint("first_name <> ''"),
        nullable=False,
    )
    last_name: Final[Column[Optional[str]]] = Column(
        String(MAX_NAME_LENGTH),
        CheckConstraint("last_name <> ''"),
    )
    username: Final[Column[Optional[str]]] = Column(
        String(MAX_USERNAME_LENGTH),
        CheckConstraint("username <> ''"),
    )
    phone_number: Final[Column[Optional[int]]] = Column(
        BigInteger,
        CheckConstraint('phone_number > 0'),
    )
    timestamp: Final[Column[datetime]] = Column(
        DateTime(timezone=True),
        nullable=False,
    )
    sender_client: Mapped['RelationshipProperty[ClientModel]'] = relationship(
        'ClientModel',
        back_populates='user_replies',
        lazy='noload',
        cascade='save-update',
        uselist=False,
    )
