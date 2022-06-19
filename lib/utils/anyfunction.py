# type: ignore

"""The module with extra utilities."""

from inspect import isasyncgen, iscoroutinefunction, isfunction, isgenerator
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Generator,
    Generic,
    ParamSpec,
    TypeVar,
    Union,
)

#
_P = ParamSpec('_P')
_T = TypeVar('_T')


class AnyFunction(Generic[_P, _T]):
    """The alias for the ``AnyFunction``."""

    f: Union[
        Callable[_P, 'AnyFunction[_P, _T]'],
        Union[_T, Awaitable[_T]],
        AsyncGenerator[_T, Any],
        Generator[_T, Any, Any],
    ]


def isanyfunction(func: AnyFunction[_P, Any], /) -> bool:
    """If the function is suitable for `AnyFunction`."""
    return isfunction(func) or isgenerator(func) or isasyncgen(func)


def isanycorofunction(func: AnyFunction[_P, Any], /) -> bool:
    """If the function is suitable for `AnyFunction`."""
    return iscoroutinefunction(func) or isasyncgen(func)


def anyfunction(
    function: AnyFunction[_P, _T],
    /,
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> Union[_T, Awaitable[_T]]:
    """
    Return the boolean value of the initial `function`.

    Args:
        function (``AnyFunction[_T, _V]``):
            The function to process.

        args (``tuple[Any``, *optional*):
            The arguments passed to `function`, if any.

        kwargs (``dict[str, Any]``, *optional*):
            The key-word arguments passed to `function`, if any.

    Returns:
        * If the `function` is a `Generator`, returns it's first returned
        value.
        * If the `function` is not a `Function`, returns that object itself.

    Raises:
        * `StopIteration` if the `function` is a `Generator` and has no value.
    """
    if isinstance(function, Generator):
        return next(function)
    elif isanycorofunction(function):
        return anycorofunction(function, *args, **kwargs)
    elif isanyfunction(function):
        return anyfunction(function(*args, **kwargs), *args, **kwargs)
    else:
        return function


async def anycorofunction(
    function: AnyFunction[_P, Awaitable[_T]],
    /,
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> _T:
    """
    Return the value of the initial `function`.

    Args:
        function (``AnyFunction[_T, _V]``):
            The function to process.

        args (``tuple[Any``, *optional*):
            The arguments passed to `function`, if any.

        kwargs (``dict[str, Any]``, *optional*):
            The key-word arguments passed to `function`, if any.

    Returns:
        * If the `function` is a `Generator` or an `AsyncGenerator`, returns
        it's first returned value.
        * If the `function` is not a `Function`, returns that object itself.

    Raises:
        * `StopIteration` if the `function` is a `Generator` and has no value.
        * `StopAsyncIteration` if the `function` is an `AsyncGenerator` and has
        no value.
    """
    if isinstance(function, Generator):
        return next(function)
    elif isinstance(function, AsyncGenerator):
        return await anext(function)
    elif iscoroutinefunction(function):
        function = await function(*args, **kwargs)
    elif isfunction(function):
        function = function(*args, **kwargs)
    else:
        return function
    return await anycorofunction(function, *args, **kwargs)
