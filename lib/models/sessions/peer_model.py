"""The module that provides a Pyrogram :class:`PeerModel`."""

from typing import Final, Literal, Optional

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column, ForeignKey, UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger, String

from .._constraints import MAX_USERNAME_LENGTH
from .._mixins import Timestamped
from ..base_interface import Base, TableArgs
from .session_model import SessionModel

PeerType: Final = Literal['bot', 'user', 'group', 'channel', 'supergroup']


class PeerModel(Timestamped, Base):
    """The model of a Pyrogram peer."""

    session_phone_number: Final[Column[int]] = Column(
        SessionModel.phone_number.type,
        ForeignKey(
            SessionModel.phone_number,
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
        primary_key=True,
    )
    id: Final[Column[int]] = Column(
        BigInteger,
        primary_key=True,
    )
    access_hash: Final[Column[int]] = Column(
        BigInteger,
        nullable=False,
        default=0,
    )
    type: Final[Column[PeerType]] = Column(
        String,
        CheckConstraint("type <> ''"),
        nullable=False,
    )
    username: Final[Column[Optional[str]]] = Column(
        String(MAX_USERNAME_LENGTH),
        CheckConstraint("username <> ''"),
    )
    phone_number: Final[Column[Optional[str]]] = Column(
        BigInteger,
        CheckConstraint('phone_number > 0'),
    )
    session: Mapped['RelationshipProperty[SessionModel]'] = relationship(
        'SessionModel',
        back_populates='peers',
        lazy='noload',
        cascade='save-update',
        uselist=False,
    )

    __table_args__: Final[TableArgs] = (
        UniqueConstraint(session_phone_number, username),
        UniqueConstraint(session_phone_number, phone_number),
    )
