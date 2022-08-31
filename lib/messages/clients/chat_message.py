"""The module for processing SenderCommands."""

from asyncio import sleep
from contextlib import suppress
from datetime import timedelta
from multiprocessing import Value
from multiprocessing.managers import ValueProxy
from time import monotonic
from typing import TYPE_CHECKING, Any, Optional, Union

from apscheduler.jobstores.base import JobLookupError
from pyrogram.errors import FloodWait
from pyrogram.errors.rpc_error import RPCError
from pyrogram.types import InlineKeyboardButton as IKB
from pyrogram.types import InlineKeyboardMarkup as IKM
from pyrogram.types import Message
from pyrogram.types.user_and_chats.chat import Chat
from sqlalchemy.sql.expression import exists, select, text
from sqlalchemy.sql.functions import count

from ...methods.chats.check_chats import CheckChatsFloodWait
from ...models.bots.chat_model import ChatDeactivatedCause as CHAT_DEACTIVATED
from ...models.bots.chat_model import ChatModel
from ...models.bots.client_model import ClientModel
from ...models.clients.user_model import UserRole
from ...models.misc.category_model import CategoryModel
from ...models.misc.input_message_model import InputMessageModel
from ...models.misc.input_model import InputModel
from ...models.misc.settings_model import SettingsModel
from ...models.sessions.session_model import SessionModel
from ...utils.pyrogram import auto_init
from ...utils.query import Query

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class ChatMessage(object):
    async def chats_list(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> None:
        """
        Show off a list of chats within pages.

        Only applicable for `UserRole.SUPPORT` and greater.

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
            The sent message with chats listed within pages.
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

        if isinstance(chat_id, InputModel):
            chat_id = chat_id.chat_id
        if isinstance(message_id, Message):
            message_id = message_id.id

        page_index: int = data.kwargs.get('p') if data is not None else None
        if not isinstance(page_index, int):
            page_index = 0

        chats_count: int = await self.storage.Session.scalar(
            select(count()).select_from(ChatModel)
        )
        if not chats_count:
            return await abort('На данный момент нет чатов для рассылки.')

        page_list_size: int = await self.storage.Session.scalar(
            select(SettingsModel.page_list_size).where(
                SettingsModel.id.is_(True)
            )
        )
        total_pages: int = -(-chats_count // page_list_size)
        return await self.send_or_edit(
            *(chat_id, message_id),
            text='Список чатов для рассылки. Всего {count} {word}.'.format(
                count=chats_count,
                word=self.morph.plural(chats_count, 'чат'),
            ),
            reply_markup=IKM(
                self.hpages(
                    page_index,
                    total_pages,
                    Query(self.SENDER_CHAT.LIST),
                    kwarg='p',
                )
                + [
                    [
                        IKB(
                            ' '.join(
                                (chat.title, '✅' if chat.active else '❌')
                            ),
                            Query(
                                self.SENDER_CHAT.PAGE, chat.id, p=page_index
                            ),
                        )
                    ]
                    async for chat in (
                        await self.storage.Session.stream_scalars(
                            select(ChatModel)
                            .order_by(
                                ChatModel.created_at.desc(),
                                ChatModel.title,
                            )
                            .slice(
                                min(page_index, total_pages - 1)
                                * page_list_size,
                                min(page_index + 1, total_pages)
                                * page_list_size,
                            )
                        )
                    )
                ]
                + [[IKB('Назад', Query(self.SERVICE._SELF))]]
            ),
        )

    async def chat_message(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        """
        Reply with a for the single chat page.

        Only applicable for `UserRole.SUPPORT` and greater.
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

        if isinstance(message_id, Message):
            message_id = message_id.id
        if isinstance(chat_id, InputModel):
            input, chat_id = chat_id, chat_id.chat_id
            if input.message_id is not None:
                message_id = input.message_id
            if input.data is not None:
                data = input.data(self.SENDER_CHAT.PAGE)

        if data is None or data.command in (
            self.SENDER_CHAT._SELF,
            self.SENDER_CHAT.CATEGORY,
        ):
            if data is None:
                data = Query(self.SENDER_CHAT._SELF)
            result = await self.category_message(
                *(chat_id, message_id, data, query_id),
                prefix_text='\n'.join(
                    (
                        'Работа осуществляется в 3 этапа:',
                        '1. Выбор категории для чатов.',
                        '2. Присылание списка чатов. Чаты должны быть '
                        'присланы построчно, возможно по несколько ссылок '
                        'к одному чату на строке.',
                        '3. Получение чатов и обновление в базе.',
                    )
                ),
                cancel_command=self.SERVICE._SELF
                if data is None or data.command == self.SENDER_CHAT._SELF
                else self.SENDER_CHAT.PAGE,
            )
            if not isinstance(result, CategoryModel):
                return result
            data = data.__copy__(kwargs=dict(category_id=result.id))

            if data.command == self.SENDER_CHAT._SELF:
                _type = InputModel.on_response.type
                check_func = _type.process_bind_param(self._add_chats)
                if await self.storage.Session.scalar(
                    select(
                        exists(text('NULL')).where(
                            InputModel.on_response == check_func
                        )
                    )
                ):
                    return await abort(
                        'Другой пользователь уже добавляет чаты.'
                    )
                input = await self.storage.Session.get(InputModel, chat_id)
                if input is None:
                    input = InputModel(
                        chat_id=chat_id,
                        message_id=message_id,
                        data=data,
                        query_pattern=self.SENDER_CHAT.REFRESH.value,
                        on_response=self._add_chats,
                        on_finished=self._add_chats_on_finished,
                        user_role=UserRole.SUPPORT,
                        do_add_message=False,
                    )
                    self.storage.Session.add(input)
                    await self.storage.Session.commit()
                return await self._add_chats(
                    input, message_id, Query(self.SENDER_CHAT.REFRESH)
                )

        chat = await self.storage.Session.get(ChatModel, data.args)
        if chat is None:
            return await abort('Чат не найден.')

        elif data.command == self.SENDER_CHAT.CATEGORY:
            chat.category_id = result.id
            await self.storage.Session.commit()

        elif data.command == self.SENDER_CHAT.REMOVE_CATEGORY:
            chat.category_id = None
            await self.storage.Session.commit()

        elif data.command == self.SENDER_CHAT.REFRESH:
            workers_flood: dict[int, float] = {}
            phone_number: int
            async for phone_number in (
                await self.storage.Session.stream_scalars(
                    select(ClientModel.phone_number)
                    .filter(
                        ClientModel.valid,
                        exists(text('NULL'))
                        .where(
                            SessionModel.phone_number
                            == ClientModel.phone_number
                        )
                        .where(SessionModel.user_id.is_not(None)),
                    )
                    .order_by(ClientModel.created_at)
                )
            ):
                async with auto_init(self.get_worker(phone_number)) as worker:
                    try:
                        _chat = await worker.check_chats(
                            (
                                chat.id,
                                chat.invite_link,
                                f'@{chat.username}' if chat.username else None,
                            ),
                            folder_id=1,
                        )
                        if _chat is None:
                            return await abort(
                                'Произошла ошибка при получении чата.'
                            )
                    except FloodWait as e:
                        workers_flood[phone_number] = e.value
                    else:
                        break
            else:
                if not workers_flood:
                    return await abort(
                        'На данный момент нет свободных ботов для обновления '
                        'чата.'
                    )
                flood = min(workers_flood.values())
                return await abort(
                    'Перед обновлением чата необходимо подождать '
                    '__%s__.' % self.morph.timedelta(flood)
                )

            chat.title = _chat.title
            chat.description = _chat.description
            await self.storage.Session.commit()

        elif data.command == self.SENDER_CHAT.ACTIVATE:
            if not chat.active:
                chat.deactivated_cause = None
            chat.active = not chat.active
            await self.storage.Session.commit()

        elif data.command == self.SENDER_CHAT.PERIOD_RESET:
            chat.period = ChatModel.period.default.arg
            await self.storage.Session.commit()

        elif data.command == self.SENDER_CHAT.PERIOD_CHANGE:
            self.storage.Session.add(
                InputModel(
                    chat_id=chat_id,
                    message_id=message_id,
                    data=data,
                    on_response=self._update_chat_period,
                    on_finished=self.sender_chat_message,
                    user_role=UserRole.SUPPORT,
                )
            )
            await self.storage.Session.commit()
            return await self.send_or_edit(
                *(chat_id, message_id),
                '\n'.join(
                    (
                        'Пришлите новую длительность периода рассылки.',
                        '',
                        'Формат: **день:час:минута:секунда** с автоматической '
                        'конвертацией значений.',
                        '',
                        'Пример:',
                        '**1:0:0:0** равен периоду в один день;',
                        '**10:30** равен периоду в 10 минут 30 секунд;',
                        '**100** равен периоду в 1 минуту 40 секунд.',
                    )
                ),
                reply_markup=IKM([[IKB('Отменить', self.INPUT.CANCEL)]]),
            )

        category_list = []
        if chat.category_id is not None:
            category: CategoryModel = await self.storage.Session.get(
                CategoryModel, chat.category_id
            )
            category_list.append(category.name)
            while category.parent is not None:
                category_list.append((category := category.parent).name)

        return await self.send_or_edit(
            *(chat_id, message_id),
            '\n'.join(
                _
                for _ in (
                    '**__Чат %s__**'
                    % (
                        f'@{chat.username}'
                        if chat.username
                        else f'[{chat.id}]({chat.invite_link or str()})'
                    ),
                    '',
                    '**Имя:** ' + chat.title if chat.title else None,
                    '**Описание:** ' + chat.description
                    if chat.title and chat.description
                    else None,
                    '**Статус:** '
                    + ('Активен' if chat.active else 'Неактивен'),
                    '**Периодичность:** ' + self.morph.timedelta(chat.period),
                    '**Категория:** {}'.format(
                        ' > '.join(reversed(category_list))
                        if category_list
                        else '__Отсутствует__'
                    ),
                    '**Причина деактивации:** '
                    + (
                        'Id чата изменился. Попробуйте добавить чат заново.'
                        if chat.deactivated_cause
                        == CHAT_DEACTIVATED.PEER_INVALID
                        else 'Проверьте настройки периодичности рассылки для '
                        'этого канала.'
                        if chat.deactivated_cause == CHAT_DEACTIVATED.SLOWMODE
                        else 'Канал не валиден.'
                        if chat.deactivated_cause == CHAT_DEACTIVATED.INVALID
                        else 'Канал был забанен.'
                        if chat.deactivated_cause == CHAT_DEACTIVATED.BANNED
                        else 'Приватный канал.'
                        if chat.deactivated_cause == CHAT_DEACTIVATED.PRIVATE
                        else 'Для рассылки в этом чате необходимо обладать '
                        'правами администратора.'
                        if chat.deactivated_cause
                        == CHAT_DEACTIVATED.ADMIN_REQUIRED
                        else 'Рассылка в этот канал воспрещена.'
                        if chat.deactivated_cause
                        == CHAT_DEACTIVATED.WRITE_FORBIDDEN
                        else 'Неизвестна.'
                    )
                    if chat.deactivated_cause is not None
                    else None,
                    '__Добавлен:__ '
                    + chat.created_at.astimezone().strftime(
                        r'%Y-%m-%d %H:%M:%S'
                    )
                    if chat.created_at is not None
                    else None,
                    '__Обновлен:__ '
                    + chat.updated_at.astimezone().strftime(
                        r'%Y-%m-%d %H:%M:%S'
                    )
                    if chat.updated_at is not None
                    else None,
                )
                if _ is not None
            ),
            reply_markup=IKM(
                [
                    [
                        IKB('Обновить', data(self.SENDER_CHAT.REFRESH)),
                        IKB(
                            'Выключить для рассылки'
                            if chat.active
                            else 'Включить для рассылки',
                            data(self.SENDER_CHAT.ACTIVATE),
                        ),
                    ],
                    (
                        [
                            IKB(
                                'Сбросить период',
                                data(self.SENDER_CHAT.PERIOD_RESET),
                            )
                        ]
                        if getattr(ChatModel.period.default, 'arg', None)
                        is not None
                        and chat.period != ChatModel.period.default
                        else []
                    )
                    + [
                        IKB(
                            'Изменить период',
                            data(self.SENDER_CHAT.PERIOD_CHANGE),
                        )
                    ],
                    (
                        [
                            IKB(
                                'Удалить категорию',
                                data(self.SENDER_CHAT.REMOVE_CATEGORY),
                            )
                        ]
                        if chat.category_id is not None
                        else []
                    )
                    + [
                        IKB(
                            'Изменить категорию'
                            if chat.category_id is not None
                            else 'Добавить категорию',
                            data(self.SENDER_CHAT.CATEGORY),
                        )
                    ],
                    [IKB('Назад', data(self.SENDER_CHAT.LIST))],
                ]
            ),
        )

    async def _update_chat_period(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> bool:
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
                'Добавить период для чата возможно только через сообщение.'
            )
        input, chat_id = chat_id, chat_id.chat_id

        chat = await self.storage.Session.get(ChatModel, input.data.args)
        if chat is None:
            return await abort('Чат не найден.')

        if not isinstance(message_id, Message):
            message_id = await self.get_messages(chat_id, message_id)
        raw_numbers = message_id.text.split()[-4:]
        if not raw_numbers or raw_numbers[0] == message_id.text:
            raw_numbers = message_id.text.split(':')[-4:]

        try:
            numbers: list[float] = [float(_ or 0) for _ in raw_numbers]
        except ValueError:
            return await abort(
                'Не удалось распознать введенные данные. Попробуйте еще раз.',
                add=True,
            )

        fractions = ('days', 'hours', 'minutes', 'seconds')
        chat.period = timedelta(
            **dict(zip(fractions[-len(numbers) :], numbers))
        )
        await self.storage.Session.commit()
        return True

    async def _add_chats(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> bool:
        """Update sender chats in the database taken from `message`."""

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
            return await abort('Добавить чаты можно только через сообщение.')
        input, chat_id = chat_id, chat_id.chat_id
        if isinstance(_message_id := message_id, Message):
            message_id = message_id.id

        def modify_kwargs(*keys: str, **kwargs: Any) -> None:
            nonlocal input
            _kw = {k: v for k, v in input.data.kwargs.items() if k not in keys}
            input.data = input.data.__copy__(kwargs=_kw | kwargs)

        if data is not None and data.command == self.SENDER_CHAT.REFRESH:
            refresh = not bool(input.data.kwargs.get('refresh'))
            modify_kwargs(refresh=int(refresh))
            await self.storage.Session.commit()
            await self.edit_message_reply_markup(
                *(chat_id, message_id),
                IKM(
                    [
                        [
                            IKB(
                                'Обновлять существующие чаты: Да'
                                if refresh
                                else 'Обновлять существующие чаты: Нет',
                                self.SENDER_CHAT.REFRESH,
                            )
                        ],
                        [IKB('Отменить', self.INPUT.CANCEL)],
                    ]
                ),
            )
            return False

        if 'category_id' not in input.data.kwargs:
            used_message = InputMessageModel(
                message_id=message_id, input=input
            )
            self.storage.Session.add(used_message)
            await self.storage.Session.commit()
            return await abort('Сначала выберите категорию в сообщении выше.')

        if not isinstance(_message_id, Message):
            _message_id = await self.get_messages(chat_id, _message_id)
        self.storage.Session.add(
            InputMessageModel.from_message(_message_id, input)
        )
        await self.storage.Session.commit()

        chat_links: dict[tuple[str], Optional[ChatModel]] = {}
        for line in _message_id.text.splitlines():
            line_chat = None
            line_links = tuple(_.strip(', ') for _ in line.split(' '))
            if not input.data.kwargs.get('refresh'):
                for link in line_links:
                    if link.startswith('@'):
                        q = select(ChatModel).filter_by(username=link)
                    elif self.INVITE_LINK_RE.search(link):
                        q = select(ChatModel).filter_by(invite_link=link)
                    else:
                        continue
                    if line_chat := await self.storage.Session.scalar(q):
                        break
            chat_links[line_links] = line_chat
        if not chat_links:
            return await abort(
                'Чатов не обнаружено. Попробуйте еще раз.', add=True
            )

        finish_message_id = input.data.kwargs.get('f_msg_id')
        if isinstance(finish_message_id, int):
            with suppress(RPCError):
                await self.edit_message_reply_markup(
                    chat_id, finish_message_id
                )
            modify_kwargs('f_msg_id')
            await self.storage.Session.commit()

        n_message_id = input.data.kwargs.get('n_msg_id')
        if isinstance(n_message_id, int):
            with suppress(RPCError):
                await self.delete_messages(chat_id, n_message_id)
            modify_kwargs('n_msg_id')
            await self.storage.Session.commit()

        _text = 'Начинаю подгрузку чатов...'
        n_msg = await self.send_message(chat_id, _text)
        modify_kwargs(n_msg_id=(n_message_id := n_msg.id))
        await self.storage.Session.commit()

        _ = can_update, new_chats = Value('b', 1), Value('i', 0)
        __ = successes, errors = Value('i', 0), Value('i', 0)

        total_count: int = len(chat_links)
        existing: Optional[int] = None
        if not input.data.kwargs.get('refresh'):
            existing = sum(_ is not None for _ in chat_links.values())
            total_count -= existing

        check_chats = [k for k, v in chat_links.items() if v is None]
        if not check_chats:
            finish_message = await self._chats_add_notify(
                *(input, n_message_id, data, query_id),
                *(total_count, existing, *_, *__),
                finish=True,
            )
            if isinstance(finish_message, Message):
                modify_kwargs('n_msg_id', f_msg_id=finish_message.id)
                await self.storage.Session.commit()
            return False

        self.scheduler.add_job(
            self.storage.scoped(self._chats_add_notify),
            trigger='interval',
            seconds=1,
            id=f'add_chats_add_notify:{chat_id}',
            args=(
                *(input, n_message_id, data, query_id),
                *(total_count, existing, *_, *__),
            ),
            replace_existing=True,
        )

        workers_flood: dict[int, float] = {
            phone_number: float('-inf')
            async for phone_number in (
                await self.storage.Session.stream_scalars(
                    select(ClientModel.phone_number)
                    .filter(
                        ClientModel.valid,
                        exists(text('NULL'))
                        .where(
                            SessionModel.phone_number
                            == ClientModel.phone_number
                        )
                        .where(SessionModel.user_id.is_not(None)),
                    )
                    .order_by(ClientModel.created_at)
                )
            )
        }
        if not workers_flood:
            return await abort(
                'На данный момент нет свободных ботов для обработки чатов.'
            )

        async def update_chat(chat: Chat, chat_link: str, /) -> None:
            if not chat.invite_link and self.INVITE_LINK_RE.search(chat_link):
                chat.invite_link = chat_link

            category_id = input.data.kwargs.get('category_id')
            sender_chat: Optional[ChatModel] = await self.storage.Session.get(
                ChatModel, chat.id
            )
            if sender_chat is None:
                new_chats.value += 1
                self.storage.Session.add(
                    ChatModel(
                        id=chat.id,
                        title=chat.title,
                        description=chat.description,
                        username=chat.username,
                        invite_link=chat.invite_link,
                        category_id=category_id,
                    )
                )
            else:
                sender_chat.title = chat.title
                sender_chat.description = chat.description
                sender_chat.username = chat.username
                sender_chat.invite_link = chat.invite_link
                if sender_chat.category_id is None:
                    sender_chat.category_id = category_id
            await self.storage.Session.commit()

        chat_index: int = -1
        while chat_index < len(check_chats) - 1:
            for phone_number, flood_wait in workers_flood.items():
                if flood_wait < monotonic():
                    break
            else:
                can_update.value = False
                flood_wait = min(workers_flood.values()) - monotonic()
                n_msg_id = input.data.kwargs.get('n_msg_id')
                sent_msg = await self.send_or_edit(
                    *(input.chat_id, n_msg_id),
                    'Задержка __%s__ из-за ограничений серверов...'
                    % self.morph.timedelta(flood_wait, precision=0),
                )
                if sent_msg is not None and sent_msg.id != n_msg_id:
                    modify_kwargs(n_msg_id=sent_msg.id)
                    await self.storage.Session.commit()
                await sleep(flood_wait)
                continue

            async with auto_init(self.get_worker(phone_number)) as worker:
                async for chat in worker.iter_check_chats(
                    check_chats[chat_index + 1 :],
                    folder_id=1,
                    yield_on_flood=True,
                ):
                    if isinstance(e := chat, CheckChatsFloodWait):
                        workers_flood[phone_number] = monotonic() + e.value
                        for chat in check_chats[chat_index + 1 :]:
                            if chat in e.checked_chats:
                                successes.value += 1
                                can_update.value = True
                                check_chats.remove(chat)
                                await update_chat(
                                    e.checked_chats[chat], chat[0]
                                )
                        break

                    chat_index += 1
                    if chat is None:
                        errors.value += 1
                        can_update.value = True
                        continue

                    try:
                        await update_chat(chat, check_chats[chat_index][0])
                    finally:
                        successes.value += 1
                        can_update.value = True

        can_update.value = False
        finish_message = await self._chats_add_notify(
            *(input, n_message_id, data, query_id),
            *(total_count, existing, *_, *__),
            finish=True,
        )
        finish_message_id = input.data.kwargs.get('n_msg_id')
        if isinstance(finish_message, Message):
            finish_message_id = finish_message.id
        modify_kwargs('n_msg_id', f_msg_id=finish_message_id)
        await self.storage.Session.commit()
        return False

    async def _add_chats_on_finished(
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

        if not isinstance(chat_id, InputModel):
            return await abort(
                'Закончить добавление чатов можно только через сообщение.'
            )
        input, chat_id = chat_id, chat_id.chat_id

        with suppress(JobLookupError):
            self.scheduler.remove_job(f'add_chats_add_notify:{chat_id}')

        n_message_id = input.data.kwargs.get('n_msg_id')
        if isinstance(n_message_id, int):
            with suppress(RPCError):
                await self.delete_messages(chat_id, n_message_id)

        finish_message_id = input.data.kwargs.get('f_msg_id')
        if isinstance(finish_message_id, int):
            with suppress(RPCError):
                await self.edit_message_reply_markup(
                    chat_id, finish_message_id
                )

        if input.success or data is None:
            with suppress(RPCError):
                await self.delete_messages(input.chat_id, input.message_id)

        if input.success:
            return await self.start_message(input, message_id, data, query_id)
        elif data is not None:
            return await self.start_message(input, None, data, query_id)

    async def _chats_add_notify(
        self: 'AdBotClient',
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]],
        data: Optional[Query],
        query_id: Optional[int],
        /,
        total_chats: int,
        existing: Optional[int],
        can_update: ValueProxy[bool],
        new_chats: ValueProxy[int],
        successes: ValueProxy[int],
        errors: ValueProxy[int],
        *,
        finish: bool = False,
    ) -> Optional[Message]:
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

        if not finish and not can_update.value:
            return None
        elif not isinstance(chat_id, InputModel):
            return await abort(
                'Обновить состояние добавления чатов можно только через '
                'сообщение.'
            )
        input, chat_id = chat_id, chat_id.chat_id
        if isinstance(message_id, Message):
            message_id = message_id.id

        def modify_kwargs(*keys: str, **kwargs: Any) -> None:
            nonlocal input
            _kw = {k: v for k, v in input.data.kwargs.items() if k not in keys}
            input.data = input.data.__copy__(kwargs=_kw | kwargs)

        try:
            message = await self.send_or_edit(
                *(chat_id, message_id),
                '\n'.join(
                    _
                    for _ in (
                        'Обработано **{total} из {total_chats}** '
                        '{chats_word}.',
                        '',
                        'Добавлено **{new_count}** {new_word}.',
                        'Успешных: **{successes_count}**.',
                        'Ошибок: **{errors_count}**.',
                        f'Существующих: **{existing}**.'
                        if existing is not None
                        else None,
                    )
                    if _ is not None
                ).format(
                    total_chats=total_chats,
                    total=successes.value + errors.value,
                    new_count=new_chats.value,
                    successes_count=successes.value,
                    errors_count=errors.value,
                    chats_word=self.morph.plural(
                        total_chats, 'чат', case='gent'
                    ),
                    new_word=self.morph.plural(
                        new_chats.value, 'новый', 'чат'
                    ),
                    # successes_word=self.morph.plural(successes.value, 'чат'),
                    # errors_word=self.morph.plural(errors.value, 'шт'),
                ),
                reply_markup=IKM([[IKB('Завершить', Query(self.INPUT._SELF))]])
                if finish
                else None,
            )
            notifier_msg_id = input.data.kwargs.get('n_msg_id')
            if message is not None and message.id != notifier_msg_id:
                modify_kwargs(n_msg_id=message.id)
                await self.storage.Session.commit()
            return message
        finally:
            await self.storage.Session.remove()
