"""The module for processing ServiceCommands."""


from contextlib import suppress
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional, Union

from pyrogram.errors.rpc_error import RPCError
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
from ...models.misc.subscription_model import SubscriptionModel
from ...models.sessions.session_model import SessionModel
from ...utils.pyrogram import auto_init
from ...utils.query import Query

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class ServiceSubscription(object):
    async def service_subscription(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        """Provide a user subscription from `SUBSCRIPTIONS`."""

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
        if isinstance(chat_id, InputModel):
            input, chat_id = chat_id, chat_id.chat_id
            if input.message_id is not None:
                message_id = input.message_id
            if input.data is not None:
                data = input.data(self.SUBSCRIPTION.VIEW)

        def _query(
            command: str,
            period: Optional[timedelta] = None,
            /,
        ) -> Query:
            args = [user_id]
            if data is None:
                return Query(command, *args)
            if isinstance(period, timedelta):
                args.append(period.total_seconds())
            return data(command, args=args)

        user_id, period, *_ = *(() if data is None else data.args), None, None
        if not isinstance(user_id, int):
            user_id = chat_id
        user = await self.storage.Session.get(UserModel, user_id)
        if user is None:
            self.storage.Session.add(user := UserModel(id=user_id))
            await self.storage.Session.commit()
        if user.is_subscribed:
            return await self.start_message(
                chat_id, _message_id, data, query_id
            )

        subscription: Optional[SubscriptionModel] = None
        if isinstance(period, (int, float)):
            subscription = await self.storage.Session.get(
                SubscriptionModel, timedelta(seconds=period)
            )
            if subscription is None:
                if user.subscription_message_id is not None:
                    user.subscription_message_id = None
                    await self.storage.Session.commit()
                return await abort('Такой длительности не существует.')

        if data is None or data.command == self.SUBSCRIPTION._SELF:
            subscription_msg = (
                user.service_id,
                user.subscription_message_id,
            )
            if all(_ is not None for _ in subscription_msg):
                subscription_message = await self.get_messages(
                    *subscription_msg
                )
                if not subscription_message.empty:
                    return await abort(
                        'Заявка уже была отправлена администратору.'
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

            apply_message = await self.service_subscription(
                user.service_id,
                data=_query(self.SUBSCRIPTION.VIEW),
                query_id=query_id,
            )
            user.subscription_message_id = apply_message.id
            await self.storage.Session.commit()
            return (
                apply_message,
                await abort(
                    'Заявка была успешно выслана заново.'
                    if subscription_msg[-1] is not None
                    else 'Заявка была успешно отправлена администратору.'
                ),
            )

        elif data.command == self.SUBSCRIPTION.VIEW:
            return await self.send_or_edit(
                *(chat_id, message_id),
                f'[Пользователь](tg://user?id={user.id}) оставил заявку на '
                'регистрацию.',
                reply_markup=IKM(
                    [
                        [
                            IKB(
                                'Выбрать длительность',
                                _query(self.SUBSCRIPTION.PICK),
                            )
                        ],
                        [IKB('Отклонить', _query(self.SUBSCRIPTION.DENY))],
                    ]
                ),
            )

        elif data.command == self.SUBSCRIPTION.DENY:
            self.storage.Session.add(
                InputModel(
                    chat_id=chat_id,
                    message_id=message_id,
                    data=data,
                    on_finished=self._service_subscription_deny,
                )
            )
            await self.storage.Session.commit()
            return await self.send_or_edit(
                *(chat_id, message_id),
                'Напишите причину отклонения заявки в ответ на это сообщение.',
                reply_markup=IKM(
                    [
                        [
                            IKB(
                                'Отклонить без причины',
                                self.INPUT._SELF,
                            )
                        ],
                        [IKB('Отмена', self.INPUT.CANCEL)],
                    ]
                ),
            )

        elif data.command == self.SUBSCRIPTION.APPLY:
            if subscription is None:
                return await abort('Вы не выбрали длительность подписки.')

            user.subscription_from = datetime.now()
            user.subscription = subscription
            user.subscription_message_id = None
            await self.storage.Session.commit()

            return (
                await self.send_or_edit(
                    *(chat_id, message_id),
                    f'Заявка [пользователя](tg://user?id={user_id}) на период '
                    f'"**{subscription.name}**" была успешно подтверждена.',
                ),
                await self.answer_edit_send(
                    chat_id=user.id,
                    text='Ваша заявка была подтверждена администратором.'
                    '\nНапишите /start, чтобы увидеть список доступных '
                    'функций.',
                ),
            )

        else:
            return await self.send_or_edit(
                *(chat_id, message_id),
                text='\n'.join(
                    (
                        f'[Пользователь](tg://user?id={user_id}) оставил '
                        'заявку '
                        'на регистрацию.',
                        '',
                        'Выберите длительность подписки: **{}**'.format(
                            subscription.name
                            if subscription is not None
                            else 'Отсутствует'
                        ),
                    )
                ),
                reply_markup=IKM(
                    (
                        [
                            [
                                IKB(
                                    'Подтвердить',
                                    _query(
                                        self.SUBSCRIPTION.APPLY,
                                        subscription.period,
                                    ),
                                )
                            ]
                        ]
                        if subscription is not None
                        else [
                            [
                                IKB(
                                    name,
                                    _query(self.SUBSCRIPTION.PICK, period),
                                )
                            ]
                            async for period, name in (
                                await self.storage.Session.stream_scalars(
                                    select(SubscriptionModel)
                                )
                            )
                        ]
                    )
                    + [
                        [
                            IKB('Отклонить', _query(self.SUBSCRIPTION.DENY))
                            if data.command == self.SUBSCRIPTION.VIEW
                            else IKB(
                                'Назад',
                                _query(
                                    self.SUBSCRIPTION.VIEW
                                    if subscription is None
                                    else data.command
                                ),
                            )
                        ]
                    ]
                ),
            )

    async def _service_subscription_deny(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        """
        Deny the user subscription with or without the actual reason.

        `InputModel` must have a user argument provided!
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

        if not isinstance(chat_id, InputModel):
            return await abort(
                'Написать причину отклонения заявки можно только через '
                'сообщение.'
            )
        input, chat_id = chat_id, chat_id.chat_id
        if isinstance(_message_id := message_id, Message):
            message_id = message_id.id
        if not input.success:
            return await self.service_subscription(
                input, _message_id, data, query_id
            )

        user = await self.storage.Session.get(UserModel, input.data.args)
        if user is not None:
            user.subscription_message_id = None
            await self.storage.Session.commit()

        if data is None and isinstance(message_id, int):
            message_id = await self.get_messages(chat_id, message_id)
        return (
            await self.send_or_edit(
                *(input.chat_id, input.message_id),
                '\n\n'.join(
                    _
                    for _ in (
                        f'Заявка [пользователя](tg://user?id={user.id}) была '
                        'отклонена.',
                        '\n'.join(
                            ('__Отклонено по причине:__', message_id.text)
                        )
                        if isinstance(message_id, Message) and message_id.text
                        else '__Отклонено без указания причины.__',
                    )
                    if _ is not None
                ),
            ),
            await self.answer_edit_send(
                chat_id=user.id,
                text='\n\n'.join(
                    _
                    for _ in (
                        'Ваша заявка была отклонена администратором.',
                        '\n'.join(
                            ('__Отклонено по причине:__', message_id.text)
                        )
                        if isinstance(message_id, Message) and message_id.text
                        else None,
                    )
                    if _ is not None
                ),
            ),
        )
