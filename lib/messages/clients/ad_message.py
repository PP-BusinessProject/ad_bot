"""The module for processing AdCommands."""

from contextlib import suppress
from typing import TYPE_CHECKING, Optional, Union

from pyrogram.errors import RPCError
from pyrogram.types import InlineKeyboardButton as IKB
from pyrogram.types import InlineKeyboardMarkup as IKM
from pyrogram.types import Message
from sqlalchemy.orm import noload
from sqlalchemy.orm.util import with_parent
from sqlalchemy.sql.expression import delete, exists, select, text
from sqlalchemy.sql.functions import count

from ...models.bots.sent_ad_model import SentAdModel
from ...models.clients.ad_model import AdModel
from ...models.clients.bot_model import BotModel
from ...models.clients.user_model import UserRole
from ...models.misc.category_model import CategoryModel
from ...models.misc.input_message_model import InputMessageModel
from ...models.misc.input_model import InputModel
from ...models.misc.settings_model import SettingsModel
from ...utils.query import Query
from .utils import message_header

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class AdMessage(object):
    async def ad_message(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> Message:
        """
        Show the ad message for one of the bot's ads.

        The controls for horizontal switching are shown if bot has more than
        one ad. This message can be seen from user's and admin's perspective.

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
            The sent message with requested ad.
        """

        async def abort(
            text: str,
            /,
            *,
            show_alert: bool = True,
        ) -> Union[bool, Message]:
            nonlocal self, query_id, chat_id
            return await self.answer_edit_send(
                *(query_id, chat_id, message_id, _query(self.AD.PAGE)),
                text=text,
                show_alert=show_alert,
            )

        def _query(command: str, /) -> Query:
            nonlocal data, ad, page_index
            if data is not None:
                return data(
                    command=command,
                    args=(ad.chat_id, ad.message_id),
                    kwargs=data.kwargs | dict(a_p=page_index),
                )
            return Query(command, ad.chat_id, ad.message_id, a_p=page_index)

        if isinstance(chat_id, InputModel):
            input, chat_id = chat_id, chat_id.chat_id
            if input.message_id is not None:
                message_id = input.message_id
            if input.data is not None:
                data = input.data(self.AD.PAGE)
        if isinstance(message_id, Message):
            message_id = message_id.id

        if data is None or data.command == self.AD._SELF:
            if await self.storage.Session.scalar(
                select(
                    exists(text('NULL')).where(InputModel.chat_id == chat_id)
                )
            ):
                return await abort('Вы уже добавляете объявление.')

            self.storage.Session.add(
                InputModel(
                    chat_id=chat_id,
                    message_id=message_id
                    if isinstance(message_id, int)
                    else message_id.id,
                    data=data(kwargs=data.kwargs | dict(a_p=-1)),
                    on_response=self._ad_add,
                    on_finished=self.ad_message,
                    user_role=UserRole.USER,
                )
            )
            await self.storage.Session.commit()
            return await self.send_or_edit(
                *(chat_id, message_id),
                'Пришлите ваше объявление в ответ на это сообщение.',
                reply_markup=IKM(
                    [[IKB('Отменить', Query(self.INPUT.CANCEL))]]
                ),
            )

        page_index = data.kwargs.get('a_p') if data is not None else None
        if not isinstance(page_index, int):
            page_index = 0

        ad: Optional[AdModel] = None
        bot: Optional[BotModel] = None
        if data is not None and data.args and isinstance(data.args[0], int):
            if data.args[0] < 0:
                ad = await self.storage.Session.get(AdModel, data.args)
                if ad is None:
                    return await abort('Объявление не найдено.')
                bot = ad.owner_bot
                page_index = await self.storage.Session.scalar(
                    select(count())
                    .where(with_parent(ad.owner_bot, BotModel.ads))
                    .where(AdModel.message_id < ad.message_id)
                )
            else:
                bot = await self.storage.Session.get(BotModel, data.args)
                if bot is None:
                    return await abort('Бот не найден.')
        else:
            bot = await self.storage.Session.get(BotModel, (chat_id, 0))
            if bot is None:
                return await abort('У вас нет ботов.')

        ads_count: int = await self.storage.Session.scalar(
            select(count()).where(with_parent(bot, BotModel.ads))
        )
        if not ads_count:
            return await self.bot_message(
                chat_id=chat_id,
                message_id=message_id,
                data=data(self.BOT.PAGE, args=(bot.owner.id, bot.id))
                if data is not None
                else Query(self.BOT.PAGE, bot.owner.id, bot.id),
                query_id=query_id,
            )

        if ad is None:
            if page_index < 0 or page_index > ads_count - 1:
                page_index = ads_count - 1
            ad: AdModel = await self.storage.Session.scalar(
                select(AdModel)
                .filter_by(bot_owner_id=bot.owner.id, bot_id=bot.id)
                .offset(page_index)
                .limit(1)
            )

        if data.command == self.AD.VIEW:
            if ad.corrupted:
                return await self.ad_message(
                    chat_id=chat_id,
                    message_id=message_id,
                    data=_query(self.AD._SELF),
                )

            try:
                _ad_message = await self.forward_messages(
                    *(chat_id, ad.chat_id, ad.message_id),
                    drop_author=True,
                )
            except RPCError:
                ad.corrupted = True
                await self.storage.Session.commit()
                await abort('Объявление повреждено.')
            else:
                with suppress(RPCError):
                    if _ad_message.reply_markup is None:
                        return await _ad_message.edit_reply_markup(
                            IKM([[IKB('Скрыть', self.SERVICE.HIDE)]])
                        )
                return _ad_message

        elif data.command == self.AD.ACTIVE:
            ad.active = not ad.active
            await self.storage.Session.commit()

        elif data.command == self.AD.BAN:
            if not ad.banned:
                ad.active = False
            ad.banned = not ad.banned
            await self.storage.Session.commit()

        elif data.command == self.AD.CATEGORY_PICK:
            result = await self.category_message(
                *(chat_id, message_id, data, query_id),
                prefix_text='Выбор категории для '
                + message_header(self, ad, chat_id),
                cancel_command=self.AD.PAGE,
            )
            if not isinstance(result, CategoryModel):
                return result
            ad.category_id = result.id
            await self.storage.Session.commit()
            data = data.__copy__(kwargs=data.kwargs | dict(s=None))

        elif data.command == self.AD.CATEGORY_DELETE:
            ad.category_id = None
            await self.storage.Session.commit()

        elif data.command == self.AD.DELETE:
            return await self.send_or_edit(
                *(chat_id, message_id),
                text='Вы уверены что хотите удалить это объявление?',
                reply_markup=IKM(
                    [
                        [
                            IKB('Да', _query(self.AD.DELETE_CONFIRM)),
                            IKB('Нет', _query(self.AD.PAGE)),
                        ]
                    ]
                ),
            )

        elif data.command == self.AD.DELETE_CONFIRM:
            if page_index:
                query = data(
                    self.AD.PAGE,
                    args=(bot.owner.id, bot.id),
                    kwargs=data.kwargs | dict(a_p=page_index - 1),
                )
                callback = self.ad_message
            elif ads_count > 1:
                query = data(
                    self.AD.PAGE,
                    args=(bot.owner.id, bot.id),
                    kwargs=data.kwargs | dict(a_p=None),
                )
                callback = self.ad_message
            elif data is not None:
                query = data(
                    self.BOT.PAGE,
                    args=(bot.owner.id, bot.id),
                    kwargs=data.kwargs | dict(a_p=None),
                )
                callback = self.bot_message
            else:
                query = Query(self.BOT.PAGE, bot.owner.id, bot.id)
                callback = self.bot_message
            await self.storage.Session.delete(ad)
            await self.storage.Session.commit()
            return await callback(
                chat_id=chat_id,
                message_id=message_id,
                data=query,
                query_id=query_id,
            )
        elif data.command == self.AD.JOURNAL_CLEAR:
            return await self.send_or_edit(
                *(chat_id, message_id),
                text='Вы уверены что хотите очистить журнал рассылки этого '
                'объявления?',
                reply_markup=IKM(
                    [
                        [
                            IKB('Да', _query(self.AD.JOURNAL_CLEAR_CONFIRM)),
                            IKB('Нет', _query(self.AD.PAGE)),
                        ]
                    ]
                ),
            )

        elif data.command == self.AD.JOURNAL_CLEAR_CONFIRM:
            await self.storage.Session.execute(
                delete(SentAdModel, with_parent(ad, AdModel.sent_ads))
            )
            await self.storage.Session.commit()

        sent_ads_count: int = await self.storage.Session.scalar(
            select(count()).where(with_parent(ad, AdModel.sent_ads))
        )

        if data.command == self.AD.JOURNAL:
            if not sent_ads_count:
                return await abort(
                    'У этого объявления нет пересланных сообщений.'
                )

            journal_page_index = data.kwargs.get('aj_p') if data else None
            if not isinstance(journal_page_index, int):
                journal_page_index = 0

            page_list_size: int = await self.storage.Session.scalar(
                select(SettingsModel.page_list_size).where(
                    SettingsModel.id.is_(True)
                )
            )
            total_journal_pages = -(-sent_ads_count // page_list_size)
            return await self.send_or_edit(
                *(chat_id, message_id),
                text='\n'.join(
                    _
                    for _ in (
                        message_header(self, SentAdModel(ad=ad), chat_id),
                        '',
                        '**Всего сообщений в журнале:** %s шт'
                        % sent_ads_count,
                    )
                    if _ is not None
                ),
                reply_markup=self.hpages(
                    journal_page_index,
                    total_journal_pages,
                    Query(
                        *(self.AD.JOURNAL, bot.owner.id, bot.id),
                        **(data.kwargs if data is not None else {})
                        | dict(a_p=page_index),
                    ),
                    kwarg='aj_p',
                )
                + [
                    [
                        IKB(
                            sent_ad.timestamp.astimezone().strftime(
                                r'%Y-%m-%d %H:%M:%S'
                            )
                            if sent_ad.timestamp is not None
                            else str(sent_ad.chat_id),
                            url=sent_ad.link,
                        )
                    ]
                    async for sent_ad in (
                        await self.storage.Session.stream_scalars(
                            select(SentAdModel)
                            .where(with_parent(ad, AdModel.sent_ads))
                            .order_by(SentAdModel.timestamp)
                            .slice(
                                min(page_index, total_journal_pages - 1)
                                * page_list_size,
                                min(page_index + 1, total_journal_pages)
                                * page_list_size,
                            )
                            .options(
                                noload(SentAdModel.ad),
                                noload(SentAdModel.chat),
                            )
                        )
                    )
                ]
                + [[IKB('Назад', _query(self.AD.PAGE))]],
            )

        category_list = []
        if ad.category_id is not None:
            category: CategoryModel = await self.storage.Session.get(
                CategoryModel, ad.category_id
            )
            category_list.append(category.name)
            while category.parent is not None:
                category_list.append((category := category.parent).name)

        return await self.send_or_edit(
            *(chat_id, message_id),
            text='\n'.join(
                _
                for _ in (
                    message_header(self, ad, chat_id),
                    '',
                    '**Статус:** {}'.format(
                        '__Не найдено__'
                        if ad.corrupted
                        else '__Заблокировано__'
                        if ad.banned
                        else 'Включено'
                        if ad.active
                        else 'Отключено'
                    ),
                    '**Текущая категория:** {}'.format(
                        ' > '.join(reversed(category_list))
                        if category_list
                        else '__Отсутствует__'
                    ),
                    '**Количество пересланных сообщений:** %s шт'
                    % sent_ads_count,
                )
                if _ is not None
            ),
            reply_markup=IKM(
                self.hpages(
                    page_index,
                    ads_count,
                    Query(
                        *(self.AD.PAGE, bot.owner.id, bot.id),
                        **(data.kwargs if data is not None else {}),
                    ),
                    kwarg='a_p',
                )
                + (
                    [
                        [
                            IKB('Обновить', _query(self.AD.PAGE)),
                            IKB('Просмотреть', _query(self.AD.VIEW)),
                        ],
                        (
                            [
                                IKB(
                                    'Удалить категорию',
                                    _query(self.AD.CATEGORY_DELETE),
                                )
                            ]
                            if ad.category_id is not None
                            else []
                        )
                        + [
                            IKB(
                                'Выбрать категорию'
                                if ad.category_id is None
                                else 'Изменить категорию',
                                _query(self.AD.CATEGORY_PICK),
                            )
                        ],
                    ]
                    if not ad.corrupted
                    else []
                )
                + [
                    [
                        IKB(
                            'Очистить журнал рассылки',
                            _query(self.AD.JOURNAL_CLEAR),
                        ),
                        IKB(
                            'Просмотреть журнал рассылки',
                            _query(self.AD.JOURNAL),
                        ),
                    ]
                ]
                + (
                    [
                        (
                            [
                                IKB(
                                    'Разблокировать'
                                    if ad.banned
                                    else 'Заблокировать',
                                    _query(self.AD.BAN),
                                )
                            ]
                            if chat_id != ad.owner_bot.owner.id
                            else []
                        )
                        + [
                            IKB(
                                'Выключить' if ad.active else 'Включить',
                                _query(self.AD.ACTIVE),
                            )
                        ]
                    ]
                    if not ad.corrupted
                    else []
                )
                + [
                    [IKB('Удалить', _query(self.AD.DELETE))],
                    [
                        IKB(
                            'Назад',
                            Query(
                                *(self.BOT.PAGE, bot.owner.id, bot.id),
                                **(data.kwargs if data is not None else {}),
                            ),
                        ),
                    ],
                ],
            ),
        )

    async def _ad_add(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> bool:
        """
        Update the ad in the database.

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
                'Добавить объявление возможно только через сообщение.'
            )
        input, chat_id = chat_id, chat_id.chat_id
        if isinstance(message_id, Message):
            message_id = message_id.id

        bot: Optional[BotModel] = await self.storage.Session.get(
            BotModel, input.data.args
        )
        if bot is None:
            return await abort('Бот не найден.')

        elif bot.owner.service_id is None:
            return await abort(
                'Личный канал пользователя не создан.'
                if chat_id != bot.owner_id
                else 'У вас нет личного канала.'
            )

        elif not await self.check_chats(
            (bot.owner.service_id, bot.owner.service_invite)
        ):
            return await abort(
                'У бота нет доступа к личному каналу пользователя.'
                if chat_id != bot.owner_id
                else 'У бота нет доступа к вашему личному каналу.'
            )

        elif bot.owner.service_invite is None:
            invite_link = await self.export_chat_invite_link(
                bot.owner.service_id
            )
            bot.owner.service_invite = invite_link.invite_link
            await self.storage.Session.commit()

        try:
            copied_message = await self.forward_messages(
                bot.owner.service_id, chat_id, message_id
            )
        except RPCError as _:
            return await abort(
                'Произошла ошибка, попробуйте еще раз.', add=True
            )

        confirm_message_id: Optional[int] = None
        if not (chat_id != bot.owner.id or bot.owner.role >= UserRole.SUPPORT):

            def _query(command: str, /) -> Query:
                c = copied_message
                return Query(command, input.data.command, c.chat.id, c.id)

            confirm_message = await copied_message.reply(
                f'Подтвердить объявление #{copied_message.id} для бота '
                f'#{bot.id}?',
                quote=True,
                reply_markup=IKM(
                    [
                        [
                            IKB('Да', _query(self.SERVICE.APPROVE)),
                            IKB('Нет', _query(self.SERVICE.DENY)),
                        ]
                    ]
                ),
            )
            confirm_message_id = confirm_message.id
            await abort(
                'Ваше объявление отправлено на согласование с администрацией.'
            )

        self.storage.Session.add(
            AdModel(
                bot_owner_id=bot.owner.id,
                bot_id=bot.id,
                chat_id=copied_message.chat.id,
                message_id=copied_message.id,
                confirm_message_id=confirm_message_id,
            )
        )
        await self.storage.Session.commit()
        return True
