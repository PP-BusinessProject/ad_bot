"""The module with the :meth:`AdBotClient.iter_dialogs`."""

from typing import TYPE_CHECKING, AsyncGenerator, Optional

from pyrogram.raw.functions.messages.get_dialogs import GetDialogs
from pyrogram.raw.types.dialog import Dialog as RawDialog
from pyrogram.raw.types.input_peer_empty import InputPeerEmpty
from pyrogram.raw.types.message_empty import MessageEmpty
from pyrogram.types.messages_and_media.message import Message
from pyrogram.types.user_and_chats.dialog import Dialog
from pyrogram.utils import get_peer_id

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class IterDialogs(object):
    async def iter_dialogs(
        self: 'AdBotClient',
        /,
        limit: int = 0,
        *,
        exclude_pinned: Optional[bool] = None,
        folder_id: Optional[int] = None,
    ) -> AsyncGenerator[Dialog, None]:
        """
        Iterate through a user's dialogs sequentially.

        This convenience method does the same as repeatedly calling
        :meth:`~pyrogram.Client.get_dialogs` in a loop, thus saving you from
        the hassle of setting up boilerplate code. It is useful for getting
        the whole dialogs list with a single call.

        Args:
            limit (``int``, *optional*):
                Limits the number of dialogs to be retrieved.
                By default, no limit is applied and all dialogs are returned.

            exclude_pinned (``Optional[bool]``, *optional*):
                If the pinned dialogs should be excluded.

            folder_id (``Optional[int]``, *optional*):
                The peer folder id to filter dialogs from.

        Returns:
            A generator yielding :class:`~pyrogram.types.Dialog` objects.

        Example:
            .. code-block:: python

                # Iterate through all dialogs
                for dialog in app.iter_dialogs():
                    print(dialog.chat.first_name or dialog.chat.title)
        """
        total = limit or (1 << 31) - 1
        limit = min(100, total)
        current, offset_date, offset_id, offset_peer = 0, 0, 0, None

        while True:
            response = await self.invoke(
                GetDialogs(
                    offset_date=offset_date,
                    offset_id=offset_id,
                    offset_peer=offset_peer or InputPeerEmpty(),
                    limit=limit,
                    hash=0,
                    exclude_pinned=exclude_pinned or None,
                    folder_id=folder_id,
                ),
                sleep_threshold=60,
            )

            users = {user.id: user for user in response.users}
            chats = {chat.id: chat for chat in response.chats}
            messages = {
                get_peer_id(message.peer_id): await Message._parse(
                    self, message, users, chats
                )
                for message in response.messages
                if not isinstance(message, MessageEmpty)
            }

            dialog = None
            for dialog in response.dialogs:
                if not isinstance(dialog, RawDialog):
                    dialog = None
                    continue
                peer = dialog.peer
                dialog = Dialog._parse(self, dialog, messages, users, chats)
                dialog.peer = peer
                yield dialog
                if (current := current + 1) >= total:
                    break
            else:
                if len(response.dialogs) >= limit:
                    offset_id = dialog.top_message.id
                    offset_date = int(dialog.top_message.date.timestamp())
                    offset_peer = await self.resolve_peer(dialog.chat.id)
                    continue
            break
