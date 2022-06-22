"""The module with the :meth:`AdBotClient.get_folder_by_title`."""

from typing import TYPE_CHECKING

from pyrogram.raw.types.dialog_filter import DialogFilter

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class GetFolderByTitle(object):
    async def get_folder_by_title(
        self: 'AdBotClient',
        /,
        title: str,
    ) -> DialogFilter:
        """
        Return the dialog filter matched by title.

        Args:
            title (``str``):
                The title to match with dialog filter.

        Returns:
            A :class:`~pyrogram.raw.types.DialogFilter` object with the
            matched title. Or the new empty one with correct id.
        """
        for folder in (folders := await self.get_folders()):
            if folder.title == title:
                return folder
        return DialogFilter(
            id=max(folder.id for folder in folders) + 1 if folders else 99,
            title=title,
            pinned_peers=[],
            include_peers=[],
            exclude_peers=[],
        )
