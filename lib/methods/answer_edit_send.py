"""The module with the :meth:`AdBotClient.answer_edit_send`."""

from typing import TYPE_CHECKING, Optional, Union

from pyrogram.types.bots_and_keyboards.inline_keyboard_button import (
    InlineKeyboardButton as IKB,
)
from pyrogram.types.bots_and_keyboards.inline_keyboard_markup import (
    InlineKeyboardMarkup as IKM,
)
from pyrogram.types.messages_and_media.message import Message

from ..utils.query import Query

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient


class AnswerEditSend(object):
    async def answer_edit_send(
        self: 'AdBotClient',
        /,
        query_id: Optional[int] = None,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        back_data: Optional[Query] = None,
        text: Optional[str] = None,
        *,
        show_alert: bool = False,
    ) -> Union[bool, Message]:
        """
        Answer the :class:`CallbackQuery` or edit/send the :class:`Message`.

        Args:
            query_id (``Optional[int]``, *optional*):
                The id of the :class:`CallbackQuery` to answer.

            chat_id (``Optional[int]``, *optional*):
                The id of the :class:`Chat` to send the :class:`Message` to.

            message_id (``Optional[int]``, *optional*):
                The id of the :class:`Message` to edit in the chat by
                `chat_id`.

            back_data (``Optional[Query]``, *optional*):
                The data to send with the edited :class:`Message`.

            text (``Optional[str]``, *optional*):
                The text of the :class:`CallbackQuery` answer, or the
                edited/sent :class:`Message`.

            show_alert (``bool``, *optional*):
                If an alert will be shown by the `self` instead of
                notification.

        Returns:
            If the :class:`CallbackQuery` was answered successfully, or the
            :class:`Message` that was sent or edited.

        Raises:
            ValueError, if the `chat_id` is invalid.
        """
        try:
            if not isinstance(query_id, (str, int)):
                raise ValueError(
                    f'query_id of type "{type(message_id)}" should be of type '
                    'int or str.'
                )
            answer = self.answer_callback_query
            return bool(await answer(query_id, text, show_alert=show_alert))
        except ValueError as exception:
            if not text:
                return False
            try:
                if not isinstance(chat_id, int):
                    raise ValueError(
                        f'chat_id of type "{type(chat_id)}" should be of type '
                        'int.'
                    ) from exception
                if not isinstance(message_id, int):
                    raise ValueError(
                        f'message_id of type "{type(message_id)}" should be '
                        'of type int.'
                    ) from exception
                return await self.edit_message_text(
                    *(chat_id, message_id, text),
                    reply_markup=IKM([[IKB('Назад', back_data)]])
                    if back_data is not None
                    else None,
                )
            except ValueError as exception:
                if not isinstance(chat_id, int):
                    raise ValueError(
                        f'chat_id of type "{type(chat_id)}" should be of type '
                        'int.'
                    ) from exception
                _ = IKM([[IKB('Скрыть', self.SERVICE.HIDE)]])
                return await self.send_message(chat_id, text, reply_markup=_)
