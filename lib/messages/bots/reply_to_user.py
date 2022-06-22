"""The module with the :meth:`AdBotClient.reply_to_user`."""


from contextlib import suppress
from typing import TYPE_CHECKING, Optional, Union

from dateutil.tz.tz import tzlocal
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
        if isinstance(chat_id, InputModel):
            chat_id = chat_id.chat_id
        if chat_id == 42777 or not self.storage.phone_number:
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

        if chat_id == owner_bot.owner_id:
            if message.reply_to_message is not None and (
                not message.reply_to_message.empty
            ):
                try:
                    top_line = message.reply_to_message.text.splitlines()[0]
                    await message.copy(int(top_line.split('ID#')[-1]))
                except ValueError:
                    return await self.answer_edit_send(
                        'Пользователь для пересылки сообщения не распознан.'
                    )

        else:
            with suppress(RPCError):
                await self.forward_messages(
                    owner_bot.owner_id, chat_id, message_id
                )
            replied: bool = False
            try:
                if await self.storage.Session.scalar(
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
                ) and await self.check_chats(
                    (
                        owner_bot.owner.service_id,
                        owner_bot.owner.service_invite,
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