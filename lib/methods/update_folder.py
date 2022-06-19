"""The module with the :meth:`AdBotClient.get_folders`."""

from typing import TYPE_CHECKING

from pyrogram.raw.functions.messages.update_dialog_filter import (
    UpdateDialogFilter,
)
from pyrogram.raw.types.dialog_filter import DialogFilter

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient


class UpdateFolder(object):
    async def update_folder(
        self: 'AdBotClient',
        /,
        folder: DialogFilter,
    ) -> bool:
        """
        Return user's dialog filters.

        Args:
            folder (``DialogFilter``):
                The folder to update.

        Returns:
            A list of :class:`~pyrogram.raw.types.DialogFilter` objects.

        Raises:
            `pyrogram.errors.exceptions.bad_request_400.FilterIdInvalid`:
                If the specified filter ID is invalid.

            `pyrogram.errors.exceptions.bad_request_400.FilterIncludeEmpty`:
                If the include_peers vector of the filter is empty.

            `pyrogram.errors.exceptions.bad_request_400.FilterTitleEmpty`:
                If the title field of the filter is empty.
        """
        return await self.send(UpdateDialogFilter(id=folder.id, filter=folder))
