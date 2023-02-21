"""The module that provides a Pyrogram :class:`SessionModel`."""

from typing import TYPE_CHECKING, Final, List, Optional

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import (
    BigInteger,
    Boolean,
    Integer,
    LargeBinary,
    SmallInteger,
)

from .._mixins import Timestamped
from ..base_interface import Base

if TYPE_CHECKING:
    from .peer_model import PeerModel


class SessionModel(Timestamped, Base):
    """The model of a Pyrogram session."""

    phone_number: Final[Column[int]] = Column(
        BigInteger,
        CheckConstraint('phone_number >= 0'),
        primary_key=True,
        default=0,
    )
    dc_id: Final[Column[int]] = Column(
        SmallInteger,
        CheckConstraint('dc_id > 0'),
        nullable=False,
        default=2,
    )
    api_id: Final[Column[int]] = Column(
        Integer,
        CheckConstraint('api_id > 0'),
        nullable=False,
    )
    test_mode: Final[Column[bool]] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
    )
    auth_key: Final[Column[Optional[bytes]]] = Column(LargeBinary)
    user_id: Final[Column[Optional[int]]] = Column(
        BigInteger,
        CheckConstraint('user_id > 0'),
        unique=True,
    )
    is_bot: Final[Column[Optional[int]]] = Column(
        Boolean(create_constraint=True),
    )
    peers: Mapped['RelationshipProperty[List[PeerModel]]'] = relationship(
        'PeerModel',
        back_populates='session',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
