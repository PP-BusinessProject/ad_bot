"""The module with :class:`InputModel`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Final, Generic, Optional, TypeVar

from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import BigInteger, Boolean, Integer, String

from ...utils.query import Query, QueryType
from .._types import IntEnum as IntEnumColumn
from .._types import LocalFunction
from ..base_interface import Base
from ..clients.user_model import UserRole

if TYPE_CHECKING:
    from .input_message_model import InputMessageModel

#
T = TypeVar('T')


class InputModel(Generic[T], Base):
    """
    The class for storing input data.

    Parameters:
        chat_id (``int``):
            The id of a chat that the input is requested to.

        message_id (``Optional[int]``):
            The id of the initial message that the input is requested from.

        data (``Query``):
            The initital query the input started from.

        on_response (``Callable[..., bool]``):
            The callback to call when this input is answered.
                If it's result is True, finishes the input.

        on_finished (``Optional[Callable[..., T]]``):
            The callback to call when this input is finished or cancelled.

        do_add_message (``bool``):
            The callback for distinguishing incoming messages.
                If it's result is True, adds the message to the used messages.

        clear_used_messages (``bool``):
            If the used messages should be removed on removal of this input.

        group (``int``):
            The group to add input handler to.

        query_pattern (``Optional[str]``):
            The pattern used to match incoming `CallbackQuery` updates.

        user_role (``Optional[UserRole]``):
            The role of a user which to accept the input from.

        calls_count (``int``):
            The maximum count of simultaneous `on_response` calls.

        action (``str``):
            The action to apply via :meth:`Client.send_chat_action`.

        private (``bool``):
            If the input should be only in private chats.

        replace_calls (``bool``):
            Whether the overflowing simultaneous call should replace the
            existing one.

        success (``Optional[bool]``):
            If this input has been completed successfully.

        used_messages (``list[UsedMessage]``):
            The messages used in this input.
    """

    chat_id: Final[Column[int]] = Column(
        'ChatId',
        BigInteger,
        primary_key=True,
        key='chat_id',
    )
    message_id: Final[Column[Optional[int]]] = Column(
        'MessageId',
        Integer,
        key='message_id',
    )
    data: Final[Column[Optional[Query]]] = Column(
        'Data',
        QueryType,
        key='data',
    )
    on_response: Final[Column[Optional[Callable[..., bool]]]] = Column(
        'OnResponse',
        LocalFunction,
        key='on_response',
    )
    on_finished: Final[Column[Optional[Callable[..., T]]]] = Column(
        'OnFinished',
        LocalFunction,
        key='on_finished',
    )
    do_add_message: Final[Column[bool]] = Column(
        'DoAddMessage',
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
        key='do_add_message',
    )
    clear_used_messages: Final[Column[bool]] = Column(
        'ClearUsedMessages',
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
        key='clear_used_messages',
    )
    group: Final[Column[int]] = Column(
        'Group',
        Integer,
        nullable=False,
        default=0,
        key='group',
    )
    query_pattern: Final[Optional[str]] = Column(
        'QueryPattern',
        String,
        key='query_pattern',
    )
    user_role: Final[Column[Optional[UserRole]]] = Column(
        'UserRole',
        IntEnumColumn(UserRole),
        key='user_role',
    )
    calls_count: Final[Column[Optional[int]]] = Column(
        'CallsCount',
        Integer,
        default=1,
        key='calls_count',
    )
    action: Final[Column[Optional[str]]] = Column(
        'Action',
        String,
        key='action',
    )
    private: Final[Column[bool]] = Column(
        'Private',
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
        key='private',
    )
    replace_calls: Final[Column[bool]] = Column(
        'ReplaceCalls',
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
        key='replace_calls',
    )
    success: Final[Column[Optional[bool]]] = Column(
        'Success',
        Boolean(create_constraint=True),
        key='success',
    )
    used_messages: Final[
        'RelationshipProperty[list[InputMessageModel]]'
    ] = relationship(
        'InputMessageModel',
        back_populates='input',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
