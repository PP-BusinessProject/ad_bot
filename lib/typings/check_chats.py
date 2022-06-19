"""The module with typings for :meth:`AdBotClient.check_chats`."""

from typing import Final, Iterable, Optional, Union

from pyrogram.types.user_and_chats.chat import Chat

#
CheckChat: Final = Union[
    Union[int, str, Chat],
    tuple[Union[int, str, Chat], Union[Optional[str], Iterable[str]]],
]
