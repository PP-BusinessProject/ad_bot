"""The module for processing SenderCommands."""

from asyncio import sleep
from contextlib import suppress
from datetime import datetime, timedelta
from multiprocessing import Value
from multiprocessing.managers import ValueProxy
from time import monotonic
from typing import TYPE_CHECKING, Any, Optional, Union

from apscheduler.jobstores.base import JobLookupError
from dateutil.tz.tz import tzlocal
from pyrogram.errors import FloodWait
from pyrogram.errors.rpc_error import RPCError
from pyrogram.types import InlineKeyboardButton as IKB
from pyrogram.types import InlineKeyboardMarkup as IKM
from pyrogram.types import Message
from pyrogram.types.user_and_chats.chat import Chat
from sqlalchemy.orm.strategy_options import contains_eager
from sqlalchemy.orm.util import with_parent
from sqlalchemy.sql.expression import exists, select, text
from sqlalchemy.sql.functions import count

from ...methods.chats.check_chats import CheckChatsFloodWait
from ...models.bots.client_model import ClientModel
from ...models.clients.ad_chat_message_model import AdChatMessageModel
from ...models.clients.ad_chat_model import AdChatModel
from ...models.clients.ad_chat_model import (
    ChatDeactivatedCause as CHAT_DEACTIVATED,
)
from ...models.clients.ad_model import AdModel
from ...models.clients.chat_model import ChatModel
from ...models.clients.user_model import UserRole
from ...models.misc.input_message_model import InputMessageModel
from ...models.misc.input_model import InputModel
from ...models.misc.settings_model import SettingsModel
from ...models.sessions.session_model import SessionModel
from ...utils.query import Query
from .utils import message_header

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

        page_index = data.kwargs.get('c_p') if data is not None else 0
        if not isinstance(page_index, int):
            page_index = 0
        ad = await self.storage.Session.get(AdModel, data.args)
        if ad is None:
            return await abort('Обьявление не существует.')

        chats_count: int = await self.storage.Session.scalar(
            select(count()).where(with_parent(ad, AdModel.chats))
        )
        if not chats_count:
            return await abort(
                'На данный момент нет чатов для рассылки этого обьявления.'
            )

        page_list_size: int = await self.storage.Session.scalar(
            select(SettingsModel.page_list_size).where(
                SettingsModel.id.is_(True)
            )
        )
        total_pages: int = -(-chats_count // page_list_size)
        return await self.send_or_edit(
            *(chat_id, message_id),
            text='Список чатов для рассылки обьявления.'
            '\nВсего {count} {word}.'.format(
                count=chats_count,
                word=self.morph.plural(chats_count, 'чат'),
            ),
            reply_markup=IKM(
                self.hpages(
                    page_index,
                    total_pages,
                    Query(
                        self.CHAT.LIST,
                        ad.chat_id,
                        ad.message_id,
                        c_p=page_index,
                        # kwargs=data.kwargs if data is not None else None,
                    ),
                    kwarg='c_p',
                )
                + [
                    [
                        IKB(
                            ' '.join(
                                (
                                    ad_chat.chat.title,
                                    '⚠️'
                                    if ad_chat.slowmode_wait is not None
                                    and ad_chat.slowmode_wait
                                    > datetime.now(tzlocal())
                                    else '✅'
                                    if ad_chat.active
                                    else '❌',
                                )
                            ),
                            Query(
                                self.CHAT.PAGE,
                                *data.args,
                                ad_chat.chat_id,
                                c_p=page_index,
                            ),
                        )
                    ]
                    for ad_chat in (
                        await self.storage.Session.scalars(
                            select(AdChatModel)
                            .join(AdChatModel.chat)
                            .where(with_parent(ad, AdModel.chats))
                            .order_by(
                                AdChatModel.created_at.desc(),
                                ChatModel.title,
                            )
                            .slice(
                                min(page_index, total_pages - 1)
                                * page_list_size,
                                min(page_index + 1, total_pages)
                                * page_list_size,
                            )
                            .options(contains_eager(AdChatModel.chat))
                        )
                    ).all()
                ]
                + [[IKB('Назад', data(self.AD.PAGE))]]
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
                data = input.data(self.CHAT.PAGE)

        if data is None or data.command == self.CHAT._SELF:
            if data is None:
                data = Query(self.CHAT._SELF)

            message = await self.send_or_edit(
                *(chat_id, message_id),
                'Пришлите список чатов для рассылки по данному обьявлению.',
                reply_markup=IKM([[IKB('Отменить', self.INPUT.CANCEL)]]),
            )

            input = await self.storage.Session.get(InputModel, chat_id)
            if input is None:
                input = InputModel(
                    chat_id=chat_id,
                    message_id=message_id,
                    data=data,
                    query_pattern=self.CHAT.REFRESH.value,
                    on_response=self._add_chats,
                    on_finished=self._add_chats_on_finished,
                    user_role=UserRole.USER,
                    do_add_message=False,
                )
                self.storage.Session.add(input)
                self.storage.Session.add(
                    InputMessageModel.from_message(message, input)
                )
                await self.storage.Session.commit()
            return await self._add_chats(
                input,
                message_id,
                data(self.CHAT.REFRESH),
            )

        ad_chat = await self.storage.Session.get(AdChatModel, data.args)
        if ad_chat is None:
            return await abort('Чат не найден.')

        elif data.command == self.CHAT.REFRESH:
            workers_flood: dict[int, float] = {}
            phone_numbers = await self.storage.Session.scalars(
                select(ClientModel.phone_number)
                .filter(
                    ClientModel.valid,
                    exists(text('NULL'))
                    .where(
                        SessionModel.phone_number == ClientModel.phone_number
                    )
                    .where(SessionModel.user_id.is_not(None)),
                )
                .order_by(ClientModel.created_at)
            )
            for phone_number in phone_numbers.all():
                async with self.worker(phone_number) as worker:
                    try:
                        _chat = await worker.check_chats(
                            (
                                ad_chat.chat_id,
                                ad_chat.chat.invite_link,
                                f'@{ad_chat.chat.username}'
                                if ad_chat.chat.username
                                else None,
                            ),
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

            ad_chat.chat.title = _chat.title
            ad_chat.chat.description = _chat.description
            await self.storage.Session.commit()

        elif data.command == self.CHAT.ACTIVATE:
            if not ad_chat.active:
                ad_chat.deactivated_cause = None
            ad_chat.active = not ad_chat.active
            await self.storage.Session.commit()

        elif data.command == self.CHAT.PERIOD_RESET:
            ad_chat.period = AdChatModel.period.default.arg
            await self.storage.Session.commit()

        elif data.command == self.CHAT.PERIOD_CHANGE:
            self.storage.Session.add(
                InputModel(
                    chat_id=chat_id,
                    message_id=message_id,
                    data=data,
                    on_response=self._update_chat_period,
                    on_finished=self.chat_message,
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

        messages_count: int = await self.storage.Session.scalar(
            select(count()).where(with_parent(ad_chat, AdChatModel.messages))
        )
        if data.command == self.CHAT.JOURNAL:
            if not messages_count:
                return await abort(
                    'У этого объявления нет пересланных сообщений.'
                )

            journal_page_index = data.kwargs.get('aj_cp') if data else None
            if not isinstance(journal_page_index, int):
                journal_page_index = 0

            page_list_size: int = await self.storage.Session.scalar(
                select(SettingsModel.page_list_size).where(
                    SettingsModel.id.is_(True)
                )
            )
            total_journal_pages = -(-messages_count // page_list_size)
            messages = await self.storage.Session.scalars(
                select(AdChatMessageModel)
                .where(with_parent(ad_chat, AdChatModel.messages))
                .order_by(AdChatMessageModel.timestamp.desc())
                .slice(
                    min(journal_page_index, total_journal_pages - 1)
                    * page_list_size,
                    min(journal_page_index + 1, total_journal_pages)
                    * page_list_size,
                )
                .options(contains_eager(AdChatMessageModel.ad_chat))
            )
            if not (messages := messages.all()):
                return await abort('Для этого чата нет высланных сообщений.')

            return await self.send_or_edit(
                *(chat_id, message_id),
                text='\n'.join(
                    _
                    for _ in (
                        message_header(self, ad_chat, chat_id),
                        '',
                        '**Всего сообщений в журнале:** %s шт'
                        % messages_count,
                    )
                    if _ is not None
                ),
                reply_markup=[
                    [
                        IKB(
                            ' '.join(
                                _
                                for _ in (
                                    sent_ad.timestamp.astimezone(
                                        tzlocal()
                                    ).strftime(
                                        r'%H:%M:%S'
                                        if datetime.now(tzlocal()).date()
                                        == sent_ad.timestamp.astimezone(
                                            tzlocal()
                                        ).date()
                                        else r'%Y-%m-%d %H:%M:%S'
                                    )
                                    if sent_ad.timestamp is not None
                                    else str(sent_ad.chat_id),
                                    sent_ad.ad_chat.chat.title
                                    if sent_ad.ad_chat
                                    else None,
                                )
                                if _
                            ),
                            url=sent_ad.link,
                        )
                    ]
                    for sent_ad in messages
                ]
                + self.hpages(
                    journal_page_index,
                    total_journal_pages,
                    Query(
                        self.CHAT.JOURNAL,
                        ad_chat.ad_chat_id,
                        ad_chat.ad_message_id,
                        ad_chat.chat_id,
                        **(data.kwargs if data is not None else {}),
                    ),
                    kwarg='aj_cp',
                )
                + [[IKB('Назад', data(self.CHAT.PAGE))]],
            )

        return await self.send_or_edit(
            *(chat_id, message_id),
            '\n'.join(
                _
                for _ in (
                    '**__Чат %s__**'
                    % (
                        f'@{ad_chat.chat.username}'
                        if ad_chat.chat.username
                        else '[%s](%s)'
                        % (ad_chat.chat_id, ad_chat.chat.invite_link or '')
                    ),
                    '',
                    '**Имя:** ' + ad_chat.chat.title
                    if ad_chat.chat.title
                    else None,
                    '**Описание:** ' + ad_chat.chat.description
                    if ad_chat.chat.title and ad_chat.chat.description
                    else None,
                    '**Статус:** '
                    + ('Активен' if ad_chat.active else 'Неактивен'),
                    '**Периодичность:** '
                    + self.morph.timedelta(ad_chat.period),
                    '**Задержка до:** '
                    + ad_chat.slowmode_wait.astimezone().strftime(
                        r'%Y-%m-%d %H:%M:%S'
                    )
                    if ad_chat.slowmode_wait is not None
                    and ad_chat.slowmode_wait > datetime.now(tzlocal())
                    else None,
                    '**Причина деактивации:** '
                    + (
                        'Id чата изменился. Попробуйте добавить чат заново.'
                        if ad_chat.deactivated_cause
                        == CHAT_DEACTIVATED.PEER_INVALID
                        else 'Канал не валиден.'
                        if ad_chat.deactivated_cause
                        == CHAT_DEACTIVATED.INVALID
                        else 'Канал был забанен.'
                        if ad_chat.deactivated_cause
                        == CHAT_DEACTIVATED.CHANNEL_BANNED
                        else 'Приватный канал.'
                        if ad_chat.deactivated_cause
                        == CHAT_DEACTIVATED.PRIVATE
                        else 'Для рассылки в этом чате необходимо обладать '
                        'правами администратора.'
                        if ad_chat.deactivated_cause
                        == CHAT_DEACTIVATED.ADMIN_REQUIRED
                        else 'Рассылка в этот канал воспрещена.'
                        if ad_chat.deactivated_cause
                        == CHAT_DEACTIVATED.WRITE_FORBIDDEN
                        else 'Канал ограничен.'
                        if ad_chat.deactivated_cause
                        == CHAT_DEACTIVATED.RESTRICTED
                        else 'Юзер забанен.'
                        if ad_chat.deactivated_cause
                        == CHAT_DEACTIVATED.USER_BANNED
                        else 'Неизвестна.'
                    )
                    if ad_chat.deactivated_cause is not None
                    else None,
                    '**Количество пересланных сообщений:** %s шт'
                    % messages_count,
                    '__Добавлен:__ '
                    + ad_chat.created_at.astimezone().strftime(
                        r'%Y-%m-%d %H:%M:%S'
                    )
                    if ad_chat.created_at is not None
                    else None,
                    '__Обновлен:__ '
                    + ad_chat.updated_at.astimezone().strftime(
                        r'%Y-%m-%d %H:%M:%S'
                    )
                    if ad_chat.updated_at is not None
                    else None,
                )
                if _ is not None
            ),
            reply_markup=IKM(
                [
                    [
                        IKB('Обновить', data(self.CHAT.REFRESH)),
                        IKB(
                            'Выключить для рассылки'
                            if ad_chat.active
                            else 'Включить для рассылки',
                            data(self.CHAT.ACTIVATE),
                        ),
                    ],
                    (
                        [
                            IKB(
                                'Сбросить период',
                                data(self.CHAT.PERIOD_RESET),
                            )
                        ]
                        if getattr(AdChatModel.period.default, 'arg', None)
                        is not None
                        and ad_chat.period != AdChatModel.period.default
                        else []
                    )
                    + [
                        IKB(
                            'Изменить период',
                            data(self.CHAT.PERIOD_CHANGE),
                        )
                    ],
                    [
                        IKB(
                            'Назад',
                            Query(
                                self.CHAT.LIST,
                                ad_chat.ad_chat_id,
                                ad_chat.ad_message_id,
                                **(data.kwargs if data else {}),
                            ),
                        )
                    ],
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

        ad_chat = await self.storage.Session.get(AdChatModel, input.data.args)
        if ad_chat is None:
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
        ad_chat.period = timedelta(
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

        if data is not None and data.command == self.CHAT.REFRESH:
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
                                self.CHAT.REFRESH,
                            )
                        ],
                        [IKB('Отменить', self.INPUT.CANCEL)],
                    ]
                ),
            )
            return False

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
            seconds=3,
            id=f'add_chats_add_notify:{chat_id}',
            args=(
                *(chat_id, n_message_id, data, query_id),
                *(total_count, existing, *_, *__),
            ),
            replace_existing=True,
        )

        workers_flood: dict[int, float] = {
            phone_number: float('-inf')
            for phone_number in (
                await self.storage.Session.scalars(
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
            ).all()
        }
        if not workers_flood:
            return await abort(
                'На данный момент нет свободных ботов для обработки чатов.'
            )

        async def update_chat(
            worker: 'AdBotClient',
            chat: Chat,
            chat_link: str,
            /,
        ) -> None:
            if not chat.invite_link and self.INVITE_LINK_RE.search(chat_link):
                chat.invite_link = chat_link

            await worker.archive_chats(chat.id)
            ad_chat: Optional[ChatModel] = await self.storage.Session.get(
                AdChatModel, (*input.data.args, chat.id)
            )
            if ad_chat is None:
                new_chats.value += 1
                _chat = await self.storage.Session.get(ChatModel, chat.id)
                if _chat is not None:
                    _chat.title = chat.title
                    _chat.description = chat.description
                    _chat.username = chat.username
                    _chat.invite_link = chat.invite_link or _chat.invite_link
                self.storage.Session.add(
                    AdChatModel(
                        ad_chat_id=input.data.args[0],
                        ad_message_id=input.data.args[1],
                        chat=_chat
                        or ChatModel(
                            id=chat.id,
                            title=chat.title,
                            description=chat.description,
                            username=chat.username,
                            invite_link=chat.invite_link,
                        ),
                    ),
                )
            else:
                ad_chat.chat.title = chat.title
                ad_chat.chat.description = chat.description
                ad_chat.chat.username = chat.username
                ad_chat.chat.invite_link = chat.invite_link
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

            async with self.worker(phone_number) as worker:
                async for chat in worker.iter_check_chats(
                    check_chats[chat_index + 1 :],
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
                                    worker, e.checked_chats[chat], chat[0]
                                )
                        break

                    chat_index += 1
                    if chat is None:
                        errors.value += 1
                        can_update.value = True
                        continue

                    try:
                        await update_chat(
                            worker, chat, check_chats[chat_index][0]
                        )
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
            return await self.ad_message(input, message_id, data, query_id)
        elif data is not None:
            return await self.ad_message(input, None, data, query_id)

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
        if not isinstance(chat_id, InputModel):
            input = await self.storage.Session.get(InputModel, chat_id)
            if input is None:
                return await abort(
                    'Обновить состояние добавления чатов можно только через '
                    'сообщение.'
                )
        else:
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
