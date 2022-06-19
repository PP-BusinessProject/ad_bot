"""Custom column types for the mapped classes."""

from datetime import datetime, timedelta, tzinfo
from enum import IntEnum as __IntEnum__
from importlib import import_module
from types import ModuleType
from typing import (
    Any,
    Callable,
    Final,
    Generic,
    Optional,
    Type,
    TypeVar,
    Union,
)

from dateutil.tz.tz import tzlocal
from sqlalchemy.sql.sqltypes import Float, Integer, String
from sqlalchemy.sql.type_api import TypeDecorator, TypeEngine
from typing_extensions import Self

#
_IntEnum = TypeVar('_IntEnum', bound=__IntEnum__, covariant=True)


class IntEnum(TypeDecorator[_IntEnum], Generic[_IntEnum]):
    """The type for storing a enum in the database as integer."""

    impl: Final[Union[Type[TypeEngine[Any]], TypeEngine[Any]]] = Integer
    cache_ok: Final[bool] = True

    _enumtype: Final[Type[_IntEnum]]

    def __init__(
        self,
        enumtype: Type[_IntEnum],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize this enum."""
        super().__init__(*args, **kwargs)
        self._enumtype = enumtype

    def process_bind_param(
        self: Self,
        value: Any,
        dialect: Any,
        /,
    ) -> Optional[int]:
        """Return enum value."""
        if isinstance(value, __IntEnum__):
            return value.value

    def process_result_value(
        self: Self,
        value: Any,
        dialect: Any,
        /,
    ) -> Optional[_IntEnum]:
        """Bind the enum from value."""
        if isinstance(value, int):
            return self._enumtype(value)


class DateTimeISO8601(TypeDecorator[datetime]):
    """The type for storing a enum in the database as integer."""

    impl: Final[Union[Type[TypeEngine[Any]], TypeEngine[Any]]] = String(32)
    cache_ok: Final[bool] = False

    sep: Final[str]
    timespec: Final[str]
    default_timezone: Final[tzinfo]
    timezone: Final[tzinfo]

    def __init__(
        self,
        /,
        sep: str = 'T',
        timespec: str = 'auto',
        default_timezone: tzinfo = tzlocal(),
        timezone: tzinfo = tzlocal(),
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize this enum."""
        super().__init__(*args, **kwargs)
        self.sep, self.timespec = sep, timespec
        self.default_timezone, self.timezone = default_timezone, timezone

    def process_bind_param(
        self: Self,
        value: Any,
        dialect: Any,
        /,
    ) -> Optional[str]:
        """Return ISO8601 formatted string from datetime `value`."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=self.default_timezone)
            return value.isoformat(sep=self.sep, timespec=self.timespec)

    def process_result_value(
        self: Self,
        value: Any,
        dialect: Any,
        /,
    ) -> Optional[datetime]:
        """Return the datetime from the ISO8601 formatted string `value`."""
        if isinstance(value, str):
            return datetime.fromisoformat(value).astimezone(self.timezone)


class TimeDelta(TypeDecorator[timedelta]):
    """The type for storing a timedelta in the database as float."""

    impl: Final[Union[Type[TypeEngine[Any]], TypeEngine[Any]]] = Float(25)
    cache_ok: Final[bool] = True

    def process_bind_param(
        self: Self,
        value: Any,
        dialect: Any,
        /,
    ) -> Optional[float]:
        """Return timdelta's total seconds."""
        if isinstance(value, timedelta):
            return value.total_seconds()

    def process_result_value(
        self: Self,
        value: Any,
        dialect: Any,
        /,
    ) -> Optional[timedelta]:
        """Bind the enum from value."""
        if isinstance(value, (int, float)):
            return timedelta(seconds=value)


class LocalFunction(TypeDecorator):
    """The SQLAlchemy converter for the `CategoryModel`."""

    impl: Union[Type[TypeEngine], TypeEngine] = String
    cache_ok: bool = False

    def process_bind_param(
        self: Self,
        value: Any,
        /,
        dialect: Any = None,
    ) -> Optional[str]:
        """Return enum value."""
        if isinstance(value, Callable):
            return ':'.join((value.__module__, value.__qualname__))

    def process_result_value(
        self: Self,
        value: Any,
        /,
        dialect: Any = None,
    ) -> Optional[ModuleType]:
        """Bind the enum from value."""
        if not isinstance(value, str):
            return

        module, _, name = value.rpartition(':')
        if module and name:
            try:
                class_, _, name = name.partition('.')
                obj = getattr(import_module(module), class_)
                while name:
                    temp = name.partition('.')
                    obj = getattr(obj, temp[0])
                    class_, _, name = temp
                return obj if isinstance(obj, Callable) else None
            except (AttributeError, ModuleNotFoundError, ImportError):
                return None
