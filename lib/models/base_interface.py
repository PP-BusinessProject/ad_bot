"""The SQLAlchemy base for :class:`AdBotClient` models."""

from __future__ import annotations

from contextlib import suppress
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from re import findall
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    Final,
    Iterable,
    List,
    Type,
    TypeVar,
    Union,
    overload,
)

from inflect import engine
from simplejson import dumps
from sqlalchemy.orm.decl_api import declarative_base, declared_attr
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.orm.state import InstanceState
from sqlalchemy.sql.schema import Column
from typing_extensions import Self

#
Serializable = Union[
    Union[None, bool, int, float, Decimal, str],
    Union[List['Serializable'], Dict[str, 'Serializable']],
]
_Serializable = TypeVar('_Serializable', bound=Serializable, covariant=True)


@overload
def serialize(
    value: _Serializable,
    /,
    *,
    encoding: str = 'utf8',
) -> _Serializable:
    pass


@overload
def serialize(
    value: Union[bytes, date, time, datetime],
    /,
    *,
    encoding: str = 'utf8',
) -> str:
    pass


@overload
def serialize(
    value: timedelta,
    /,
    *,
    encoding: str = 'utf8',
) -> float:
    pass


@overload
def serialize(
    value: BaseInterface,
    /,
    *,
    encoding: str = 'utf8',
) -> Dict[str, Serializable]:
    pass


@overload
def serialize(
    value: Dict[str, _Serializable],
    /,
    *,
    encoding: str = 'utf8',
) -> Dict[str, _Serializable]:
    pass


@overload
def serialize(
    value: Iterable[_Serializable],
    /,
    *,
    encoding: str = 'utf8',
) -> List[_Serializable]:
    pass


@overload
def serialize(value: Any, /, *, encoding: str = 'utf8') -> Serializable:
    pass


def serialize(value: Any, /, *, encoding: str = 'utf8') -> Serializable:
    if isinstance(value, BaseInterface):
        return serialize(value.dict)
    elif isinstance(value, (type(None), bool, int, float, Decimal, str)):
        return value
    elif isinstance(value, bytes):
        return value.decode(encoding)
    elif isinstance(value, timedelta):
        return value.total_seconds()
    elif isinstance(value, (date, time, datetime)):
        return value.isoformat()
    elif isinstance(value, Enum):
        return value.value
    elif isinstance(value, dict):
        return {serialize(k): serialize(v) for k, v in value.items()}
    elif isinstance(value, Iterable):
        return list(map(serialize, value))
    else:
        raise TypeError(f'Unserializable type "{type(value)}": {value}')


class BaseInterface(object):
    """The base class for all :module:`SQLAlchemy` models."""

    inflect: ClassVar[engine] = engine()
    __mapper_args__: Final[dict[str, Any]] = dict(eager_defaults=True)

    @declared_attr
    def __tablename__(cls: Type[Self], /) -> str:  # noqa: N805
        words = findall(r'[A-Z][^A-Z]*', cls.__name__.removesuffix('Model'))
        words.append(cls.inflect.plural(words.pop().lower()).capitalize())
        return ''.join(words)

    @classmethod
    def from_other(cls: Type[Self], other: Any, /) -> Self:
        return cls(
            **{
                column.key: getattr(other, column.key)
                for column in cls.columns
            }
        )

    @classmethod
    def from_previous_state(cls: Type[Self], state: InstanceState, /) -> Self:
        return cls(
            **{
                prop.key: next(
                    iter(getattr(state.attrs, prop.key).history.deleted or ()),
                    getattr(state.attrs, prop.key).value,
                )
                for prop in state.mapper.iterate_properties
                if isinstance(prop, ColumnProperty)
            }
        )

    @classmethod
    @property
    def columns(cls: Type[Self], /) -> Iterable[Column]:
        if hasattr(cls, '__table__'):
            return cls.__table__.columns
        elif not hasattr(cls, '_columns'):
            cls._columns = [
                column.fget(cls)
                if isinstance(column, declared_attr)
                else column
                for key, column in cls.__dict__.items()
                if not key.startswith('_')
                and isinstance(column, (Column, declared_attr))
            ]
        return cls._columns

    @classmethod
    @property
    def column_types(cls: Type[Self], /) -> Dict[Column, Type[Any]]:
        column_types: Dict[Column, Type[Any]] = {}
        for column in cls.columns:
            if getattr(getattr(column.type, 'impl', None), 'python_type', ''):
                column_types[column] = column.type.impl.python_type
            elif getattr(column.type, 'python_type', None):
                column_types[column] = column.type.python_type
            else:
                raise ValueError(f'Could not infer python type for {column}')
        return column_types

    @classmethod
    @property
    def relationships(cls: Type[Self], /) -> Iterable[RelationshipProperty]:
        if hasattr(cls, '__mapper__'):
            return cls.__mapper__.relationships
        elif not hasattr(cls, '_relationships'):
            cls._relationships = [
                column
                for key, column in cls.__dict__.items()
                if not key.startswith('_')
                and isinstance(column, RelationshipProperty)
            ]
        return cls._relationships

    @classmethod
    @property
    def relationship_types(
        cls: Type[Self],
        /,
    ) -> Dict[RelationshipProperty, Type[BaseInterface]]:
        relationship_types: Dict[Column, Type[Any]] = {}
        for relationship in cls.relationships:
            if getattr(getattr(relationship, 'entity', None), 'class_', None):
                relationship_types[relationship] = relationship.entity.class_
            elif getattr(relationship, 'argument', None):
                with suppress(NameError):
                    relationship_types[relationship] = eval(
                        relationship.argument
                    )
                    continue
            raise ValueError(f'Could not infer type for {relationship}')
        return relationship_types

    @property
    def dict(self: Self, /) -> Dict[str, Any]:
        return {_.key: getattr(self, _.key, None) for _ in self.columns} | {
            _.key: getattr(self, _.key, None) for _ in self.relationships
        }

    @property
    def json(self: Self, /) -> Dict[str, Serializable]:
        return serialize(self)

    def __str__(self: Self, /) -> str:
        return dumps(
            self.json,
            skipkeys=False,
            check_circular=False,
            separators=(',', ':'),
            namedtuple_as_object=False,
        )

    def __repr__(self: Self, /) -> str:
        return f'{self.__class__.__name__}(%s)' % ', '.join(
            f'{key}={repr(value)}'
            for key, value in self.json.items()
            if value is not None
        )


if TYPE_CHECKING:
    from sqlalchemy.orm.decl_api import _DeclarativeBase

    Base: Final[Type[_DeclarativeBase]]

Base = declarative_base(cls=BaseInterface)
