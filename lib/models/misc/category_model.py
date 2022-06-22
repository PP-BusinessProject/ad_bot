from typing import TYPE_CHECKING, Final, Optional

from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.expression import literal_column
from sqlalchemy.sql.schema import CheckConstraint, Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer, String

from ..base_interface import Base

if TYPE_CHECKING:
    from ..bots.chat_model import ChatModel
    from ..clients.ad_model import AdModel


class CategoryModel(Base):
    id: Final[Column[int]] = Column(
        'Id',
        Integer,
        primary_key=True,
        autoincrement=True,
        key='id',
    )
    parent_id: Final[Column[Optional[int]]] = Column(
        'ParentId',
        id.type,
        ForeignKey(id, onupdate='CASCADE', ondelete='CASCADE'),
        key='parent_id',
    )
    name: Final[Column[str]] = Column(
        'Name',
        String(255),
        CheckConstraint(literal_column('"Name"') != literal_column('\'\'')),
        nullable=False,
        unique=True,
        key='name',
    )

    ads: Final['RelationshipProperty[list[AdModel]]'] = relationship(
        'AdModel',
        back_populates='category',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
    chats: Final['RelationshipProperty[list[ChatModel]]'] = relationship(
        'ChatModel',
        back_populates='category',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
    parent: Final[
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
    children: Final[
        'RelationshipProperty[list[CategoryModel]]'
    ] = relationship(
        'CategoryModel',
        back_populates='parent',
        lazy='noload',
        join_depth=1,
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
