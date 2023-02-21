"""Module for utilizing the :class:`Query` for sending data."""


from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from inspect import isfunction
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    Final,
    Iterable,
    Optional,
    Self,
    Type,
    TypeVar,
    Union,
)

from sqlalchemy.sql.sqltypes import String
from sqlalchemy.sql.type_api import TypeDecorator, TypeEngine

#
_T = TypeVar('_T')


def _decode_arg(arg: str, /) -> Any:
    if not arg or arg == 'None':
        return None
    try:
        return int(arg)
    except ValueError:
        with suppress(ValueError):
            return float(arg)
    return arg


def _encode_arg(arg: Any, /) -> str:
    return '' if arg is None else str(arg)


def _decode_kwarg(
    kwarg: str,
    /,
    sep: Optional[str] = ':',
) -> Optional[tuple[str, Optional[Any]]]:
    if not kwarg:
        return None
    key, value, *_ = *kwarg.split(sep), None
    if value is None:
        return None
    key = _decode_arg(key)
    if not isinstance(key, str):
        return None
    return key, _decode_arg(value)


def _encode_kwarg(key: str, value: Any, /, sep: str = ':') -> str:
    return '' if value is None else sep.join(map(str, (key, value)))


def _pass(
    function: Optional[Callable[..., _T]],
    /,
    *args,
    **kwargs,
) -> Optional[_T]:
    return function(*args, **kwargs) if isfunction(function) else None


class QueryType(TypeDecorator):
    """The database type for a :class:``.Query``."""

    impl: Union[Type[TypeEngine], TypeEngine] = String
    cache_ok: bool = False

    def process_bind_param(self: Self, value: Any, dialect: Any, /) -> str:
        """Return enum value."""
        if isinstance(value, str):
            value = self.process_result_value(value, dialect)
        return str(value) if isinstance(value, Query) else None

    def process_result_value(self: Self, value: Any, dialect: Any, /) -> Query:
        """Bind the enum from value."""
        return Query.parse(value) if isinstance(value, str) else None


@dataclass(init=False, frozen=True)
class Query(object):
    """Manages a data for a :class:``CallbackQuery``."""

    command: Final[str]
    args: Final[tuple[Any]]
    kwargs: Final[MappingProxyType[str, Any]]
    sep: Final[str]
    encoding: Final[str]
    args_encode: Final[Optional[Callable[[Any], str]]]
    kwargs_encode: Final[Optional[Callable[[str, Any], str]]]

    @classmethod
    def parse(
        cls: Type[Self],
        raw: Union[str, bytes],
        /,
        *,
        sep: str = '|',
        encoding: str = 'utf-8',
        args_decode: Optional[Callable[[str], Optional[Any]]] = _decode_arg,
        args_encode: Optional[Callable[[Any], str]] = _encode_arg,
        kwargs_decode: Optional[
            Callable[[str], Optional[tuple[str, Optional[Any]]]]
        ] = _decode_kwarg,
        kwargs_encode: Optional[Callable[[str, Any], str]] = _encode_kwarg,
    ) -> Self:
        """
        Create ``Query`` from raw string.

        Args:
            raw (``int``):
                The raw object to parse. If `bool(raw)` is False, raises
                ValueError.

            sep (``str``, *optional*):
                The separator of data values in the string.

            encoding (``str``, *optional*):
                The encoding to which a resulting string will be formatted.

            args_decode (``Callable[[str], Any]``, *optional*):
                The decoder for the arguments.

            args_encode (``Optional[Callable[[Any], str]]``, *optional*):
                The encoder for the arguments.

            kwargs_decode (``...``, *optional*):
                The decoder for the key-word arguments.

            kwargs_encode (``...``, *optional*):
                The encoder for the key-word arguments.

        Returns:
            If any data is matched, returns the ``Query`` created from it.
        """
        if not raw:
            raise ValueError(f'Object `{raw}` is not valid.')

        command, *args_kwargs = cls._decode(raw, encoding).split(sep)
        args, kwargs = [], {}
        for arg_kwarg in args_kwargs:
            if result := _pass(kwargs_decode, arg_kwarg):
                key, value = result
                if key:
                    kwargs[key] = value
            else:
                args.append(_pass(args_decode, arg_kwarg))

        kwargs.update(sep=sep, args_encode=args_encode)
        kwargs.update(kwargs_encode=kwargs_encode)
        return cls(command, *args, **kwargs)

    def __init__(
        self: Self,
        command: str,
        /,
        *args: Any,
        sep: str = '|',
        encoding: str = 'utf-8',
        args_encode: Optional[Callable[[str], Any]] = _encode_arg,
        kwargs_encode: Optional[Callable[[str, Any], str]] = _encode_kwarg,
        **kwargs: Any,
    ) -> Self:
        """
        Init a ``Query`` with command and args.

        Separator is used when converting to a string.
        """
        object.__setattr__(self, 'command', command)
        object.__setattr__(self, 'sep', sep)
        object.__setattr__(self, 'encoding', encoding)
        object.__setattr__(self, 'args', args)
        object.__setattr__(self, 'kwargs', MappingProxyType(kwargs))
        object.__setattr__(self, 'args_encode', args_encode)
        object.__setattr__(self, 'kwargs_encode', kwargs_encode)

    @classmethod
    def _encode(
        cls: Type[Self],
        raw,
        /,
        encoding: str = 'utf-8',
    ) -> bytes:
        """Encrypt the raw object."""
        return bytes(str(raw), encoding)

    @classmethod
    def _decode(
        cls: Type[Self],
        raw: Any,
        /,
        encoding: str = 'utf-8',
    ) -> str:
        """Decrypt the raw object."""
        if not isinstance(raw, bytes):
            raw = cls._encode(raw, encoding)
        return raw.decode(encoding)

    def __copy__(
        self: Self,
        /,
        command: Optional[str] = None,
        args: Optional[Iterable[Any]] = None,
        kwargs: Optional[dict[str, Any]] = None,
        sep: Optional[str] = None,
        encoding: Optional[str] = None,
        args_encode: Optional[Callable[[str], Any]] = None,
        kwargs_encode: Optional[Callable[[str, Any], str]] = None,
    ) -> Self:
        """Return the copy of this ``Query``."""
        args, kwargs = args or self.args, dict(kwargs or self.kwargs)
        kwargs.update(sep=sep or self.sep)
        kwargs.update(encoding=encoding or self.encoding)
        kwargs.update(args_encode=args_encode or self.args_encode)
        kwargs.update(kwargs_encode=kwargs_encode or self.kwargs_encode)
        return self.__class__(command or self.command, *args, **kwargs)

    __call__ = __copy__

    def __add__(self: Self, other: _T, /) -> _T:
        return other.__class__(self) + other

    def __radd__(self: Self, other: _T, /) -> _T:
        return other + other.__class__(self)

    def __len__(self: Self, /) -> int:
        return len(str(self))

    def __bytes__(self: Self, /, encoding: Optional[str] = None) -> bytes:
        return bytes(str(self), encoding=encoding or self.encoding)

    def __str__(self: Self, /) -> str:
        return self._decode(self.sep, self.encoding).join(
            self._decode(_, self.encoding)
            for _ in (
                getattr(self.command, 'value', self.command),
                *(
                    self.args_encode(arg) if self.args_encode else arg
                    for arg in self.args
                ),
                *(
                    self.kwargs_encode(*kwarg)
                    if self.kwargs_encode
                    else ':'.join(kwarg)
                    for kwarg in self.kwargs.items()
                ),
            )
            if _
        )
