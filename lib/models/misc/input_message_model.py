"""The module with :class:`InputMessageModel`."""

from __future__ import annotations

from typing import Final, Optional, Type

from pyrogram.client import Client
from pyrogram.types import Message
from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer
from typing_extensions import Self

from ..base_interface import Base
from .input_model import InputModel


class InputMessageModel(Base):
    """The used message to store in the database."""

    chat_id: Final[Column[int]] = Column(
        'ChatId',
        InputModel.chat_id.type,
        ForeignKey(
            InputModel.chat_id,
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
        primary_key=True,
        key='chat_id',
    )
    message_id: Final[Column[int]] = Column(
        'MessageId',
        Integer,
        primary_key=True,
        key='message_id',
    )
    input: Final['RelationshipProperty[InputModel]'] = relationship(
        'InputModel',
        back_populates='used_messages',
        lazy='noload',
        cascade='save-update',
        order_by=message_id,
        uselist=False,
    )
    _instance: Optional[Message] = None

    @classmethod
    def from_message(
        cls: Type[Self],
        message: Message,
        /,
        input: Optional[InputModel] = None,
    ) -> Self:
        """Create the used message from `message`."""
        self = cls(chat_id=message.chat.id, message_id=message.id, input=input)
        self._instance = message
        return self

    async def get_instance(
        self: Self,
        client: Client,
        /,
        *,
        force: bool = False,
    ) -> Message:
        """
        Load and return the used message from `client`.

        Args:
            client (``Client``):
                The client used to download the used message.

            force (``bool``, *optional*):
                If the message should be reloaded anyway.

        Returns:
            The fetched message from the `client`.
        """
        if not force and self._instance is not None:
            return self._instance

        self._instance = await client.get_messages(
            self.chat_id, self.message_id
        )
        return self._instance

    @property
    def instance(self: Self, /) -> bool:
        """Return the message instance of this used message."""
        return self._instance
