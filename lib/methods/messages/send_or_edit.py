"""The module with the :meth:`AdBotClient.send_or_edit`."""

from typing import TYPE_CHECKING, Optional, Union

from pyrogram.enums.parse_mode import ParseMode
from pyrogram.errors.exceptions.bad_request_400 import (
    MediaPrevInvalid,
    MessageEditTimeExpired,
    MessageIdInvalid,
    MessageNotModified,
    MsgIdInvalid,
)
from pyrogram.types.bots_and_keyboards.inline_keyboard_button import (
    InlineKeyboardButton as IKB,
)
from pyrogram.types.bots_and_keyboards.inline_keyboard_markup import (
    InlineKeyboardMarkup as IKM,
)
from pyrogram.types.messages_and_media.message import Message
from pyrogram.types.messages_and_media.message_entity import MessageEntity

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class SendOrEdit(object):
    async def send_or_edit(
        self: 'AdBotClient',
        /,
        chat_id: int,
        message_id: Optional[int],
        text: str,
        parse_mode: Optional[ParseMode] = None,
        entities: list[MessageEntity] = None,
        disable_web_page_preview: bool = None,
        reply_markup: Union[IKM, list[list[IKB]]] = None,
    ) -> Optional[Message]:
        """
        Edit or send a new message if an edit fails due to unimportant reasons.

        Args:
            chat_id (``int``):
                The id of a chat to send or edit message at.

            message_id(``Optional[int]``):
                The id of a message to edit. If None, just sends the message.

        Returns:
            The message that was sent or edited.
            Or None, if message was not modified.
        """
        if isinstance(message_id, int):
            try:
                return await self.edit_message_text(
                    *(chat_id, message_id),
                    text=text,
                    parse_mode=parse_mode,
                    entities=entities,
                    disable_web_page_preview=disable_web_page_preview,
                    reply_markup=IKM(reply_markup)
                    if isinstance(reply_markup, list)
                    else reply_markup,
                )
            except MessageNotModified:
                return None
            except (
                MessageEditTimeExpired,
                MessageIdInvalid,
                MsgIdInvalid,
                MediaPrevInvalid,
            ):
                pass

        return await self.send_message(
            chat_id,
            text=text,
            parse_mode=parse_mode,
            entities=entities,
            disable_web_page_preview=disable_web_page_preview,
            reply_markup=IKM(reply_markup)
            if isinstance(reply_markup, list)
            else reply_markup,
        )
