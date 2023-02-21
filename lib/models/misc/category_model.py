from typing import TYPE_CHECKING, Final, List, Optional

from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import CheckConstraint, Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer, String

from ..base_interface import Base

if TYPE_CHECKING:
    from ..bots.chat_model import ChatModel
    from ..clients.ad_model import AdModel


class CategoryModel(Base):
    id: Final[Column[int]] = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    parent_id: Final[Column[Optional[int]]] = Column(
        id.type,
        ForeignKey(id, onupdate='CASCADE', ondelete='CASCADE'),
    )
    name: Final[Column[str]] = Column(
        String(255),
        CheckConstraint("name <> ''"),
        nullable=False,
        unique=True,
    )

    ads: Mapped['RelationshipProperty[List[AdModel]]'] = relationship(
        'AdModel',
        back_populates='category',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
    chats: Mapped['RelationshipProperty[List[ChatModel]]'] = relationship(
        'ChatModel',
        back_populates='category',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
    parent: Mapped[
        'RelationshipProperty[Optional[CategoryModel]]'
    ] = relationship(
        'CategoryModel',
        back_populates='children',
        lazy='joined',
        join_depth=3,
        remote_side=[id],
        cascade='save-update',
        uselist=False,
    )
    children: Mapped[
        'RelationshipProperty[List[CategoryModel]]'
    ] = relationship(
        'CategoryModel',
        back_populates='parent',
        lazy='noload',
        join_depth=1,
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
