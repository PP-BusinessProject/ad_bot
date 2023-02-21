"""The module for processing StartCommands."""


from datetime import timedelta
from typing import TYPE_CHECKING, Any, Optional, Union

from pyrogram.types import InlineKeyboardButton as IKB
from pyrogram.types import InlineKeyboardMarkup as IKM
from pyrogram.types import Message
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.state import InstanceState

from ...models.clients.user_model import UserModel, UserRole
from ...models.misc.input_model import InputModel
from ...utils.query import Query
from .utils import subscription_text

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class StartMessage(object):
    async def start_message(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> Message:
        """
        Greet the user and provide initial functionality.

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
            The sent message with start functions.
        """
        if isinstance(chat_id, InputModel):
            input, chat_id = chat_id, chat_id.chat_id
            if message_id is None:
                message_id = input.message_id
        else:
            input = await self.storage.Session.get(InputModel, chat_id)
            if input is not None:
                await self.input_message(
                    *(input, message_id),
                    data=Query(self.INPUT.CANCEL),
                    query_id=query_id,
                )
        if isinstance(message_id, Message):
            message_id = message_id.id

        user: UserModel
        user_first = user = await self.storage.Session.get(UserModel, chat_id)
        if user is None:
            self.storage.Session.add(user := UserModel(id=chat_id))
            await self.storage.Session.commit()
            self.logger.info(f'Registered user with id {user.id}')
        return await self.send_or_edit(
            *(chat_id, message_id),
            text='\n'.join(
                _
                for _ in (
                    'Вы успешно зарегистрировались в Advertisment Bot!'
                    if user_first is None
                    else 'Приветствуем в Advertisment Bot!',
                    '',
                    f'**Ваша роль:** {user.role.translation.capitalize()}'
                    if user.is_subscribed
                    else None,
                    subscription_text(user),
                    None
                    if user.is_subscribed
                    else 'Для того чтобы оставить заявку воспользуйтесь меню '
                    'ниже.',
                    '__Дата регистрации:__ '
                    + user.created_at.astimezone().strftime(
                        r'%Y-%m-%d %H:%M:%S'
                    )
                    if user_first is not None
                    else None,
                )
                if _ is not None
            ),
            reply_markup=IKM(
                [
                    [IKB('Мои боты', self.BOT.PAGE)],
                    [IKB('Текущие пользователи', self.BOT.LIST)],
                    [
                        IKB('Добавить бота', self.SENDER_CLIENT._SELF),
                        IKB('Список ботов', self.SENDER_CLIENT.LIST),
                    ],
                    [
                        IKB('Добавить чаты', self.SENDER_CHAT._SELF),
                        IKB('Список чатов', self.SENDER_CHAT.LIST),
                    ],
                ]
                if user.role in {UserRole.SUPPORT, UserRole.ADMIN}
                else [
                    [IKB('Мои боты', self.BOT.PAGE)],
                    [IKB('Связаться с администрацией', self.HELP._SELF)],
                ]
                if user.is_subscribed
                else [
                    [IKB('Оставить заявку', self.SUBSCRIPTION._SELF)],
                    [IKB('Связаться с администрацией', self.HELP._SELF)],
                ]
            ),
        )

    def user_create_listeners(
        self: 'AdBotClient',
        notify_subscription_end: timedelta,
        /,
    ) -> None:
        """Bind :class:`UserModel` events with `client` handler."""

        def _after_insert(_: Any, __: Any, user: UserModel, /) -> None:
            self.notify_subscription_end_job_init(
                user, notify_subscription_end
            )

        def _after_delete(_: Any, __: Any, user: UserModel, /) -> None:
            user.subscription_from = user.subscription_period = None
            self.notify_subscription_end_job_init(
                user, notify_subscription_end
            )

            chats = self.__class__.Registry.get(self.storage.phone_number, {})
            for tasks in chats.get(user.id, {}).values():
                for task in tasks:
                    task.cancel()

        def _after_update(_: Any, __: Any, user: UserModel, /) -> None:
            state: InstanceState = inspect(user)
            if not state.modified:
                return

            prev_user = UserModel.from_previous_state(state)
            self.notify_subscription_end_job_init(
                user, notify_subscription_end
            )

            sup_roles = {UserRole.SUPPORT, UserRole.ADMIN}
            if user.role not in sup_roles and prev_user.role in sup_roles:
                handlers_whitelist = {
                    handler.callback_name
                    for group in self.groups.values()
                    for handler in group
                    if handler.check_user is None
                    or handler.check_user not in sup_roles
                }
            else:
                return

            chats = self.__class__.Registry.get(self.storage.phone_number, {})
            for handler_name, tasks in chats.get(user.id, {}).items():
                if handler_name not in handlers_whitelist:
                    for task in tasks:
                        task.cancel()

        if UserModel not in self.listeners:
            self.listeners[UserModel] = {}
        if 'after_insert' not in self.listeners[UserModel]:
            self.listeners[UserModel]['after_insert'] = [_after_insert]
        if 'after_delete' not in self.listeners[UserModel]:
            self.listeners[UserModel]['after_delete'] = [_after_delete]
        if 'after_update' not in self.listeners[UserModel]:
            self.listeners[UserModel]['after_update'] = [_after_update]
