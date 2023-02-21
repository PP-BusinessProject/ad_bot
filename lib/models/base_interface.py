"""The SQLAlchemy base for :class:`AdBotClient` models."""

from contextlib import suppress
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from re import findall
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Final,
    Iterable,
    List,
    Self,
    Tuple,
    Type,
    Union,
)
from uuid import UUID

from inflect import engine
from pydantic.main import BaseConfig, BaseModel, create_model
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.decl_api import declarative_base, declared_attr
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.orm.state import InstanceState
from sqlalchemy.sql.schema import Column, SchemaItem

#
TableArgs = Tuple[Union[SchemaItem, Dict[str, Any]]]
Policies = Dict[str, Dict[str, Union[bool, str, Tuple[str, ...]]]]
Permissions = Dict[
    Union[str, Tuple[str, ...]],
    Dict[Union[str, Tuple[str, ...]], Tuple[Column, ...]],
]
Serializable = Union[
    Union[None, bool, int, float, Decimal, str],
    Union[List['Serializable'], Dict[str, 'Serializable']],
]


class _OrmConfig(BaseConfig):
    orm_mode: Final[bool] = True


class BaseInterface(object):
    """The base class for all :module:`SQLAlchemy` models."""

    inflect: ClassVar[engine] = engine()
    __mapper_args__: ClassVar[Dict[str, Any]] = dict(eager_defaults=True)

    @declared_attr
    def __tablename__(cls: Type[Self], /) -> str:
        words = findall(r'[A-Z]+[^A-Z]*', cls.__name__.removesuffix('Model'))
        words.append(cls.inflect.plural(words.pop().lower()))
        return '_'.join(word.lower() for word in words)

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
        if hasattr(cls, '__mapper__'):
            return cls.__mapper__.columns
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
    ) -> Dict[RelationshipProperty, Type[Self]]:
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
        return {_.key: self.__dict__.get(_.key) for _ in self.columns} | {
            _.key: self.__dict__.get(_.key) for _ in self.relationships
        }

    @property
    def json(self: Self, /) -> Dict[str, Serializable]:
        return serialize(self)

    def __str__(self: Self, /) -> str:
        return str(self.json)

    def __repr__(self: Self, /) -> str:
        return f'{self.__class__.__name__}(%s)' % ', '.join(
            f'{key}={repr(value)}'
            for key, value in self.json.items()
            if value is not None
        )

    @classmethod
    @property
    def pydantic(cls: Type[Self], /) -> Type[BaseModel]:
        if not hasattr(cls, '_pydantic'):
            cls._pydantic = create_model(
                f'Pydantic{cls.__name__}',
                __config__=_OrmConfig,
                **{
                    column.key: (
                        type,
                        ...
                        if column.default is None
                        and (not column.nullable or not column.autoincrement)
                        else None,
                    )
                    for column, type in cls.columns_types.items()
                },
            )
        return cls._pydantic

    def to_pydantic(self: Self, /) -> BaseModel:
        return self.__class__.pydantic(**self.dict)


def serialize(
    value: Any,
    /,
    checked: Iterable[BaseInterface] = (),
    *,
    encoding: str = 'utf8',
) -> Serializable:
    if isinstance(value, BaseInterface):
        state: InstanceState = inspect(value)
        serialized = {_.key: state.dict.get(_.key) for _ in value.columns}
        for relationship in value.relationships:
            _def = [] if relationship.uselist else None
            if (_value := state.dict.get(relationship.key, _def)) in checked:
                _value = None
            elif isinstance(_value, list):
                for checked_model in checked:
                    while checked_model in _value:
                        _value.remove(checked_model)
            serialized[relationship.key] = _value
        return serialize(serialized, (*checked, value))
    elif isinstance(value, (type(None), bool, int, float, str)):
        return value
    elif isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, UUID):
        return str(value)
    elif isinstance(value, bytes):
        return value.decode(encoding)
    elif isinstance(value, timedelta):
        return value.total_seconds()
    elif isinstance(value, (date, time, datetime)):
        return value.isoformat()
    elif isinstance(value, Enum):
        return value.value
    elif isinstance(value, Callable):
        return f'{value.__module__}.{value.__name__}'
    elif isinstance(value, dict):
        return {
            serialize(k, checked): serialize(v, checked)
            for k, v in value.items()
        }
    elif isinstance(value, Iterable):
        return [serialize(_, checked) for _ in value]
    else:
        raise TypeError(f'Unserializable type "{type(value)}": {value}')


if TYPE_CHECKING:
    from sqlalchemy.orm.decl_api import _DeclarativeBase

    Base: Final[Type[_DeclarativeBase]]

Base = declarative_base(cls=BaseInterface)
