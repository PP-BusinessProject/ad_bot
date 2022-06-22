"""Custom column types for the mapped classes."""

from importlib import import_module
from inspect import isfunction
from types import ModuleType
from typing import Any, Callable, Optional, Type, Union

from sqlalchemy.sql.sqltypes import String
from sqlalchemy.sql.type_api import TypeDecorator, TypeEngine
from typing_extensions import Self


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
        if isinstance(value, Callable):  # type: ignore
            return ':'.join((value.__module__, value.__qualname__))
        return None

    def process_result_value(
        self: Self,
        value: Any,
        /,
        dialect: Any = None,
    ) -> Optional[ModuleType]:
        """Bind the enum from value."""
        if not isinstance(value, str):
            return None

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
            except (AttributeError, ImportError):
                return None
        return None
