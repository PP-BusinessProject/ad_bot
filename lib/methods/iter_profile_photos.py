"""The module with the :meth:`AdBotClient.iter_profile_photos`."""

from typing import AsyncGenerator, Optional, Union

from pyrogram import types
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient


class IterProfilePhotos(object):
    async def iter_profile_photos(
        self: 'AdBotClient',
        chat_id: Union[int, str],
        offset: int = 0,
        limit: int = 0,
    ) -> Optional[AsyncGenerator["types.Photo", None]]:
        """
        Iterate through a chat or a user profile photos sequentially.

        This convenience method does the same as repeatedly calling
        :meth:`~pyrogram.Client.get_profile_photos` in a loop, thus saving you
        from the hassle of setting up boilerplate code. It is useful for
        getting all the profile photos with a single call.

        Args:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use
                "me" or "self". For a contact that exists in your Telegram
                address book you can use his phone number (str).

            limit (``int``, *optional*):
                Limits the number of profile photos to be retrieved.
                By default, no limit is applied and all profile photos are
                returned.

            offset (``int``, *optional*):
                Sequential number of the first profile photo to be returned.

        Returns:
            A generator yielding :obj:`~pyrogram.types.Photo` objects.

        Example:
            .. code-block:: python

                for photo in app.iter_profile_photos("me"):
                    print(photo.file_id)
        """
        current = 0
        total = limit or (1 << 31)
        limit = min(100, total)

        while True:
            photos = await self.get_profile_photos(chat_id, offset, limit)
            for photo in photos:
                yield photo
                if (current := current + 1) >= total:
                    return
            if len(photos) < limit:
                return
            offset += len(photos)
