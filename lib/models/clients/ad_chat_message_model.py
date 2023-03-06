"""The module that provides a `AdChatMessageModel`."""

from datetime import datetime
from typing import ClassVar, Final, Optional, Self, Type

from dateutil.tz.tz import tzlocal
from pyrogram.client import Client
from pyrogram.types import Message
from sqlalchemy import CheckConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.functions import now
from sqlalchemy.sql.schema import ClauseElement, Column, ForeignKeyConstraint
from sqlalchemy.sql.sqltypes import DateTime, String

from ..base_interface import Base, TableArgs
from .ad_chat_model import AdChatModel


class AdChatMessageModel(Base):
    """
    The model of an already sent message of the advertisment.

    Parameters:
        ad_chat_id (``int``):
            The id of the chat where initial ad message belongs to.

        ad_message_id (``int``):
            The id of the initial ad message in the `ad_chat_id`.

        chat_id (``int``):
            The id of the sent message with the ad.

        message_id (``int``):
            The id of the sent message with the ad.

        link (``str``):
            The link to the sent message with the ad.

        timestamp (``datetime``):
            The date and time the sent message with the ad was sent.
    """

    ad_chat_id: Final = Column(
        AdChatModel.ad_chat_id.type,
        primary_key=True,
    )
    ad_message_id: Final = Column(
        AdChatModel.ad_chat_id.type,
        primary_key=True,
    )
    chat_id: Final = Column(
        AdChatModel.chat_id.type,
        primary_key=True,
    )
    message_id: Final[Column[int]] = Column(
        AdChatModel.ad_message_id.type,
        CheckConstraint('message_id > 0'),
        primary_key=True,
    )
    link: Final[Column[str]] = Column(
        String(255),
        CheckConstraint("link <> ''"),
        nullable=False,
    )
    timestamp: Final[Column[datetime]] = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    ad_chat: Mapped['RelationshipProperty[AdChatModel]'] = relationship(
        'AdChatModel',
        back_populates='messages',
        lazy='noload',
        cascade='save-update',
        uselist=False,
    )

    __table_args__: Final[TableArgs] = (
        ForeignKeyConstraint(
            [ad_chat_id, ad_message_id, chat_id],
            [
                AdChatModel.ad_chat_id,
                AdChatModel.ad_message_id,
                AdChatModel.chat_id,
            ],
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
    )

    @hybrid_property
    def scheduled(self: Self, /) -> bool:
        """If this instance is valid."""
        return self.timestamp > datetime.now(tzlocal())

    @scheduled.expression
    def scheduled(cls: Type[Self], /) -> ClauseElement:  # noqa: N805
        return cls.timestamp > now()

    _instance: ClassVar[Optional[Message]] = None

    @classmethod
    def from_message(
        cls: Type[Self],
        message: Message,
        /,
        ad_chat: AdChatModel,
    ) -> Self:
        """Create the used message from `message`."""
        self = cls(message_id=message.id, ad_chat=ad_chat)
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
