"""The module for processing BotCommands."""

from contextlib import suppress
from typing import TYPE_CHECKING, Optional, Union

from pyrogram.errors.rpc_error import RPCError
from pyrogram.raw.types.channel_participant_admin import \
    ChannelParticipantAdmin
from pyrogram.raw.types.channel_participant_creator import \
    ChannelParticipantCreator
from pyrogram.types import InlineKeyboardButton as IKB
from pyrogram.types import InlineKeyboardMarkup as IKM
from pyrogram.types import Message
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm.util import with_parent
from sqlalchemy.sql.expression import exists, select, text, update
from sqlalchemy.sql.functions import count

from ...models.bots.client_model import ClientModel
from ...models.clients.ad_model import AdModel
from ...models.clients.bot_model import BotModel
from ...models.clients.user_model import UserModel, UserRole
from ...models.misc.input_model import InputModel
from ...models.misc.settings_model import SettingsModel
from ...models.sessions.session_model import SessionModel
from ...utils.pyrogram import auto_init
from ...utils.query import Query
from .utils import message_header, subscription_text

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class BotMessage(object):
    async def bots_list(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        """
        Show the message with a list of current active users.

        Only applicable for `UserRole.SUPPORT` and greater.

        The user that called this page, can only see users with role below his
        own.

        If there aren't any users at the moment, sends an info message.

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
            The sent message with the list of current active users.

        See Also:
            * `~plugins.horizontal_pages.hpages` for info on the page keyboard.
            * `~messages.users_message._user_page_text` for detailed info on
            how the page buttons with the user info are formed.
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

        page_index = data.kwargs.get('u_p') if data is not None else None
        if not isinstance(page_index, int):
            page_index = 0

        user_role: UserRole = await self.storage.Session.scalar(
            select(UserModel.role).filter_by(id=chat_id).limit(1)
        )
        users_count: int = await self.storage.Session.scalar(
            select(count()).where(UserModel.role < user_role)
        )
        if not users_count:
            return await abort('На данный момент нет активных пользователей.')

        def user_page_text(
            user: UserModel,
            bot: Optional[BotModel] = None,
            /,
        ) -> str:
            """
            Return the text for :meth:`~AdBotClient.users_page` button.

            Shows if the `user` is subscribed, his id and the name of his
            `bot`.

            If `bot` is None, only `user's` id is shown.
            """
            icon = text = None
            if bot is not None:
                text_parts = [bot.first_name]
                if bot.last_name:
                    text_parts.append(bot.last_name)
                text = ' '.join((*text_parts, f'({user.id})'))
            else:
                text = str(user.id)

            if user.role >= UserRole.SUPPORT:
                icon = '🛡️'
            elif user.is_subscribed:
                icon = '✅'
            else:
                icon = '❌'
            return ' '.join(_ for _ in (icon, text) if _ is not None) or str(
                user.id
            )

        page_list_size: int = await self.storage.Session.scalar(
            select(SettingsModel.page_list_size).where(
                SettingsModel.id.is_(True)
            )
        )
        total_pages: int = -(-users_count // page_list_size)
        return await self.send_or_edit(
            *(chat_id, message_id),
            text='Список активных пользователей. Всего {count} {word}.'.format(
                count=users_count,
                word=self.morph.plural(users_count, 'пользователь'),
            ),
            reply_markup=IKM(
                [
                    [
                        IKB(
                            user_page_text(user, bot),
                            Query(self.BOT.PAGE, user.id, u_p=page_index),
                        )
                    ]
                    async for user, bot in await self.storage.Session.stream(
                        select(UserModel, BotModel)
                        .join(UserModel.bots, isouter=True)
                        .group_by(UserModel.id)
                        .having(UserModel.role < user_role)
                        .slice(
                            min(page_index, total_pages - 1) * page_list_size,
                            min(total_pages + 1, page_index) * page_list_size,
                        )
                        .options(contains_eager(BotModel.owner))
                    )
                ]
                + self.hpages(
                    page_index, total_pages, Query(self.BOT.LIST), kwarg='u_p'
                )
                + [[IKB('Назад', Query(self.SERVICE._SELF))]]
            ),
        )

    async def bot_message(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Union[str, bytes, Query]] = None,
        query_id: Optional[int] = None,
    ) -> Message:
        """
        Show the bot message for an active user.

        If user does not have any bots, new bot is automatically created.

        If user has more than one bot, the controls for horizontal switching
        are shown. Otherwise, they are hidden.

        This message can be seen from user's and admin's perspective.
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

        def _query(command: str, /) -> Query:
            if data is None:
                return Query(command, bot.owner.id, bot.id, b_p=page_index)
            return data(
                command,
                args=(bot.owner.id, bot.id),
                kwargs=(data.kwargs if data else {}) | dict(b_p=page_index),
            )

        if isinstance(chat_id, InputModel):
            chat_id = chat_id.chat_id
        if isinstance(_message_id := message_id, Message):
            message_id = message_id.id

        page_index, bot_owner_id, bot_id = None, None, None
        if data is not None:
            bot_owner_id, bot_id, *_ = *data.args, None, None
            page_index = data.kwargs.get('b_p')
        if not isinstance(page_index, int):
            page_index = 0
        if not isinstance(bot_owner_id, int):
            bot_owner_id = chat_id

        bots_count: int = await self.storage.Session.scalar(
            select(count()).where(BotModel.owner_id == bot_owner_id)
        )
        if not bots_count and bot_owner_id != chat_id:
            return await abort(
                'У данного пользователя нет подключенных ботов.'
            )

        elif (data is None or data.command == self.BOT._SELF) or (
            not bots_count and data.command == self.BOT.PAGE
        ):
            owner = await self.storage.Session.get(UserModel, bot_owner_id)
            phone_number: int
            async for phone_number in (
                await self.storage.Session.stream_scalars(
                    select(ClientModel.phone_number)
                    .where(ClientModel.valid)
                    .where(
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
                    owner = await self.storage.Session.merge(
                        await worker.initialize_user_service(
                            owner, promote_users=self.username
                        )
                    )
                    await self.storage.Session.commit()
                    break
            else:
                return await abort(
                    'На данный момент нет свободного бота для создания '
                    'вашего личного канала. Попробуйте еще раз позже.'
                )
            bot: BotModel = BotModel(
                id=bots_count,
                owner_id=bot_owner_id,
                forward_to_id=bot_owner_id,
                owner=owner,
            )
            ads_count = banned_ads_count = 0
            if bots_count:
                page_index += 1
            bots_count += 1
            await self.get_profile_settings(bot, force=True)
            self.storage.Session.add(bot)
            await self.storage.Session.commit()

            if chat_id == bot.owner.id and bot.owner.role < UserRole.SUPPORT:

                def _query2(command: str, /) -> Query:
                    q = _query(command)
                    return q(args=(self.SETTINGS._SELF.value,) + q.args)

                confirm_message = await self.send_message(
                    bot.owner.service_id,
                    '\n'.join(
                        _
                        for _ in (
                            f'Создание бота #{bot.id} со следующими полями:',
                            '',
                            '**Имя:** %s' % bot.first_name
                            if bot.first_name
                            else None,
                            '**Фамилия:** %s' % bot.last_name
                            if bot.last_name
                            else None,
                            '**Биография:** %s' % bot.about
                            if bot.about
                            else None,
                            '**Юзернейм:** %s'
                            % ('@' + bot.username.removeprefix('@'))
                            if bot.username
                            else None,
                            '**Контакт:** [{name}](tg://user?id={id})'.format(
                                id=bot.forward_to_id,
                                name='пользователь',
                            )
                            if bot.forward_to_id
                            else None,
                            '**Автоответ:** __Есть__'
                            if bot.reply_message_id is not None
                            else None,
                            '**Аватар:** Есть'
                            if bot.avatar_message_id is not None
                            else None,
                            '',
                            'Подтвердить?',
                        )
                        if _ is not None
                    ),
                    reply_markup=IKM(
                        [
                            [
                                IKB('Да', _query2(self.SERVICE.APPROVE)),
                                IKB('Нет', _query2(self.SERVICE.DENY)),
                            ]
                        ]
                    ),
                )
                bot.confirm_message_id = confirm_message.id
                await self.storage.Session.commit()

        elif bots_count:
            bot = None
            if isinstance(bot_id, int):
                bot = await self.storage.Session.get(
                    BotModel, (bot_owner_id, bot_id)
                )
                if bot is not None:
                    page_index = await self.storage.Session.scalar(
                        select(count())
                        .where(with_parent(bot.owner, UserModel.bots))
                        .where(BotModel.id < bot.id)
                    )
            if bot is None:
                if page_index < 0 or page_index > bots_count - 1:
                    page_index = bots_count - 1
                bot = await self.storage.Session.scalar(
                    select(BotModel)
                    .filter_by(owner_id=bot_owner_id)
                    .offset(page_index)
                    .limit(1)
                )

            ads_count: int = await self.storage.Session.scalar(
                select(count()).where(with_parent(bot, BotModel.ads))
            )
            banned_ads_count: int = await self.storage.Session.scalar(
                select(count()).where(
                    with_parent(bot, BotModel.ads) & AdModel.banned
                )
            )

        else:
            return await abort('У вас нет созданных ботов.')

        if data is None:
            data = _query(self.BOT.PAGE)

        if data.command == self.BOT.AUTHORIZE:
            if bot.owner.service_id is None:
                return await abort(
                    'Личный канал пользователя не создан.'
                    if chat_id != owner.id
                    else 'У вас нет личного канала.'
                )

            phone_number: int
            async for phone_number in (
                await self.storage.Session.stream_scalars(
                    select(ClientModel.phone_number)
                    .where(ClientModel.valid)
                    .where(
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
                    with suppress(RPCError):
                        if await worker.check_chats(
                            (
                                bot.owner.service_id,
                                bot.owner.service_invite,
                            )
                        ) and isinstance(
                            await self.get_channel_participants(
                                bot.owner.service_id,
                                await worker.storage.user_id(),
                            ),
                            (
                                ChannelParticipantAdmin,
                                ChannelParticipantCreator,
                            ),
                        ):
                            await self.storage.Session.merge(
                                await worker.initialize_user_service(
                                    bot.owner,
                                    promote_users=[self.username, chat_id],
                                )
                            )
                            await self.storage.Session.commit()
                            await abort(
                                'Вам успешно выдано права администратора для '
                                'сервисного чата [пользователя]'
                                f'(tg://user?id={bot.owner.id}).'

                            )
                            break
            else:
                return await abort(
                    'На данный момент нет свободного бота для добавления вас '
                    'в сервисный чат пользователя. Попробуйте еще раз позже.'

                )

        elif data.command == self.BOT.BAN:
            ban = banned_ads_count != ads_count
            await self.storage.Session.execute(
                update(AdModel, values={AdModel.banned: ban})
            )
            await self.storage.Session.commit()

        elif data.command == self.BOT.ROLE:
            diff = 1 if bot.owner.role < UserRole.SUPPORT else -1
            bot.owner.role = UserRole(bot.owner.role.value + diff)
            await self.storage.Session.commit()

        elif data.command == self.BOT.DELETE:
            return await self.send_or_edit(
                *(chat_id, message_id),
                'Вы уверены что хотите удалить этого бота?',
                reply_markup=IKM(
                    [
                        [
                            IKB('Да', _query(self.BOT.DELETE_CONFIRM)),
                            IKB('Нет', _query(self.BOT.PAGE)),
                        ]
                    ]
                ),
            )

        elif data.command == self.BOT.DELETE_CONFIRM:
            await self.storage.Session.delete(bot)
            await self.storage.Session.commit()
            if chat_id != bot.owner.id and bots_count == 1:
                return await self.bots_list(
                    chat_id=chat_id,
                    message_id=_message_id,
                    data=_query(self.BOT.LIST),
                    query_id=query_id,
                )
            elif bots_count == 1:
                return await self.start_message(
                    chat_id=chat_id,
                    message_id=_message_id,
                    data=_query(self.SERVICE._SELF),
                    query_id=query_id,
                )
            else:
                return await self.bot_message(
                    chat_id=chat_id,
                    message_id=_message_id,
                    data=_query(self.BOT.PAGE),
                    query_id=query_id,
                )

        bot_valid: Optional[bool] = None
        bot_has_forward_peer: bool = False
        if bot.phone_number is not None and chat_id == bot.owner.id:
            bot_worker = self.get_worker(bot.phone_number)
            if bot_valid := await bot_worker.validate():
                async with auto_init(bot_worker):
                    bot_has_forward_peer = bool(
                        await bot_worker.check_chats(bot.forward_to_id)
                    )

        max_ads: int = await self.storage.Session.scalar(
            select(SettingsModel.ads_per_bot).where(SettingsModel.id.is_(True))
        )
        return await self.send_or_edit(
            *(chat_id, message_id),
            text='\n'.join(
                _
                for _ in (
                    message_header(self, bot, chat_id),
                    '',
                    '**Объявлений:** '
                    + ' '.join(
                        _
                        for _ in (
                            str(ads_count),
                            '(макс)' if ads_count >= max_ads else None,
                            f'(забанено {banned_ads_count})'
                            if banned_ads_count
                            else None,
                        )
                        if _ is not None
                    ),
                    '__Добавлен:__ '
                    + bot.created_at.astimezone().strftime(
                        r'%Y-%m-%d %H:%M:%S'
                    )
                    if bot.created_at is not None
                    else None,
                    '__Обновлен:__ '
                    + bot.updated_at.astimezone().strftime(
                        r'%Y-%m-%d %H:%M:%S'
                    )
                    if bot.updated_at is not None
                    else None,
                    '\n'.join(
                        (
                            '',
                            subscription_text(bot.owner),
                            '__Дата регистрации:__ '
                            + bot.owner.created_at.strftime(
                                r'%Y-%m-%d %H:%M:%S'
                            ),
                        )
                    )
                    if chat_id != bot.owner.id
                    and bot.owner.created_at is not None
                    else None,
                    '\n__%s__'
                    % 'Внимание! Назначенный [Бот]({link}) не является '
                    'валидным. Попробуйте назначить другого бота с помощью '
                    'кнопки "Настройки аккаунта > Применить настройки" или '
                    'обратитесь к администратору за поддержкой.'.format(
                        link=f't.me/+{bot.phone_number}'
                    )
                    if bot_valid is False
                    else '\n__%s__' % 'Внимание! [Бот]({link}) не имеет '
                    'доступа к личной переписке с назначенным контактом! '
                    'Для того чтобы у бота была возможность пересылать  '
                    'полученные отклики от пользователей, получателю '
                    'необходимо написать ему в личные сообщения.'.format(
                        link=f't.me/+{bot.phone_number}'
                    )
                    if bot_valid and not bot_has_forward_peer
                    else None,
                )
                if _ is not None
            ),
            reply_markup=IKM(
                self.hpages(
                    page_index,
                    bots_count,
                    Query(
                        *(self.BOT.PAGE, bot.owner.id),
                        **(data.kwargs if data is not None else {}),
                    ),
                    kwarg='b_p',
                )
                + [
                    (
                        [IKB('Добавить объявление', _query(self.AD._SELF))]
                        if ads_count < max_ads
                        else []
                    )
                    + (
                        [
                            IKB(
                                'Просмотреть объявлениe'
                                if ads_count == 1
                                else 'Просмотреть объявления',
                                _query(self.AD.PAGE),
                            )
                        ]
                        if ads_count
                        else []
                    ),
                    [IKB('Настройки аккаунта', _query(self.SETTINGS.PAGE))],
                ]
                + (
                    [
                        [
                            IKB(
                                'Разблокировать все объявления'
                                if banned_ads_count == ads_count
                                else 'Заблокировать все объявления',
                                _query(self.BOT.BAN),
                            )
                        ]
                    ]
                    + (
                        [
                            [
                                IKB(
                                    'Повысить роль'
                                    if bot.owner.role < UserRole.SUPPORT
                                    else 'Понизить роль',
                                    _query(self.BOT.ROLE),
                                ),
                            ]
                        ]
                        if await self.storage.Session.scalar(
                            select(
                                exists(text('NULL')).where(
                                    (UserModel.id == chat_id)
                                    & (UserModel.role >= UserRole.ADMIN)
                                )
                            )
                        )
                        else []
                    )
                    if bot.owner.id != chat_id
                    else []
                )
                + (
                    [
                        [
                            IKB('Добавить бота', _query(self.BOT._SELF)),
                            IKB('Удалить бота', _query(self.BOT.DELETE)),
                        ],
                    ]
                    if bot.owner.id != chat_id
                    or bot.owner.role >= UserRole.SUPPORT
                    else []
                )
                + (
                    [
                        [
                            IKB(
                                'Запросить права для сервисного чата',
                                _query(self.BOT.AUTHORIZE),
                            )
                        ]
                    ]
                    if bot.owner.id != chat_id
                    and bot.owner.service_id is not None
                    and await self.get_channel_participants(
                        bot.owner.service_id, await self.storage.user_id()
                    )
                    is not None
                    and not isinstance(
                        await self.get_channel_participants(
                            bot.owner.service_id, chat_id
                        ),
                        (
                            type(None),
                            ChannelParticipantAdmin,
                            ChannelParticipantCreator,
                        ),
                    )
                    else []
                )
                + [
                    [
                        IKB(
                            'Назад',
                            _query(
                                self.SERVICE._SELF
                                if chat_id == bot.owner.id
                                else self.BOT.LIST
                            ),
                        )
                    ],
                ]
            ),
        )
