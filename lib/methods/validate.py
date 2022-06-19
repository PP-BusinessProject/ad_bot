"""The module with the :meth:`AdBotClient.validate`."""

from typing import TYPE_CHECKING

from sqlalchemy.sql.expression import exists, select, text

from ..models.sessions.session_model import SessionModel

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient


class Validate(object):
    async def validate(self: 'AdBotClient', /) -> bool:
        """Validate the `client`."""
        if self.is_connected:
            return True
        return await self.storage.Session.scalar(
            select(
                exists(text('NULL'))
                .where(SessionModel.phone_number == self.storage.phone_number)
                .where(SessionModel.user_id.is_not(None))
            )
        )
