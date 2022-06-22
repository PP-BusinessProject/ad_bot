"""Module for processing :class:`SERVICE` commands."""

from typing import TYPE_CHECKING, Optional, Union

from pyrogram.types.bots_and_keyboards.inline_keyboard_button import (
    InlineKeyboardButton as IKB,
)
from pyrogram.types.bots_and_keyboards.inline_keyboard_markup import (
    InlineKeyboardMarkup as IKM,
)
from pyrogram.types.messages_and_media.message import Message

from ...models.clients.ad_model import AdModel
from ...models.clients.bot_model import BotModel
from ...models.misc.input_message_model import InputMessageModel
from ...models.misc.input_model import InputModel
from ...utils.query import Query

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class ServiceValidation(object):
    async def service_validation(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        """
        Process :class:`ServiceCommands` from data.

        Args:
            chat_id (``int``):
                The id of a chat to send this message to.

            message_id (``Optional[Union[int, Message]]``, *optional*):
                The id of an already sent message to show this message in.

            data (``Optional[Query]``, *optional*):
                The data used for retrieving information with `session`.

            query_id (``Optional[int]``, *optional*):
                The id of a :class:`CallbackQuery` that has requested this
                message.

        Returns:
            * `SERVICE.HIDE`:
                If hide was successful.

            * `SERVICE.APPROVE`, `SERVICE.DENY`:
                The result of the underlying handler.

        Raises:
            ValueError, if the data argument is invalid.
        """
        if isinstance(chat_id, InputModel):
            chat_id = chat_id.chat_id
        if isinstance(_message_id := message_id, Message):
            message_id = message_id.id
        if not isinstance(data, Query):
            raise ValueError(
                '`data` argument of type `Query` must be provided.'
            )

        elif data.command == self.SERVICE.HIDE:
            if message_id is not None:
                return await self.delete_messages(chat_id, message_id)
            return False

        elif data.command in (self.SERVICE.APPROVE, self.SERVICE.DENY):
            if not data.args:
                raise ValueError('`Query` arguments must be provided.')

            elif data.args[0] in self.AD._member_map_.values():
                if data.command != self.SERVICE.APPROVE:
                    return await self.delete_messages(chat_id, message_id)

                ad = await self.storage.Session.get(AdModel, data.args[1:])
                if ad is None:
                    await self.delete_messages(chat_id, message_id)
                    return await self.answer_edit_send(
                        *(query_id, chat_id),
                        text='Объявление не найдено.',
                    )

                ad.confirm_message_id = None
                await self.storage.Session.commit()
                return (
                    await self.edit_message_text(
                        *(chat_id, message_id),
                        f'Объявление #{ad.message_id} для бота #{ad.bot_id} '
                        'подтверждено.',
                    ),
                    await self.answer_edit_send(
                        chat_id=ad.bot_owner_id,
                        text=f'Ваше объявление #{ad.message_id} подтверждено '
                        'администрацией.',
                    ),
                )

            elif data.args[0] in self.SETTINGS._member_map_.values():
                bot = await self.storage.Session.get(BotModel, data.args[1:])
                if bot is None:
                    await self.delete_messages(chat_id, message_id)
                    return await self.answer_edit_send(
                        *(query_id, chat_id),
                        text='Бот не найден.',
                    )

                if data.command == self.SERVICE.APPROVE:
                    bot.confirm_message_id = None
                    await self.storage.Session.commit()

                    if not isinstance(_message_id, Message):
                        _message_id = await self.get_messages(
                            chat_id, _message_id
                        )
                    if not _message_id.empty:
                        text = _message_id.text.markdown
                        _message_id = await _message_id.edit_text(
                            ''.join(text.splitlines(keepends=True)[:-1])
                            + 'Подтверждено.',
                        )
                    answer = await self.answer_edit_send(
                        chat_id=bot.owner.id,
                        text=f'Изменения вашего бота #{bot.id} '
                        'подтверждены администрацией.',
                    )
                    return (
                        answer if _message_id.empty else (_message_id, answer)
                    )

                input = InputModel(
                    chat_id=chat_id,
                    message_id=message_id,
                    data=data,
                    on_finished=self._service_settings_deny_reason,
                )
                self.storage.Session.add(input)
                await self.storage.Session.commit()

                used = await self.send_message(
                    chat_id,
                    'Напишите причину отклонения изменений в ответ на это '
                    'сообщение.',
                    reply_markup=IKM(
                        [
                            [
                                IKB(
                                    'Отправить без причины',
                                    self.INPUT._SELF,
                                ),
                                IKB('Отменить', self.INPUT.CANCEL),
                            ]
                        ]
                    ),
                )
                self.storage.Session.add(
                    InputMessageModel.from_message(used, input)
                )
                await self.storage.Session.commit()
                return used

            raise NotImplementedError(
                f'Command "{data.args[0]}" is not supported.'
            )
        else:
            raise NotImplementedError(
                f'Command "{data.command}" is not supported.'
            )

    async def _service_settings_deny_reason(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        """
        Deny the requested changes with or without the actual reason.

        Args:
            input (``InputModel``):
                The input that was used to ask for settings denial reason.

            chat_id (``int``):
                The id of a chat to send this message to.

            message_id (``Optional[Union[int, Message]]``, *optional*):
                The id of an already sent message to show this message in.

            data (``Optional[Query]``, *optional*):
                The data used for retrieving information with `session`.

            query_id (``Optional[int]``, *optional*):
                The id of a :class:`CallbackQuery` that has requested this
                message.

        Returns:
            The message for the settings denial.
        """
        if not isinstance(chat_id, InputModel):
            raise NotImplementedError('This method works only with inputs.')
        input, chat_id = chat_id, chat_id.chat_id
        if not input.success:
            return

        reason: str = '__Отклонено без причины.__'
        if data is None and message_id is not None:
            if not isinstance(message_id, Message):
                message_id = await self.get_messages(chat_id, message_id)
            if not message_id.empty and message_id.text:
                reason = '\n'.join(
                    ('__Отклонено по причине:__', message_id.text)
                )
        deny_message = await self.get_messages(input.chat_id, input.message_id)
        if not deny_message.empty:
            text = deny_message.text.markdown
            deny_message = await deny_message.edit_text(
                ''.join(text.splitlines(keepends=True)[:-1]) + ('\n' + reason)
            )
        answer = await self.answer_edit_send(
            *(query_id, input.data.args[0]),
            text=f'Изменения вашего бота #{input.data.args[1]} отклонены '
            'администрацией.' + ('\n\n' + reason),
        )
        return answer if deny_message.empty else (deny_message, answer)
