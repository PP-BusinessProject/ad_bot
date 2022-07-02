"""The module for processing SettingsCommands."""

from contextlib import suppress
from copy import copy
from datetime import datetime
from time import time
from typing import TYPE_CHECKING, Optional, Union

from pyrogram.errors import RPCError, UsernameInvalid, UsernameNotOccupied
from pyrogram.errors.exceptions.bad_request_400 import PeerIdInvalid
from pyrogram.errors.exceptions.flood_420 import Flood
from pyrogram.errors.exceptions.unauthorized_401 import Unauthorized
from pyrogram.types import InlineKeyboardButton as IKB
from pyrogram.types import InlineKeyboardMarkup as IKM
from pyrogram.types import InputMediaPhoto, Message
from pyrogram.utils import get_channel_id
from sqlalchemy.sql.expression import exists, select
from sqlalchemy.sql.expression import text as sql_text

from ...models._constraints import (
    MAX_ABOUT_LENGTH,
    MAX_NAME_LENGTH,
    MAX_USERNAME_LENGTH,
)
from ...models.bots.client_model import ClientModel
from ...models.clients.bot_model import BotModel
from ...models.clients.user_model import UserModel, UserRole
from ...models.misc.input_message_model import InputMessageModel
from ...models.misc.input_model import InputModel
from ...models.sessions.session_model import SessionModel
from ...utils.pyrogram import auto_init
from ...utils.query import Query
from .utils import message_header

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class SettingsMessage(object):
    async def settings_message(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        """
        Show the message with :class:`BotModel` properties.

        Args:
            chat_id (``int``):
                The id of a chat to send this message to.

            message_id (``int``, *optional*):
                The id of an already sent message to show this message in.

            data (``Optional[Query]``):
                The data used for retrieving information with `session`.

        Returns:
            The sent message with :class:`BotModel` properties.
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

        if isinstance(_message_id := message_id, Message):
            message_id = message_id.id
        input: Optional[InputModel] = None
        if isinstance(chat_id, InputModel):
            input, chat_id = chat_id, chat_id.chat_id
            if input.message_id is not None:
                message_id = input.message_id
            if input.data is not None:
                data = input.data(self.SETTINGS.PAGE)
        if data is None:
            data = Query(self.SETTINGS.PAGE, chat_id, 0)

        bot: BotModel
        bot = await self.storage.Session.get(BotModel, data.args)
        if bot is None:
            return await abort('Бот не существует.')

        if data.command in self.SETTINGS_DELETE._member_map_.values():
            text = command = None
            if data.command == self.SETTINGS_DELETE.FIRST_NAME:
                text = f'Вы уверены что хотите стереть Имя бота#{bot.id}?'
                command = self.SETTINGS_DELETE.FIRST_NAME_CONFIRM

            elif data.command == self.SETTINGS_DELETE.LAST_NAME:
                text = f'Вы уверены что хотите убрать Фамилию бота#{bot.id}?'
                command = self.SETTINGS_DELETE.LAST_NAME_CONFIRM

            elif data.command == self.SETTINGS_DELETE.ABOUT:
                text = (
                    f'Вы уверены что хотите удалить Биографию бота#{bot.id}?'
                )
                command = self.SETTINGS_DELETE.ABOUT_CONFIRM

            elif data.command == self.SETTINGS_DELETE.USERNAME:
                text = (
                    'Вы уверены что хотите удалить ваш Юзернейм '
                    f'бота#{bot.id}?'
                )
                command = self.SETTINGS_DELETE.USERNAME_CONFIRM

            elif data.command == self.SETTINGS_DELETE.REPLY:
                text = (
                    f'Вы уверены что хотите сбросить Автоответ бота#{bot.id}?'
                )
                command = self.SETTINGS_DELETE.REPLY_CONFIRM

            elif data.command == self.SETTINGS_DELETE.CONTACT:
                text = f'Вы уверены что хотите сбросить Контакт бота#{bot.id}?'
                command = self.SETTINGS_DELETE.CONTACT_CONFIRM

            elif data.command == self.SETTINGS_DELETE.AVATAR:
                text = (
                    f'Вы уверены что хотите удалить ваш Аватар бота#{bot.id}?'
                )
                command = self.SETTINGS_DELETE.AVATAR_CONFIRM

            if text is not None and command is not None:
                return await self.send_or_edit(
                    *(chat_id, message_id),
                    text=text,
                    reply_markup=IKM(
                        [
                            [
                                IKB('Да', data(command)),
                                IKB('Нет', data(self.SETTINGS.PAGE)),
                            ]
                        ]
                    ),
                )

            if data.command == self.SETTINGS_DELETE.FIRST_NAME_CONFIRM:
                bot.first_name = BotModel.first_name.default

            elif data.command == self.SETTINGS_DELETE.LAST_NAME_CONFIRM:
                bot.last_name = None

            elif data.command == self.SETTINGS_DELETE.ABOUT_CONFIRM:
                bot.about = None

            elif data.command == self.SETTINGS_DELETE.USERNAME_CONFIRM:
                bot.username = None

            elif data.command == self.SETTINGS_DELETE.REPLY_CONFIRM:
                bot.reply_message_id = None

            elif data.command == self.SETTINGS_DELETE.CONTACT_CONFIRM:
                bot.forward_to_id = bot.owner.id

            elif data.command == self.SETTINGS_DELETE.AVATAR_CONFIRM and (
                bot.avatar_message_id is not None
            ):
                bot.avatar_message_id = None
            await self.storage.Session.commit()
            data = data(self.SETTINGS.PAGE)

        if data.command == self.SETTINGS.APPLY:
            if not bot.confirmed:
                return await abort('Бот не подтвержден.')

            phone_number: int
            async for phone_number in (
                await self.storage.Session.stream_scalars(
                    select(ClientModel.phone_number)
                    .filter(
                        ClientModel.valid,
                        (ClientModel.phone_number == bot.phone_number)
                        | ~exists(sql_text('NULL')).where(
                            ClientModel.phone_number == BotModel.phone_number
                        ),
                        exists(sql_text('NULL'))
                        .where(
                            SessionModel.phone_number
                            == ClientModel.phone_number
                        )
                        .where(SessionModel.user_id.is_not(None)),
                    )
                    .order_by(ClientModel.phone_number != bot.phone_number)
                )
            ):
                async with auto_init(self.get_worker(phone_number)) as worker:
                    try:
                        await worker.apply_profile_settings(bot)
                    except (Flood, Unauthorized):
                        continue

                try:
                    return await abort(
                        'Предыдущий бот не смог применить настройки. Новый '
                        'бот был назначен и настройки были успешно применены.'
                        if phone_number != bot.phone_number
                        else 'Настройки для бота были успешно применены.'
                    )
                finally:
                    if phone_number != bot.phone_number:
                        bot.phone_number = phone_number
                        await self.storage.Session.commit()
            return await abort(
                'Бот для рассылки не был назначен.'
                if bot.phone_number is None
                else 'Бот для рассылки не смог применить настройки.'
            )

        elif data.command == self.SETTINGS.REPLY_VIEW:
            if bot.reply_message_id is None:
                return await abort('У вас нет автоответа.')
            try:
                reply_message = await self.forward_messages(
                    *(chat_id, bot.owner.service_id, bot.reply_message_id),
                    drop_author=True,
                )
            except RPCError:
                bot.reply_message_id = None
                await self.storage.Session.commit()
                return await abort('Автоответ поврежден.')
            else:
                with suppress(RPCError):
                    if reply_message.reply_markup is None:
                        return await reply_message.edit_reply_markup(
                            IKM([[IKB('Скрыть', Query(self.SERVICE.HIDE))]])
                        )
                return reply_message

        elif data.command == self.SETTINGS.PAGE:
            return await self.send_or_edit(
                *(chat_id, message_id),
                text='\n'.join(
                    _
                    for _ in (
                        message_header(self, bot, chat_id),
                        '',
                        f'**Имя:** {bot.first_name}'
                        if bot.first_name
                        else None,
                        f'**Фамилия:** {bot.last_name}'
                        if bot.last_name
                        else None,
                        f'**Биография:** {bot.about}' if bot.about else None,
                        f"**Юзернейм:** @{bot.username.removeprefix('@')}"
                        if bot.username
                        else None,
                        '**Контакт:** [{name}](tg://user?id={id})'.format(
                            id=bot.forward_to_id,
                            name='вы'
                            if bot.forward_to_id == chat_id
                            else 'пользователь',
                        )
                        if bot.forward_to_id
                        else None,
                        '**Автоответ:** __Есть__'
                        if bot.reply_message_id is not None
                        else None,
                        '**Аватар:** Есть'
                        if bot.avatar_message_id is not None
                        else None,
                    )
                    if _ is not None
                ),
                reply_markup=IKM(
                    [
                        [
                            IKB(
                                'Установить настройки аккаунта',
                                data(self.SETTINGS.DOWNLOAD),
                            ),
                            IKB(
                                'Применить настройки',
                                data(self.SETTINGS.APPLY),
                            ),
                        ],
                        [
                            IKB(
                                'Изменить Имя'
                                if bot.first_name is not None
                                else 'Добавить Имя',
                                data(self.SETTINGS.FIRST_NAME),
                            ),
                        ],
                        (
                            [
                                IKB(
                                    'Удалить Фамилию',
                                    data(self.SETTINGS_DELETE.LAST_NAME),
                                )
                            ]
                            if bot.last_name is not None
                            else []
                        )
                        + [
                            IKB(
                                'Изменить Фамилию'
                                if bot.last_name is not None
                                else 'Добавить Фамилию',
                                data(self.SETTINGS.LAST_NAME),
                            ),
                        ],
                        (
                            [
                                IKB(
                                    'Удалить Биографию',
                                    data(self.SETTINGS_DELETE.ABOUT),
                                )
                            ]
                            if bot.about is not None
                            else []
                        )
                        + [
                            IKB(
                                'Изменить Биографию'
                                if bot.about is not None
                                else 'Добавить Биографию',
                                data(self.SETTINGS.ABOUT),
                            ),
                        ],
                        (
                            [
                                IKB(
                                    'Удалить Юзернейм',
                                    data(self.SETTINGS_DELETE.USERNAME),
                                )
                            ]
                            if bot.username is not None
                            else []
                        )
                        + [
                            IKB(
                                'Изменить Юзернейм'
                                if bot.username
                                else 'Добавить Юзернейм',
                                data(self.SETTINGS.USERNAME),
                            ),
                        ],
                        (
                            [
                                IKB(
                                    'Сбросить Контакт',
                                    data(self.SETTINGS_DELETE.CONTACT),
                                )
                            ]
                            if bot.forward_to_id != bot.owner.id
                            else []
                        )
                        + [
                            IKB(
                                'Изменить Контакт'
                                if bot.forward_to_id is not None
                                else 'Добавить Контакт',
                                data(self.SETTINGS.CONTACT),
                            ),
                        ],
                        (
                            [
                                IKB(
                                    'Удалить Автоответ',
                                    data(self.SETTINGS_DELETE.REPLY),
                                )
                            ]
                            if bot.reply_message_id is not None
                            else []
                        )
                        + [
                            IKB(
                                'Изменить Автоответ'
                                if bot.reply_message_id is not None
                                else 'Добавить Автоответ',
                                data(self.SETTINGS.REPLY),
                            ),
                        ]
                        + (
                            [
                                IKB(
                                    'Просмотреть Автоответ',
                                    data(self.SETTINGS.REPLY_VIEW),
                                )
                            ]
                            if bot.reply_message_id is not None
                            else []
                        ),
                        (
                            [
                                IKB(
                                    'Удалить Аватар',
                                    data(self.SETTINGS_DELETE.AVATAR),
                                )
                            ]
                            if bot.avatar_message_id is not None
                            else []
                        )
                        + [
                            IKB(
                                'Изменить Аватар'
                                if bot.avatar_message_id is not None
                                else 'Добавить Аватар',
                                data(self.SETTINGS.AVATAR),
                            ),
                        ],
                        [IKB('Назад', data(self.BOT.PAGE))],
                    ]
                ),
            )

        elif data.command in self.SETTINGS._member_map_.values():
            if input is None:
                input = await self.storage.Session.get(InputModel, chat_id)
            if input is not None:
                return await self.input_message(
                    input,
                    message_id=_message_id,
                    data=data,
                    query_id=query_id,
                )
            self.storage.Session.add(
                InputModel(
                    chat_id=chat_id,
                    message_id=message_id,
                    data=data,
                    on_response=self._settings_update,
                    on_finished=self.settings_message,
                    user_role=UserRole.USER,
                )
            )
            await self.storage.Session.commit()
            return await self.send_or_edit(
                *(chat_id, message_id),
                'Отправьте новое имя аккаунта рассыльщика. '
                'Длина имени не может превышать 64 символа!'
                if data.command == self.SETTINGS.FIRST_NAME
                else 'Отправьте новую фамилию аккаунта рассыльщика. '
                'Длина имени не может превышать 64 символа!'
                if data.command == self.SETTINGS.LAST_NAME
                else 'Отправьте новое описание аккаунта рассыльщика. '
                'Длина описания не может превышать 70 символа!'
                if data.command == self.SETTINGS.ABOUT
                else 'Отправьте новый юзернейм аккаунта рассыльщика. '
                'Длина юзернейма не может превышать 32 символа!'
                if data.command == self.SETTINGS.USERNAME
                else 'Отправьте сообщение для автоматического ответа '
                'рассыльщика.'
                if data.command == self.SETTINGS.REPLY
                else 'Отправьте @username или перешлите сообщение от '
                'пользователя, которому будут пересылаться сообщения.'
                if data.command == self.SETTINGS.CONTACT
                else 'Пришлите новый аватар в виде картинки. '
                'Минимальный размер аватара 512х512 пикселей.'
                if data.command == self.SETTINGS.AVATAR
                else 'Пришлите сообщение, контакт или юзернейм пользователя, '
                'чей профиль будет загружен в аккаунт бота.',
                reply_markup=IKM(
                    (
                        [[IKB('Скачать мой профиль', data)]]
                        if data.command == self.SETTINGS.DOWNLOAD
                        else []
                    )
                    + [[IKB('Отменить', self.INPUT.CANCEL)]]
                ),
            )

    async def _settings_update(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> bool:
        """
        Try to update the bot in the database.

        Creates a string with changes and sends it to the service channel for
        confirmation purposes.

        Args:
            input (``InputModel``):
                The active awaiting input of a user with the ``CallbackQuery``
                of the initial request.

        Returns:
            If update was successful, returns True. Otherwise, False.
        """

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
                'Изменить настройки бота можно только через сообщение.'
            )
        input, chat_id = chat_id, chat_id.chat_id
        bot: Optional[BotModel] = await self.storage.Session.get(
            BotModel, input.data.args
        )
        if bot is None:
            return await abort('Бот не найден, попробуйте еще раз.', add=False)

        elif bot.owner.service_id is None:
            return await abort(
                'Личный канал пользователя не создан.'
                if chat_id != bot.owner.id
                else 'У вас нет личного канала.'
            )

        elif not await self.check_chats(
            (bot.owner.service_id, bot.owner.service_invite),
            folder_id=1,
        ):
            return await abort(
                'У бота нет доступа к личному каналу пользователя.'
                if chat_id != bot.owner.id
                else 'У бота нет доступа к вашему личному каналу.'
            )

        elif bot.owner.service_invite is None:
            invite_link = await self.export_chat_invite_link(
                bot.owner.service_id
            )
            bot.owner.service_invite = invite_link.invite_link
            await self.storage.Session.commit()

        if not isinstance(message := message_id, Message):
            message: Message = await self.get_messages(chat_id, message_id)
        else:
            message_id = message_id.id
        if input.data.command == self.SETTINGS.DOWNLOAD:
            if data is not None:
                user_id = input.chat_id
            elif message.contact:
                user_id = message.contact.user_id
            elif message.forward_from:
                user_id = message.forward_from.id
            else:
                try:
                    user_id = await self.resolve_peer(message.text)
                except PeerIdInvalid:
                    return await abort(
                        'Не обнаружен контакт или пользователь от '
                        'пересланного сообщения, попробуйте еще раз.',
                        add=True,
                    )

            old_bot = copy(bot)
            await self.get_profile_settings(bot, user_id, force=True)

            _changes: list[tuple[str, ...]] = []
            if old_bot.first_name != bot.first_name:
                _changes.append(
                    (
                        '**Имя:**',
                        '__Было:__ %s' % (old_bot.first_name or 'Не было'),
                        '__Стало:__ %s' % bot.first_name,
                    )
                )

            if old_bot.last_name != bot.last_name:
                _changes.append(
                    (
                        '**Фамилия:**',
                        '__Была:__ %s' % (old_bot.last_name or 'Не было'),
                        '__Стала:__ %s' % bot.last_name,
                    )
                )

            if old_bot.about != bot.about:
                _changes.append(
                    (
                        '**Биография:**',
                        '__Была:__ %s' % (old_bot.about or 'Не было'),
                        '__Стала:__ %s' % bot.about,
                    )
                )

            if old_bot.username != bot.username:
                _changes.append(
                    (
                        '**Юзернейм:**',
                        '__Был:__ %s'
                        % (
                            f'@{old_bot.username}'
                            if old_bot.username
                            else 'Не было'
                        ),
                        '__Стал:__ %s' % bot.username,
                    )
                )
            if old_bot.avatar_message_id != bot.avatar_message_id:
                service_id = get_channel_id(bot.owner.service_id)
                _changes.append(
                    (
                        '**Аватар:**',
                        '__Был:__ %s'
                        % (
                            '[ссылка](https://t.me/c/%s/%s)'
                            % (service_id, old_bot.avatar_message_id)
                            if old_bot.avatar_message_id is not None
                            else 'Не было'
                        ),
                        '__Стал:__ [ссылка](https://t.me/c/%s/%s)'
                        % (service_id, bot.avatar_message_id),
                    )
                )
            changes = '\n\n'.join('\n'.join(_) for _ in _changes)

        elif input.data.command == self.SETTINGS.FIRST_NAME:
            if len(message.text) > MAX_NAME_LENGTH:
                return await abort(
                    'Введенное имя слишком длинное, попробуйте еще раз.',
                    add=True,
                )
            changes = '\n'.join(
                (
                    '**Имя:**',
                    '__Было:__ %s' % (bot.first_name or 'Не было'),
                    '__Стало:__ %s' % message.text,
                )
            )
            bot.first_name = message.text

        elif input.data.command == self.SETTINGS.LAST_NAME:
            if len(message.text) > MAX_NAME_LENGTH:
                return await abort(
                    'Введенная фамилия слишком длинная, попробуйте еще раз.',
                    add=True,
                )
            changes = '\n'.join(
                (
                    '**Фамилия:**',
                    '__Была:__ %s' % (bot.last_name or 'Не было'),
                    '__Стала:__ %s' % message.text,
                )
            )
            bot.last_name = message.text

        elif input.data.command == self.SETTINGS.ABOUT:
            if len(message.text) > MAX_ABOUT_LENGTH:
                return await abort(
                    'Введеная биография слишком длинная, попробуйте еще раз.',
                    add=True,
                )
            changes = '\n'.join(
                (
                    '**Биография:**',
                    '__Была:__ %s' % (bot.about or 'Не было'),
                    '__Стала:__ %s' % message.text,
                )
            )
            bot.about = message.text

        elif input.data.command == self.SETTINGS.USERNAME:
            username = '@' + message.text.replace('@', '')
            if len(username) > MAX_USERNAME_LENGTH:
                return await abort(
                    'Введеный юзернейм слишком длинный, попробуйте еще раз.',
                    add=True,
                )

            try:
                await self.get_users(username)
            except UsernameInvalid:
                return await abort(
                    'Невозможно использовать этот юзернейм, попробуйте '
                    'другой.',
                    add=True,
                )
            except (UsernameNotOccupied, IndexError):
                changes = '\n'.join(
                    (
                        '**Юзернейм:**',
                        '__Был:__ '
                        + (f'@{bot.username}' if bot.username else 'Не было'),
                        '__Стал:__ ' + username,
                    )
                )

                bot.username = username.removeprefix('@')
            except RPCError as _:
                return await abort(
                    'Произошла ошибка, попробуйте еще раз.',
                    add=True,
                )
            else:
                return await abort(
                    'Пользователь с этим юзернеймом уже существует, '
                    'попробуйте другой.',
                    add=True,
                )

        elif input.data.command == self.SETTINGS.REPLY:
            try:
                reply_message = await self.forward_messages(
                    bot.owner.service_id, chat_id, message_id
                )
            except RPCError as _:
                return await abort(
                    'Произошла ошибка, попробуйте еще раз.',
                    add=True,
                )

            service_id = get_channel_id(bot.owner.service_id)
            changes = '\n'.join(
                (
                    '**Автоответ:** ',
                    '__Был:__'
                    + (
                        '[ссылка](https://t.me/c/%s/%s)'
                        % (service_id, bot.reply_message_id)
                        if bot.reply_message_id is not None
                        else 'Не было'
                    ),
                    '__Стал:__ [ссылка](https://t.me/c/%s/%s)'
                    % (service_id, reply_message.id),
                )
            )
            bot.reply_message_id = reply_message.id

        elif input.data.command == self.SETTINGS.CONTACT:
            try:
                contact_user = await self.get_users(
                    message.forward_from.id
                    if message.forward_from
                    else message.text
                )
            except (IndexError, RPCError):
                return await abort(
                    'Не удалось получить информацию о пользователе, '
                    'попробуйте еще раз.',
                    add=True,
                )

            changes = '\n'.join(
                (
                    '**Контакт:**',
                    '__Был:__ '
                    + (
                        '[пользователь](tg://user?id=%s)' % bot.forward_to_id
                        if bot.forward_to_id is not None
                        else 'Не было'
                    ),
                    '__Стал:__ [пользователь](tg://user?id=%s)'
                    % contact_user.id,
                )
            )

            bot.forward_to_id = contact_user.id

        elif input.data.command == self.SETTINGS.AVATAR:
            photo_messages: list[Message] = []
            if message.media_group_id is not None:
                photo_messages += await message.get_media_group()
            elif message.photo is not None:
                photo_messages.append(message)

            if not photo_messages:
                return await abort(
                    'Вы не отправили изображение, попробуйте еще раз.',
                    add=True,
                )

            invalid_messages: dict[str, Message] = {
                str(index): message
                for index, message in enumerate(photo_messages, 1)
                if message.photo.height < 512 or message.photo.width < 512
            }
            if invalid_messages:
                word = self.plural(
                    len(invalid_messages), 'Изображение', 'имеет'
                )
                return await abort(
                    (
                        (
                            ' номер %s '
                            % ', '.join(
                                f'[{index}]({message.link})'
                                for index, message in invalid_messages.items()
                            )
                        ).join(word.split())
                        if message.media_group_id is not None
                        else word
                    ).capitalize()
                    + ' слишком маленький размер. Попробуйте еще раз.',
                    add=True,
                )

            try:
                new_messages = await self.send_media_group(
                    bot.owner.service_id,
                    [
                        InputMediaPhoto(message.photo.file_id)
                        for message in photo_messages
                    ],
                )
            except RPCError:
                return await abort(
                    'Не удалось обновить аватар, попробуйте еще раз.',
                    add=True,
                )

            service_id = get_channel_id(bot.owner.service_id)
            changes = '\n'.join(
                (
                    '**Аватар:**',
                    '__Был:__ %s'
                    % (
                        '[ссылка](https://t.me/c/%s/%s)'
                        % (service_id, bot.avatar_message_id)
                        if bot.avatar_message_id is not None
                        else 'Не было'
                    ),
                    '__Стал:__ %s' % new_messages[0].link,
                )
            )
            bot.avatar_message_id = new_messages[0].id

        else:
            raise NotImplementedError(
                f'Command {input.data.command} is not supported.'
            )

        if bot.owner.id != chat_id:
            user_confirmed: bool = await self.storage.Session.scalar(
                select(
                    exists(sql_text('NULL')).where(
                        (UserModel.id == chat_id)
                        & (UserModel.role >= UserRole.SUPPORT)
                    )
                )
            )
        else:
            user_confirmed = bot.owner.role >= UserRole.SUPPORT

        confirm_message: Optional[Message] = None
        if bot.confirm_message_id is not None:
            if user_confirmed:
                await self.service_validation(
                    chat_id=bot.owner.service_id,
                    message_id=bot.confirm_message_id,
                    data=input.data(
                        self.SERVICE.APPROVE,
                        args=(input.data.command, *input.data.args),
                    ),
                    query_id=query_id,
                )
            else:
                confirm_message: Message = await self.get_messages(
                    bot.owner.service_id, bot.confirm_message_id
                )
                if not confirm_message.empty:
                    date = '[%s]' % datetime.fromtimestamp(round(time()))
                    _text = confirm_message.text.markdown
                    confirm_message = await confirm_message.edit(
                        ''.join(_text.splitlines(keepends=True)[:-1])
                        + '\n'.join((date, changes, '', 'Подтвердить?')),
                        reply_markup=confirm_message.reply_markup,
                    )

        if not user_confirmed and (
            confirm_message is None or confirm_message.empty
        ):

            def _query(command: str, /) -> Query:
                return input.data(
                    command,
                    args=(input.data.command, *input.data.args),
                )

            confirm_message = await self.send_message(
                bot.owner.service_id,
                '\n'.join(
                    (
                        '**Изменения в боте #%s**' % bot.id,
                        '',
                        '[%s]' % datetime.fromtimestamp(round(time())),
                        changes,
                        '',
                        'Подтвердить?',
                    )
                ),
                reply_markup=IKM(
                    [
                        [
                            IKB('Да', _query(self.SERVICE.APPROVE)),
                            IKB('Нет', _query(self.SERVICE.DENY)),
                        ]
                    ]
                ),
            )
            bot.confirm_message_id = confirm_message.id
        await self.storage.Session.commit()
        return True
