"""The module for processing ServiceCommands."""

from ast import literal_eval
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Optional, Union

from pyrogram.errors.rpc_error import RPCError
from pyrogram.types import KeyboardButton as KB
from pyrogram.types import ReplyKeyboardMarkup as RKM
from pyrogram.types.bots_and_keyboards.inline_keyboard_button import (
    InlineKeyboardButton as IKB,
)
from pyrogram.types.bots_and_keyboards.inline_keyboard_markup import (
    InlineKeyboardMarkup as IKM,
)
from pyrogram.types.messages_and_media.message import Message
from sqlalchemy.sql.expression import exists, select, text

from ...models.bots.client_model import ClientModel
from ...models.clients.user_model import UserModel
from ...models.misc.input_message_model import InputMessageModel
from ...models.misc.input_model import InputModel
from ...models.sessions.session_model import SessionModel
from ...utils.pyrogram import auto_init
from ...utils.query import Query

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class ServiceHelp(object):
    async def service_help(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        """
        Approve or deny help request in the service chat.

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
            If the :meth:`CallbackQuery.answer` was successful, and the
            messages used in the service and/or user chats.
        """

        async def abort(
            text: str,
            /,
            *,
            show_alert: bool = True,
        ) -> Union[bool, Message]:
            nonlocal self, query_id, chat_id
            return await self.answer_edit_send(
                *(query_id, chat_id),
                text=text,
                show_alert=show_alert,
            )

        async def abort_not_found() -> Union[bool, Message]:
            if data is None or data.args and data.args[0] == chat_id:
                return await self.answer_edit_send(
                    chat_id=chat_id,
                    text='Вы не зарегистрированы, чтобы зарегистрироваться '
                    'напишите **/start**.',
                )
            elif data.args:
                return await abort('Пользователь не найден.')
            else:
                return await abort('Произошла ошибка.')

        if isinstance(chat_id, InputModel):
            chat_id = chat_id.chat_id
        if isinstance(message_id, Message):
            message_id = message_id.id

        if data is None or data.command == self.HELP._SELF:
            user: UserModel = await self.storage.Session.get(
                UserModel, chat_id
            )
            if user is None:
                return await abort_not_found()

            help_message = user.service_id, user.help_message_id
            if all(_ is not None for _ in help_message):
                help_message = await self.get_messages(*help_message)
                if not help_message.empty:
                    return await self.send_or_edit(
                        *(chat_id, message_id),
                        'Вы уже оставили заявку на связь с администрацией.',
                        reply_markup=IKM(
                            [
                                [
                                    IKB(
                                        'Отменить заявку',
                                        Query(self.HELP.CANCEL, chat_id),
                                    )
                                ]
                            ]
                        ),
                    )

            input = InputModel(
                chat_id=chat_id,
                message_id=message_id,
                data=data or Query(self.HELP._SELF, chat_id),
                on_response=self._service_help,
                on_finished=self._service_help_finished,
            )
            self.storage.Session.add(input)
            await self.storage.Session.commit()

            async def send_used_message(*args: Any, **kwargs: Any) -> Message:
                used = await self.send_message(chat_id, *args, **kwargs)
                self.storage.Session.add(
                    InputMessageModel.from_message(used, input)
                )
                return used

            try:
                return (
                    await send_used_message(
                        'Чтобы связаться с администрацией пришлите ваш '
                        'контакт с помощью кнопки ниже или вручную.',
                        reply_markup=RKM(
                            [[KB('Прислать контакт', request_contact=True)]],
                            resize_keyboard=True,
                        ),
                    ),
                    await send_used_message(
                        'Вы также можете написать ваши вопросы в ответ к '
                        'этому сообщению.',
                        reply_markup=IKM([[IKB('Отмена', self.INPUT.CANCEL)]]),
                    ),
                )
            finally:
                await self.storage.Session.commit()

        elif data.command == self.HELP.ANSWER:
            user = await self.storage.Session.scalar(
                select(UserModel).filter_by(service_id=chat_id)
            )
            if user is None:
                with suppress(RPCError):
                    await self.delete_messages(chat_id, message_id)
                return await abort_not_found()

            help_closed = await self.send_message(
                chat_id,
                f'Заявка для [пользователя](tg://user?id={user.id}) '
                'успешно закрыта.',
                reply_to_message_id=user.help_message_id,
            )
            if user.help_message_id is not None:
                user.help_message_id = None
                await self.storage.Session.commit()
            return (
                await self.answer_edit_send(
                    chat_id=user.id,
                    text='Ваша заявка была закрыта администрацией.',
                ),
                await self.edit_message_reply_markup(chat_id, message_id),
                help_closed,
            )

        elif data.command == self.HELP.CANCEL:
            with suppress(RPCError):
                await self.delete_messages(chat_id, message_id)

            user = await self.storage.Session.get(UserModel, chat_id)
            if user is None:
                return await abort_not_found()

            elif user.help_message_id is None:
                return await abort(
                    '\n'.join(
                        (
                            'Ваша заявка уже отменена.',
                            'Чтобы оставить новую заявку воспользуйтесь меню '
                            'ниже.',
                        )
                    )
                )

            help_message_id = int(user.help_message_id)
            user.help_message_id = None
            await self.storage.Session.commit()

            return (
                await abort(
                    '\n'.join(
                        (
                            'Ваша заявка успешно отменена.',
                            'Чтобы оставить новую заявку воспользуйтесь меню '
                            'ниже.',
                        )
                    )
                ),
                await self.edit_message_reply_markup(
                    user.service_id, help_message_id
                ),
                await self.send_message(
                    user.service_id,
                    f'[Пользователь](tg://user?id={user.id}) отменил заявку.',
                    reply_to_message_id=help_message_id,
                ),
            )

        else:
            raise NotImplementedError(
                f'Command {data.command} is not supported.'
            )

    async def _service_help(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> bool:
        """Write down user questions and contact for his request."""

        async def abort(
            text: str,
            /,
            *,
            add: bool = False,
            show_alert: bool = True,
        ) -> bool:
            nonlocal self, query_id, chat_id, input
            message = await self.answer_edit_send(
                *(query_id, chat_id),
                text=text,
                show_alert=show_alert,
            )
            if add and isinstance(message, Message):
                self.storage.Session.add(
                    InputMessageModel.from_message(message, input)
                )
                await self.storage.Session.commit()
            return not add

        if not isinstance(chat_id, InputModel):
            return await abort(
                'Связаться с администрацией можно только через сообщение.'
            )
        input, chat_id = chat_id, chat_id.chat_id

        if message_id is None:
            return True
        elif not isinstance(message := message_id, Message):
            message = await self.get_messages(chat_id, message_id)

        if message.contact is None:
            if not message.text:
                return await abort(
                    'Контакт не найден. Попробуйте еще раз.',
                    add=True,
                )

            qs = literal_eval(input.data.kwargs.get('questions', str(())))
            qs += (message.text,)
            input.data = input.data(
                kwargs=input.data.kwargs | dict(questions=qs)
            )
            return await abort(
                f'Ваш вопрос записан. Всего вопросов: {len(qs)}.',
                add=True,
            )

        elif message.contact.user_id != chat_id:
            return await abort(
                'Это не ваш контакт. Повторите попытку.',
                add=True,
            )

        user = await self.storage.Session.get(UserModel, chat_id)
        if user is None:
            return await abort(
                'Вы не зарегистрированы, чтобы зарегистрироваться '
                'напишите **/start**.',
            )

        phone_number: int
        async for phone_number in (
            await self.storage.Session.stream_scalars(
                select(ClientModel.phone_number)
                .where(ClientModel.valid)
                .where(
                    exists(text('NULL')).where(
                        (SessionModel.phone_number == ClientModel.phone_number)
                        & SessionModel.user_id
                        == chat_id
                    )
                )
                .order_by(ClientModel.created_at)
            )
        ):
            async with auto_init(self.get_worker(phone_number)) as worker:
                with suppress(RPCError):
                    user = await self.storage.Session.merge(
                        await worker.initialize_user_service(
                            user, promote_users=self.username
                        )
                    )
                    await self.storage.Session.commit()
                    break
        else:
            return await abort(
                'На данный момент нет свободного бота для создания '
                'вашего личного канала. Попробуйте еще раз позже.'
            )

        await message.copy(user.service_id)
        help_message = await self.send_message(
            user.service_id,
            '\n\n'.join(
                _
                for _ in (
                    f'[Пользователь](tg://user?id={user.id}) хочет связаться '
                    'с администрацией.',
                    '\n'.join(
                        (
                            'Список вопросов:',
                            '\n'.join(
                                ('. ' if '\n' not in value else '.\n').join(
                                    map(str, (i, value))
                                )
                                for i, value in enumerate(
                                    literal_eval(
                                        input.data.kwargs.get(
                                            'questions', str(())
                                        )
                                    ),
                                    1,
                                )
                            ),
                        )
                    )
                    if 'questions' in input.data.kwargs
                    else None,
                )
                if _ is not None
            ),
            reply_markup=IKM(
                [[IKB('Закрыть заявку', input.data(self.HELP.ANSWER))]],
            ),
        )
        user.help_message_id = help_message.id
        await self.storage.Session.commit()
        return True

    async def _service_help_finished(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        async def abort(
            text: str,
            /,
            *,
            show_alert: bool = True,
        ) -> Union[bool, Message]:
            nonlocal self, query_id, chat_id
            return await self.answer_edit_send(
                *(query_id, chat_id),
                text=text,
                show_alert=show_alert,
            )

        input: Optional[InputModel] = None
        if isinstance(chat_id, InputModel):
            input, chat_id = chat_id, chat_id.chat_id

        return (
            (
                await abort(
                    'Вы успешно оставили заявку на связь с администрацией.'
                ),
                await self.start_message(
                    input or chat_id, message_id, data, query_id
                ),
            )
            if input.success
            else await abort('Заявка не была оставлена.')
        )
