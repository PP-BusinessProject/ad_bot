"""The module with :class:`InputModel`."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Callable,
    Final,
    Generic,
    List,
    Optional,
    TypeVar,
)

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import BigInteger, Boolean, Integer, String

from ...utils.query import Query, QueryType
from .._types import LocalFunction
from ..base_interface import Base
from ..clients.user_model import UserModel, UserRole

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

        used_messages (``list[InputMessageModel]``):
            The messages used in this input.
    """

    chat_id: Final[Column[int]] = Column(
        BigInteger,
        primary_key=True,
    )
    message_id: Final[Column[Optional[int]]] = Column(
        Integer,
        CheckConstraint('message_id > 0'),
    )
    data: Final[Column[Optional[Query]]] = Column(QueryType)
    on_response: Final[Column[Optional[Callable[..., bool]]]] = Column(
        LocalFunction
    )
    on_finished: Final[Column[Optional[Callable[..., T]]]] = Column(
        LocalFunction,
    )
    do_add_message: Final[Column[bool]] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
    )
    clear_used_messages: Final[Column[bool]] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
    )
    group: Final[Column[int]] = Column(
        Integer,
        nullable=False,
        default=0,
    )
    query_pattern: Final[Optional[str]] = Column(String)
    user_role: Final[Column[Optional[UserRole]]] = Column(UserModel.role.type)
    calls_count: Final[Column[Optional[int]]] = Column(
        Integer,
        CheckConstraint('calls_count > 0'),
        default=1,
    )
    action: Final[Column[Optional[str]]] = Column(String)
    private: Final[Column[bool]] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
    )
    replace_calls: Final[Column[bool]] = Column(
        Boolean(create_constraint=True),
        nullable=False,
        default=False,
    )
    success: Final[Column[Optional[bool]]] = Column(
        Boolean(create_constraint=True),
    )
    used_messages: Mapped[
        'RelationshipProperty[List[InputMessageModel]]'
    ] = relationship(
        'InputMessageModel',
        back_populates='input',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )
