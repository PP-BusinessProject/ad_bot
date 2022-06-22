"""The module that provides a Pyrogram :class:`PeerModel`."""

from typing import Any, Dict, Final, Literal, Optional, Tuple, Union
from sqlalchemy import Numeric

from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.schema import PrimaryKeyConstraint as PKC
from sqlalchemy.sql.schema import SchemaItem
from sqlalchemy.sql.schema import UniqueConstraint as UC
from sqlalchemy.sql.sqltypes import BigInteger, Integer, String

from .._mixins import Timestamped
from ..base_interface import Base
from .session_model import SessionModel

PeerType: Final = Literal['bot', 'user', 'group', 'channel', 'supergroup']


class PeerModel(Timestamped, Base):
    """The model of a Pyrogram peer."""

    session_phone_number: Final[Column[int]] = Column(
        'SessionPhoneNumber',
        SessionModel.phone_number.type,
        ForeignKey(
            SessionModel.phone_number,
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
        key='session_phone_number',
    )
    id: Final[Column[int]] = Column(
        'Id',
        BigInteger,
        key='id',
    )
    access_hash: Final[Column[int]] = Column(
        'AccessHash',
        BigInteger,
        nullable=False,
        default=0,
        key='access_hash',
    )
    type: Final[Column[PeerType]] = Column(
        'Type',
        String,
        nullable=False,
        key='type',
    )
    username: Final[Column[Optional[str]]] = Column(
        'Username',
        String,
        key='username',
    )
    phone_number: Final[Column[Optional[str]]] = Column(
        'PhoneNumber',
        BigInteger,
        key='phone_number',
    )
    session: Final['RelationshipProperty[SessionModel]'] = relationship(
        'SessionModel',
        back_populates='peers',
        lazy='noload',
        cascade='save-update',
        uselist=False,
    )

    __table_args__: Final[Tuple[Union[SchemaItem, Dict[str, Any]], ...]] = (
        PKC(session_phone_number, id, sqlite_on_conflict='IGNORE'),
        UC(session_phone_number, username, sqlite_on_conflict='REPLACE'),
        UC(session_phone_number, phone_number, sqlite_on_conflict='REPLACE'),
    )
