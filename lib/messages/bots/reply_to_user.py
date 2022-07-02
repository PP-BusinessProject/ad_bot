"""The module with the :meth:`AdBotClient.reply_to_user`."""


from contextlib import suppress
from typing import TYPE_CHECKING, Optional, Union

from dateutil.tz.tz import tzlocal
from pyrogram.enums.chat_type import ChatType
from pyrogram.errors.rpc_error import RPCError
from pyrogram.types.messages_and_media.message import Message
from sqlalchemy.sql.expression import or_, select
from sqlalchemy.sql.functions import count

from ...models.bots.reply_model import ReplyModel
from ...models.clients.bot_model import BotModel
from ...models.misc.input_model import InputModel
from ...models.misc.settings_model import SettingsModel
from ...utils.query import Query

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class ReplyToUser(object):
    async def reply_to_user(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> None:
        """Reply to user to navigate to the end client."""

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
        if chat_id == 42777 or not self.storage.is_nested:
            return

        owner_bot: Optional[BotModel] = await self.storage.Session.scalar(
            select(BotModel)
            .filter_by(phone_number=self.storage.phone_number)
            .limit(1),
        )
        if owner_bot is None:
            return

        if isinstance(message := message_id, Message):
            message_id = message_id.id
        if not isinstance(message, Message):
            message = await self.get_messages(chat_id, message_id)

        if chat_id == owner_bot.forward_to_id:
            if message.reply_to_message is None:
                return await abort(
                    'Пользователь для пересылки сообщения не распознан.'
                )
            elif message.reply_to_message.forward_from is None:
                async for dialog in self.iter_dialogs(
                    exclude_pinned=True, folder_id=0
                ):
                    if dialog.chat.type == ChatType.PRIVATE and (
                        ' '.join(
                            _
                            for _ in (
                                dialog.chat.first_name,
                                dialog.chat.last_name,
                            )
                            if _
                        )
                        == message.reply_to_message.forward_sender_name
                    ):
                        forward_id = dialog.chat.id
                        break
                else:
                    return await abort('У пользователя скрыт аккаунт.')
            else:
                forward_id = message.reply_to_message.forward_from.id

            try:
                await self.forward_messages(
                    *(forward_id, chat_id, message_id),
                    drop_author=True,
                )
            except RPCError as _:
                return await abort(
                    'Произошла ошибка при пересылке сообщения '
                    f'[пользователю](tg://user?id={forward_id})).',
                )

        else:
            with suppress(RPCError):
                await self.forward_messages(
                    owner_bot.forward_to_id, chat_id, message_id
                )
            replied: bool = False
            try:
                if owner_bot.reply_message_id is not None and (
                    await self.storage.Session.scalar(
                        select(
                            or_(
                                SettingsModel.replies_per_chat == 0,
                                select(count())
                                .filter(
                                    ReplyModel.client_phone_number
                                    == owner_bot.phone_number,
                                    ReplyModel.chat_id == chat_id,
                                    ReplyModel.replied,
                                )
                                .scalar_subquery()
                                < SettingsModel.replies_per_chat,
                            )
                        ).where(SettingsModel.id.is_(True))
                    )
                    and await self.check_chats(
                        (
                            owner_bot.owner.service_id,
                            owner_bot.owner.service_invite,
                        ),
                        folder_id=1,
                    )
                ):
                    await self.forward_messages(
                        *(
                            chat_id,
                            owner_bot.owner.service_id,
                            owner_bot.reply_message_id,
                        ),
                        drop_author=True,
                    )
                    replied = True
            finally:
                self.storage.Session.add(
                    ReplyModel(
                        client_phone_number=owner_bot.phone_number,
                        chat_id=chat_id,
                        message_id=message_id,
                        first_name=message.from_user.first_name,
                        last_name=message.from_user.last_name,
                        username=message.from_user.username,
                        phone_number=message.from_user.phone_number,
                        timestamp=message.date.replace(tzinfo=tzlocal()),
                        replied=replied,
                    )
                )
                await self.storage.Session.commit()
