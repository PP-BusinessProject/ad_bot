"""The module with the :meth:`AdBotClient.get_folders`."""

from pyrogram.raw.base.dialog_filter import DialogFilter as RawDialogFilter
from pyrogram.raw.functions.messages.get_dialog_filters import GetDialogFilters
from pyrogram.raw.types.dialog_filter import DialogFilter
from pyrogram.types.list import List

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class GetFolders(object):
    async def get_folders(self: 'AdBotClient', /) -> list[DialogFilter]:
        """
        Return user's dialog filters.

        Returns:
            A list of :class:`~pyrogram.raw.types.DialogFilter` objects.
        """
        response: List[RawDialogFilter] = await self.invoke(GetDialogFilters())
        return [d for d in response if isinstance(d, DialogFilter)]
