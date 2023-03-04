"""The model of a user reply."""

from typing import Final, Optional

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import BigInteger, Integer, String

from .._constraints import MAX_NAME_LENGTH, MAX_USERNAME_LENGTH
from .._mixins import Timestamped
from ..base_interface import Base
from .client_model import ClientModel


class ReplyModel(Timestamped, Base):
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
    reply_message_id: Final[Column[Optional[int]]] = Column(
        Integer,
        CheckConstraint('reply_message_id IS NULL OR reply_message_id > 0'),
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
    sender_client: Mapped['RelationshipProperty[ClientModel]'] = relationship(
        'ClientModel',
        back_populates='user_replies',
        lazy='noload',
        cascade='save-update',
        uselist=False,
    )
