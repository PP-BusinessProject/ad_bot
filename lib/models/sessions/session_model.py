"""The module that provides a Pyrogram :class:`SessionModel`."""

from typing import TYPE_CHECKING, Final, Optional

from sqlalchemy.orm import relationship
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
        'PhoneNumber',
        BigInteger,
        primary_key=True,
        default=0,
        key='phone_number',
    )
    dc_id: Final[Column[int]] = Column(
        'DcId',
        SmallInteger,
        nullable=False,
        default=2,
        key='dc_id',
    )
    api_id: Final[Column[int]] = Column(
        'ApiId',
        Integer,
        nullable=False,
        key='api_id',
    )
    test_mode: Final[Column[bool]] = Column(
        'TestMode',
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
        key='test_mode',
    )
    auth_key: Final[Column[Optional[bytes]]] = Column(
        'AuthKey',
        LargeBinary,
        key='auth_key',
    )
    user_id: Final[Column[Optional[int]]] = Column(
        'UserId',
        BigInteger,
        unique=True,
        key='user_id',
    )
    is_bot: Final[Column[Optional[int]]] = Column(
        'IsBot',
        Boolean(create_constraint=True),
        key='is_bot',
    )
    peers: Final['RelationshipProperty[list[PeerModel]]'] = relationship(
        'PeerModel',
        back_populates='session',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
