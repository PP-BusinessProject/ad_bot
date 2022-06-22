"""The module to work with `SenderBotCommands`."""

from contextlib import suppress
from re import sub
from typing import TYPE_CHECKING, Any, Optional, Union

from pyrogram.errors import (
    BadRequest,
    FloodWait,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
)
from pyrogram.errors.rpc_error import RPCError
from pyrogram.types import InlineKeyboardButton as IKB
from pyrogram.types import InlineKeyboardMarkup as IKM
from pyrogram.types import Message, TermsOfService, User
from sqlalchemy.sql.expression import exists, select, text
from sqlalchemy.sql.functions import count

from ...models._constraints import MAX_NAME_LENGTH
from ...models.bots.chat_model import ChatModel
from ...models.bots.client_model import ClientModel
from ...models.clients.user_model import UserRole
from ...models.misc.input_message_model import InputMessageModel
from ...models.misc.input_model import InputModel
from ...models.misc.settings_model import SettingsModel
from ...utils.pyrogram import auto_init
from ...utils.query import Query

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class ClientMessage(object):
    async def clients_list(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        """Send a list of sender clients on a page."""
        if isinstance(chat_id, InputModel):
            chat_id = chat_id.chat_id
        if isinstance(message_id, Message):
            message_id = message_id.id

        page_index = data.kwargs.get('p') if data is not None else None
        if not isinstance(page_index, int):
            page_index = 0

        clients_count: int = await self.storage.Session.scalar(
            select(count()).select_from(ClientModel)
        )
        if not clients_count:
            return await self.answer_edit_send(
                *(query_id, chat_id),
                text='На данный момент нет ботов для рассылки.',
                show_alert=True,
            )

        page_list_size: int = await self.storage.Session.scalar(
            select(SettingsModel.page_list_size).where(
                SettingsModel.id.is_(True)
            )
        )
        total_pages: int = -(-clients_count // page_list_size)
        return await self.send_or_edit(
            *(chat_id, message_id),
            'Список ботов для рассылки. Всего {count} {word}.'.format(
                count=clients_count,
                word=self.morph.plural(clients_count, 'бот'),
            ),
            reply_markup=IKM(
                [
                    [
                        IKB(
                            ' '.join(
                                (
                                    '✅' if sender_active else '❌',
                                    str(sender_phone_number),
                                )
                            ),
                            Query(
                                self.SENDER_CLIENT.PAGE,
                                sender_phone_number,
                                p=page_index,
                            ),
                        )
                    ]
                    async for (
                        sender_phone_number,
                        sender_active,
                    ) in await self.storage.Session.stream(
                        select(ClientModel.phone_number, ClientModel.active)
                        .order_by(ClientModel.created_at)
                        .slice(
                            min(page_index, total_pages - 1) * page_list_size,
                            min(page_index + 1, total_pages) * page_list_size,
                        )
                    )
                ]
                + self.hpages(
                    page_index,
                    total_pages,
                    Query(self.SENDER_CLIENT.LIST),
                    kwarg='p',
                )
                + [[IKB('Назад', Query(self.SERVICE._SELF))]]
            ),
        )

    async def client_message(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        """Return the page for sender self."""
        if isinstance(chat_id, InputModel):
            chat_id = chat_id.chat_id
        if isinstance(message_id, Message):
            message_id = message_id.id

        async def abort(
            text: str,
            /,
            *,
            show_alert: bool = False,
        ) -> Union[bool, Message]:
            return await self.answer_edit_send(
                *(query_id, chat_id),
                text=text,
                show_alert=show_alert,
            )

        if data is None or data.command == self.SENDER_CLIENT._SELF:
            if await self.storage.Session.scalar(
                select(
                    exists(text('NULL')).where(InputModel.chat_id == chat_id)
                )
            ):
                return await abort('Вы уже добавляете бота.', show_alert=True)

            input = InputModel(
                chat_id=chat_id,
                message_id=message_id,
                data=data,
                on_response=self._add_client,
                on_finished=self._add_client_on_finished,
                user_role=UserRole.SUPPORT,
                query_pattern='|'.join(
                    (
                        self.SENDER_CLIENT.AUTH_SEND_SMS,
                        self.SENDER_CLIENT.AUTH_RECOVER_PASSWORD,
                        self.SENDER_CLIENT.AUTH_SKIP_LAST_NAME,
                        self.SENDER_CLIENT.AUTH_REGISTER_APPROVE,
                        self.SENDER_CLIENT.AUTH_REGISTER_RETRY,
                    )
                ),
            )
            self.storage.Session.add(input)
            await self.storage.Session.commit()
            return await self.send_or_edit(
                *(chat_id, message_id),
                'Введите номер телефона аккаунта для бота.',
                reply_markup=IKM(
                    [[IKB('Отменить', Query(self.INPUT.CANCEL))]]
                ),
            )

        sender = await self.storage.Session.get(ClientModel, data.args)
        if sender is None:
            if message_id is not None:
                await self.delete_messages(chat_id, message_id)
            return await abort('Бот не найден.', show_alert=True)

        elif data.command == self.SENDER_CLIENT.REFRESH:
            sender_client = self.get_worker(sender.phone_number)
            if not await sender_client.validate():
                return await abort(
                    'Не удалось обновить статус бота.', show_alert=True
                )

            async with auto_init(sender_client):
                me = await sender_client.get_me()
            sender.restricted = me.is_restricted
            sender.scam = me.is_scam
            sender.fake = me.is_fake
            sender.deleted = me.is_deleted
            await self.storage.Session.commit()

        elif data.command == self.SENDER_CLIENT.ACTIVE:
            if sender.active or (
                await self.get_worker(sender.phone_number).validate()
            ):
                sender.active = not sender.active
                await self.storage.Session.commit()
            else:
                return await abort(
                    'Бот не валиден. Повторите попытку еще раз.',
                    show_alert=True,
                )

        elif data.command == self.SENDER_CLIENT.WARMUP:
            sender.warmup = not sender.warmup
            await self.storage.Session.commit()

        elif data.command == self.SENDER_CLIENT.WARMUP_STATUS:
            sender_client = self.get_worker(sender.phone_number)
            if not await sender_client.validate():
                return await abort(
                    'Не удалось получить статус прогрева для бота.',
                    show_alert=True,
                )

            chat_ids: list[int] = await self.storage.Session.scalars(
                select(ChatModel.id)
            )
            if not (chat_ids := chat_ids.all()):
                return await abort('Нет чатов для прогрева.', show_alert=True)

            async with auto_init(sender_client):
                chat_dialogs = await sender_client.get_peer_dialogs(chat_ids)
                valid = sum(d.top_message is not None for d in chat_dialogs)
                word = self.morph.plural(len(chat_ids), 'чат', case='gent')
                return await abort(
                    f'Прогрето {valid} из {len(chat_ids)} {word}.',
                    show_alert=True,
                )

        elif data.command == self.SENDER_CLIENT.DELETE:
            await self.storage.Session.delete(sender)
            await self.storage.Session.commit()
            return await self.clients_list(chat_id, message_id, data, query_id)

        return await self.send_or_edit(
            *(chat_id, message_id),
            text='\n'.join(
                _
                for _ in (
                    '**__Бот [+{phone}](t.me/+{phone})__**'.format(
                        phone=sender.phone_number,
                    ),
                    '',
                    '**Текущий владелец:** '
                    + (
                        '[{user}](tg://user?id={id})'.format(
                            id=sender.owner_bot.owner.id,
                            user='вы'
                            if sender.owner_bot.owner.id == chat_id
                            else 'пользователь',
                        )
                        if sender.owner_bot is not None
                        else 'Отсутствует'
                    ),
                    '**Статус:** '
                    + ('Активен' if sender.active else 'Неактивен'),
                    '**Прогрев:** '
                    + ('Включен' if sender.warmup else 'Отключен'),
                    '**Имеет ограничения:** '
                    + (
                        ('Да' if sender.restricted else 'Нет')
                        if sender.restricted is not None
                        else '__Нет информации__'
                    ),
                    '**Помечен как мошенник:** '
                    + (
                        ('Да' if sender.scam else 'Нет')
                        if sender.scam is not None
                        else '__Нет информации__'
                    ),
                    '**Помечен как фейк:** '
                    + (
                        ('Да' if sender.fake else 'Нет')
                        if sender.fake is not None
                        else '__Нет информации__'
                    ),
                    '**Удален:** '
                    + (
                        ('Да' if sender.deleted else 'Нет')
                        if sender.deleted is not None
                        else '__Нет информации__'
                    ),
                    '__Добавлен:__ '
                    + sender.created_at.astimezone().strftime(
                        r'%Y-%m-%d %H:%M:%S'
                    )
                    if sender.created_at is not None
                    else None,
                    '__Обновлен:__ '
                    + sender.updated_at.astimezone().strftime(
                        r'%Y-%m-%d %H:%M:%S'
                    )
                    if sender.updated_at is not None
                    else None,
                )
                if _ is not None
            ),
            reply_markup=IKM(
                [
                    [
                        IKB('Обновить', data(self.SENDER_CLIENT.REFRESH)),
                        IKB(
                            'Выключить для рассылки'
                            if sender.active
                            else 'Включить для рассылки',
                            data(self.SENDER_CLIENT.ACTIVE),
                        ),
                    ],
                    [
                        IKB(
                            'Статус прогрева',
                            data(self.SENDER_CLIENT.WARMUP_STATUS),
                        ),
                        IKB(
                            'Отключить прогрев'
                            if sender.warmup
                            else 'Включить прогрев',
                            data(self.SENDER_CLIENT.WARMUP),
                        ),
                    ],
                    [IKB('Удалить бота', data(self.SENDER_CLIENT.DELETE))],
                    [IKB('Назад', data(self.SENDER_CLIENT.LIST))],
                ]
            ),
        )

    async def _add_client(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> bool:
        """
        Add a `ClientModel` from the `input` to the database.

        Steps:
        1. Receive a phone number.
            1. Check for phone number validity.

        2. Initialize a self.
            1. If client is valid, check if it is in the database. *optional*
                1. If the client is in the database, ask for another self.
                2. If client was not in the database, add it automatically.

        3. Receive a code in the app OR receive code via sms for the self.
            1. Check for code validity.
            2. If code is valid, authorize a self.
            3. Check for the client's password. *optional*
                1. Check for the client's password validity.
                    OR
                    1. Restore the client's password.
                    2. Check the confirmation code from email.

        4. If the client is not registered. *optional*
            1. Ask the First Name of the self.
            2. Ask the Last Name of the self.
            3. Confirm the received name.
            4. Enter the name again. *optional*
            5. Register the client with the given name.

        5. Add the client to the database.
        """
        if not isinstance(chat_id, InputModel):
            raise NotImplementedError('This method works only with inputs.')
        input, chat_id = chat_id, chat_id.chat_id

        async def abort(text: str, /, *, add: bool = True) -> bool:
            used = await self.answer_edit_send(query_id, chat_id, text=text)
            if add and isinstance(used, Message):
                self.storage.Session.add(
                    InputMessageModel.from_message(used, input)
                )
                await self.storage.Session.commit()
            return not add

        def modify_kwargs(*keys: str, **kwargs: Any) -> None:
            input.data = input.data(
                kwargs={
                    k: v for k, v in input.data.kwargs.items() if k not in keys
                }
                | kwargs
            )

        sender, phone_number = None, input.data.kwargs.get('phone_number')
        if isinstance(phone_number, int):
            sender = self.get_worker(phone_number)

        # MIDSTEPS: OR
        if data is not None:
            # STEP 3.3.2.1: Restore the client's password
            if data.command == self.SENDER_CLIENT.AUTH_RECOVER_PASSWORD:
                try:
                    async with auto_init(
                        sender, only_connect=True, stop=False
                    ):
                        modify_kwargs(email=await sender.send_recovery_code())
                        await self.storage.Session.commit()
                except BadRequest:
                    return await abort(
                        'У данного аккаунта нет прикрепленной почты для '
                        'восстановления пароля. Попробуйте еще раз.'
                    )
                else:
                    await self.answer_callback_query(query_id)
                    await self.answer_edit_send(
                        chat_id=input.chat_id,
                        message_id=input.data.kwargs.get('email_msg_id'),
                        text='Введите код восстановления пароля с адреса '
                        f"__{input.data.kwargs['email']}__.",
                    )

            # STEP 3: Receive a confirmation code via sms
            elif 'phone_code_type' in input.data.kwargs and (
                'phone_code_hash' in input.data.kwargs
                and input.data.kwargs['phone_code_type'] != 'sms'
                and data.command == self.SENDER_CLIENT.AUTH_SEND_SMS
            ):
                try:
                    async with auto_init(
                        sender, only_connect=True, stop=False
                    ):
                        sent_code = await sender.resend_code(
                            str(input.data.kwargs['phone_number']),
                            input.data.kwargs['phone_code_hash'],
                        )
                        modify_kwargs(
                            phone_code_type=sent_code.type,
                            phone_code_hash=sent_code.phone_code_hash,
                        )
                        await self.storage.Session.commit()
                    await abort('Код отправлен с помощью смс.')

                    sms_msg_id = input.data.kwargs.get('sms_msg_id')
                    if isinstance(sms_msg_id, int):
                        await self.edit_message_reply_markup(
                            input.chat_id, sms_msg_id
                        )
                except FloodWait as e:
                    await abort(
                        'Для отправки кода с помощью смс необходимо подождать '
                        'еще __%s__.'
                        % self.morph.timedelta(e.value, case='gent')
                    )
                except BadRequest as _:
                    await abort('Не удалось отправить код с помощью смс.')

            # STEP 4.2: Skip entering the Last Name
            elif data.command == self.SENDER_CLIENT.AUTH_SKIP_LAST_NAME:
                name_message = await self.send_message(
                    chat_id,
                    '\n'.join(
                        _
                        for _ in (
                            'Имя пользователя: __{}__'.format(
                                input.data.kwargs.get('first_name')
                                or 'Отсутствует'
                            ),
                            'Все ли заполнено верно?',
                        )
                        if _ is not None
                    ),
                    reply_markup=IKM(
                        [
                            [
                                IKB(
                                    'Подтвердить',
                                    self.SENDER_CLIENT.AUTH_REGISTER_APPROVE,
                                )
                            ],
                            [
                                IKB(
                                    'Заполнить заново',
                                    self.SENDER_CLIENT.AUTH_REGISTER_RETRY,
                                )
                            ],
                        ]
                    ),
                )
                modify_kwargs(last_name='', name_msg_id=name_message.id)
                self.storage.Session.add(
                    InputMessageModel.from_message(name_message, input)
                )
                await self.storage.Session.commit()

                last_name_message_id = input.data.kwargs.get('ln_msg_id')
                if isinstance(last_name_message_id, int):
                    await self.edit_message_reply_markup(
                        input.chat_id, last_name_message_id
                    )

            # STEP 4.4: Enter the name again
            elif data.command == self.SENDER_CLIENT.AUTH_REGISTER_RETRY:
                modify_kwargs('first_name', 'last_name', 'ln_msg_id')
                await self.answer_edit_send(
                    chat_id=input.chat_id,
                    message_id=input.data.kwargs.get('name_msg_id'),
                    text='Еще раз пришлите имя пользователя для регистрации.',
                )

            # STEP 4.5: Register the client with the given name and last_name
            elif data.command == self.SENDER_CLIENT.AUTH_REGISTER_APPROVE:
                try:
                    async with auto_init(
                        sender, only_connect=True, stop=False
                    ):
                        await sender.sign_up(
                            str(input.data.kwargs['phone_number']),
                            input.data.kwargs['phone_code_hash'],
                            input.data.kwargs['first_name'],
                            input.data.kwargs.get('last_name', ''),
                        )

                        tos_id = input.data.kwargs.get('tos_id')
                        if isinstance(tos_id, str):
                            return await sender.accept_terms_of_service(tos_id)
                    return not await abort(
                        'Произошла ошибка. Попробуйте еще раз.'
                    )
                except BadRequest:
                    return await abort(
                        'Введено неккоректное имя или фамилия '
                        'пользователя. Попробуйте ввести данные еще раз.',
                    )

            return False

        # STEP 1: Receive a phone number
        elif 'phone_code_hash' not in input.data.kwargs:
            # STEP 1.1: Validate a phone number
            if not isinstance(message_id, Message):
                message_id = await self.get_messages(chat_id, message_id)
            phone_number = int(sub(r'\D', '', message_id.text) or 0)
            if not phone_number:
                return await abort(
                    'Получен неккоректный номер телефона. Попробуйте еще раз.'
                )
            elif phone_number == (await self.get_users(chat_id)).phone_number:
                return await abort(
                    'Вы не можете использовать свой аккаунт в качестве бота.'
                )
            modify_kwargs(phone_number=phone_number)

            # STEP 2: Initialize a client
            sender = self.get_worker(phone_number)

            # STEP 2.1: Validate a client
            if await sender.validate():
                # STEP 2.1.2: Add a client to the database
                if await self.storage.Session.scalar(
                    select(
                        ~exists(text('NULL')).where(
                            ClientModel.phone_number == phone_number
                        )
                    )
                ):
                    return True

                # STEP 2.1.1: Ask for another client
                return await abort(
                    'Этот клиент уже используется. Попробуйте еще раз.'
                )

            # STEP 3: Receive a confirmation code in the app
            else:
                try:
                    async with auto_init(
                        sender, only_connect=True, stop=False
                    ):
                        try:
                            sent_code = await sender.send_code(
                                str(phone_number)
                            )
                        except PhoneNumberInvalid:
                            return await abort(
                                'Получен неккоректный номер телефона. '
                                'Попробуйте еще раз.'
                            )

                    sms_msg = await self.send_message(
                        chat_id,
                        '\n'.join(
                            (
                                f'На номер {phone_number} было отправлено '
                                'сообщение с кодом авторизации.',
                                'Пришлите его в сообщении ниже.',
                            )
                        ),
                        reply_markup=IKM(
                            [
                                [
                                    IKB(
                                        'Отправить код с помощью смс',
                                        self.SENDER_CLIENT.AUTH_SEND_SMS,
                                    )
                                ]
                            ]
                        ),
                    )
                    used_sms_msg = InputMessageModel.from_message(
                        sms_msg, input
                    )
                    self.storage.Session.add(used_sms_msg)
                    modify_kwargs(
                        phone_code_type=sent_code.type,
                        phone_code_hash=sent_code.phone_code_hash,
                        sms_msg_id=sms_msg.id,
                    )
                    await self.storage.Session.commit()
                except (BadRequest, ConnectionError) as _:
                    return await abort(
                        '\n'.join(
                            (
                                'Ошибка при отправке кода авторизации.',
                                'Возможно введен некорректный номер телефона.',
                                'Попробуйте ввести номер телефона еще раз.',
                            )
                        ),
                        add=False,
                    )
                except FloodWait as e:
                    return await abort(
                        'Перед следующей попыткой входа по номеру '
                        f'{phone_number} необходимо подождать еще '
                        '__%s__.' % self.morph.timedelta(e.value, case='gent'),
                        add=False,
                    )

            return False

        # STEP 4: Register a client
        elif 'signed_in' in input.data.kwargs:
            # STEP 4.1: The first name of the client
            if 'first_name' not in input.data.kwargs:
                if not isinstance(message_id, Message):
                    message_id = await self.get_messages(chat_id, message_id)
                first_name = sub(r'\s+', '', message_id.text)
                if len(first_name) > MAX_NAME_LENGTH:
                    return await abort(
                        'Введенное имя слишком длинное, попробуйте еще раз.'
                    )

                ln_message = await self.send_message(
                    chat_id,
                    '\n'.join(
                        (
                            f'Имя пользователя: __{first_name}__',
                            'Теперь пришлите фамилию пользователя.',
                        )
                    ),
                    reply_markup=IKM(
                        [
                            [
                                IKB(
                                    'Пропустить',
                                    self.SENDER_CLIENT.AUTH_SKIP_LAST_NAME,
                                )
                            ]
                        ]
                    ),
                )
                modify_kwargs(first_name=first_name, ln_msg_id=ln_message.id)
                self.storage.Session.add(
                    InputMessageModel.from_message(ln_message, input)
                )
                await self.storage.Session.commit()

            # STEP 4.2: The last name of the client
            elif 'last_name' not in input.data.kwargs:
                if not isinstance(message_id, Message):
                    message_id = await self.get_messages(chat_id, message_id)
                last_name = sub(r'\s+', '', message_id.text)
                if len(last_name) > MAX_NAME_LENGTH:
                    return await abort(
                        'Введенная фамилия слишком длинная, попробуйте еще '
                        'раз.'
                    )

                modify_kwargs(last_name=last_name)
                used = await self.send_message(
                    '\n'.join(
                        (
                            'Имя пользователя: __%s__'
                            % (
                                input.data.kwargs.get('first_name')
                                or 'Отсутствует'
                            ),
                            'Фамилия пользователя: __%s__'
                            % (last_name or 'Отсутствует'),
                            'Все ли заполнено верно?',
                        )
                    ),
                    reply_markup=IKM(
                        [
                            [
                                IKB(
                                    'Подтвердить',
                                    self.SENDER_CLIENT.AUTH_REGISTER_APPROVE,
                                )
                            ],
                            [
                                IKB(
                                    'Заполнить заново',
                                    self.SENDER_CLIENT.AUTH_REGISTER_RETRY,
                                )
                            ],
                        ]
                    ),
                )
                self.storage.Session.add(
                    InputMessageModel.from_message(used, input)
                )
                await self.storage.Session.commit()

                last_name_message_id = input.data.kwargs.get('ln_msg_id')
                if isinstance(last_name_message_id, int):
                    await self.edit_message_reply_markup(
                        input.chat_id, last_name_message_id
                    )
            return False

        # STEP 3.3.2.2: Enter password recovery code
        elif 'email' in input.data.kwargs:
            try:
                if not isinstance(message_id, Message):
                    message_id = await self.get_messages(chat_id, message_id)
                recovery_code = int(sub(r'\s+', '', message_id.text))
                async with auto_init(sender, only_connect=True, stop=False):
                    await sender.recover_password(recovery_code)
                return True
            except (BadRequest, ValueError):
                return await abort(
                    '\n'.join(
                        (
                            'Введен неккоректный код авторизации.',
                            'Попробуйте ввести код авторизации еще раз.',
                        )
                    )
                )

        # STEP 3.3.1: Validate a client's password
        elif 'phone_code' in input.data.kwargs:
            if not isinstance(message_id, Message):
                message_id = await self.get_messages(chat_id, message_id)
            try:
                async with auto_init(sender, only_connect=True, stop=False):
                    return bool(await sender.check_password(message_id.text))
            except BadRequest:
                return await abort(
                    '\n'.join(
                        (
                            'Введен неккоректный пароль.',
                            'Попробуйте ввести пароль еще раз.',
                        )
                    )
                )

        # STEP 3.1: Check for code's validity
        else:
            try:
                if not isinstance(message_id, Message):
                    message_id = await self.get_messages(chat_id, message_id)
                phone_code = int(sub(r'\D', '', message_id.text))

                # STEP 3.2: Authorize a client
                async with auto_init(sender, only_connect=True, stop=False):
                    signed_in = await sender.sign_in(
                        str(input.data.kwargs['phone_number']),
                        input.data.kwargs['phone_code_hash'],
                        str(phone_code),
                    )
                if isinstance(signed_in, User):
                    return True
                elif isinstance(signed_in, TermsOfService):
                    modify_kwargs(tos_id=signed_in.id)
                modify_kwargs(signed_in=True)

                # STEP 4: Register a user
                return await abort(
                    'Пользователь успешно авторизован. '
                    'Теперь пришлите имя пользователя для регистрации.'
                )
            except FloodWait as e:
                return await abort(
                    'Перед следующей попыткой входа по номеру '
                    '{phone_number} необходимо подождать еще '
                    '__{time}__.'.format(
                        phone_number=input.data.kwargs['phone_number'],
                        time=self.morph.timedelta(e.value, case='gent'),
                    ),
                    add=False,
                )

            # STEP 3.3: Check for the client's password
            except SessionPasswordNeeded as e:
                recover_code = self.SENDER_CLIENT.AUTH_RECOVER_PASSWORD
                async with auto_init(sender, only_connect=True, stop=False):
                    password_hint = await sender.get_password_hint()
                email_msg = await self.send_message(
                    chat_id,
                    '\n'.join(
                        _
                        for _ in (
                            'Для авторизации необходим ввод пароля.',
                            '',
                            '**Подсказка:** __%s__'
                            % (password_hint or 'Отсутствует'),
                        )
                        if _ is not None
                    ),
                    reply_markup=IKM([[IKB('Сбросить пароль', recover_code)]]),
                )
                modify_kwargs(phone_code=phone_code, email_msg_id=email_msg.id)
                self.storage.Session.add(
                    InputMessageModel.from_message(email_msg, input)
                )
                await self.storage.Session.commit()
                return False

            except (BadRequest, ValueError) as e:
                return await abort(
                    '\n'.join(
                        (
                            'Введен неккоректный или устарелый код '
                            'авторизации.',
                            'Попробуйте ввести код авторизации еще раз.',
                        )
                    )
                )

    async def _add_client_on_finished(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        if not isinstance(chat_id, InputModel):
            raise NotImplementedError('This method works only with inputs.')
        input, chat_id = chat_id, chat_id.chat_id

        phone_number = input.data.kwargs.get('phone_number')
        if not input.success:
            if query_id is None:
                with suppress(RPCError):
                    await self.delete_messages(input.chat_id, input.message_id)
                return
        elif isinstance(phone_number, int):
            _client = self.get_worker(phone_number)
            async with auto_init(_client, start=False, stop=True):
                pass
            if await _client.validate():
                await self.storage.Session.merge(
                    ClientModel(phone_number=phone_number)
                )
                await self.storage.Session.commit()
                await self.answer_edit_send(
                    *(query_id, chat_id),
                    text=f'Бот под номером {phone_number} был успешно '
                    'добавлен.',
                )
            else:
                await _client.storage.delete()
        return await self.start_message(input, None, data, query_id)
