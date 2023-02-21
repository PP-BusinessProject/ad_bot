"""The module that provides a `BotModel`."""

from typing import TYPE_CHECKING, Final, List, Optional, Self, Type

from sqlalchemy import CheckConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import Mapped
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.expression import ClauseElement
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer, String

from .._constraints import MAX_NAME_LENGTH, MAX_USERNAME_LENGTH
from .._mixins import Timestamped
from ..base_interface import Base
from ..bots.client_model import ClientModel
from .user_model import UserModel

if TYPE_CHECKING:
    from .ad_model import AdModel


class BotModel(Timestamped, Base):
    """
    The model that represents a worker bot.

    Parameters:
        id (``int``):
            The id of this bot in the database.

        owner_id (``int``):
            The id of the owner of this bot.

        forward_to_id (``int``):
            The id of a user that will receive responses sent to this bot.

        reply_text (``str``):
            The text of the response that will be sent to a user that initiates
            a contact with this bot.

        first_name (``str``):
            The first name of this bot.

        last_name (``Optional[str]``):
            The last name of this bot. May be omitted.

        username (``Optional[str]``):
            The username of this bot. Starts with @. May be omitted.

        about (``str``, *optional*):
            The biography of this bot. May be omitted.

        avatar_message_id (``Optional[int]``):
            The id of the message that contains the avatar in this bot's
            service channel.

        phone_number (``Optional[int]``):
            The phone number of the :class:`ClientModel` asssigned to
            this bot.

        confirm_message_id (``Optional[int]``):
            The id of the current message that confirmes this bot in this bot
            owner's service channel.

        confirmed (``bool``):
            If this bot was confirmed by administration.

        active (``bool``):
            If this bot is currently active for mailing.

        banned (``bool``):
            If this bot can be mailing at all. Can only be edited by
            administrator.

        created_at (``datetime``):
            The date and time this model was added to the database.

        updated_at (``datetime``):
            The date and time of the last time this model was updated in the
            database.

        ads (``list[AdModel]``):
            The ads that belong to this bot. If any were fetched yet.
    """

    owner_id: Final = Column(
        UserModel.id.type,
        ForeignKey(UserModel.id, onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True,
    )
    id: Final[Column[int]] = Column(
        Integer,
        CheckConstraint('id >= 0'),
        primary_key=True,
        autoincrement=True,
    )
    forward_to_id: Final = Column(
        UserModel.id.type,
        nullable=False,
    )
    reply_message_id: Final[Column[Optional[int]]] = Column(
        Integer,
        CheckConstraint('reply_message_id > 0'),
    )
    first_name: Final[Column[str]] = Column(
        String(MAX_NAME_LENGTH),
        CheckConstraint("first_name <> ''"),
        nullable=False,
        default='Бот',
    )
    last_name: Final[Column[Optional[str]]] = Column(
        String(MAX_NAME_LENGTH),
        CheckConstraint("last_name <> ''"),
    )
    username: Final[Column[Optional[str]]] = Column(
        String(MAX_USERNAME_LENGTH),
        CheckConstraint("username <> ''"),
        unique=True,
    )
    about: Final[Column[Optional[str]]] = Column(
        String(70),
        CheckConstraint("about <> ''"),
    )
    avatar_message_id: Final[Column[Optional[int]]] = Column(
        Integer,
        CheckConstraint('avatar_message_id > 0'),
    )
    phone_number: Final[Column[Optional[int]]] = Column(
        ForeignKey(
            ClientModel.phone_number,
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
        unique=True,
        index=True,
    )
    confirm_message_id: Column[Optional[int]] = Column(
        Integer,
        CheckConstraint('confirm_message_id > 0'),
    )
    owner: Mapped['RelationshipProperty[UserModel]'] = relationship(
        'UserModel',
        back_populates='bots',
        lazy='joined',
        cascade='save-update',
        uselist=False,
    )
    sender_client: Mapped['RelationshipProperty[ClientModel]'] = relationship(
        'ClientModel',
        back_populates='owner_bot',
        lazy='noload',
        cascade='save-update',
        uselist=False,
    )
    ads: Mapped['RelationshipProperty[List[AdModel]]'] = relationship(
        'AdModel',
        back_populates='owner_bot',
        lazy='noload',
        cascade='save-update, merge, expunge, delete, delete-orphan',
        uselist=True,
    )

    @hybrid_property
    def confirmed(self: Self, /) -> bool:
        """If this instance is marked as confirmed."""
        return self.confirm_message_id is None

    @confirmed.expression
    def confirmed(cls: Type[Self], /) -> ClauseElement:  # noqa: N805
        return cls.confirm_message_id.is_(None)
