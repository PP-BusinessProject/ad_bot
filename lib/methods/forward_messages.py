"""The module with the :meth:`AdBotClient.forward_messages`."""

from typing import Iterable, Optional, Union

from pyrogram.raw.base.input_channel import InputChannel
from pyrogram.raw.base.input_peer import InputPeer
from pyrogram.raw.base.input_user import InputUser
from pyrogram.raw.functions.messages.forward_messages import (
    ForwardMessages as RawForwardMessages,
)
from pyrogram.raw.types.update_new_channel_message import (
    UpdateNewChannelMessage as UNCM,
)
from pyrogram.raw.types.update_new_message import UpdateNewMessage as UNM
from pyrogram.raw.types.update_new_scheduled_message import (
    UpdateNewScheduledMessage as UNSM,
)
from pyrogram.types import Message
from pyrogram.types.list import List

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ad_bot_client import AdBotClient


class ForwardMessages(object):
    async def forward_messages(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, str, InputPeer, InputUser, InputChannel],
        from_chat_id: Union[int, str, InputPeer, InputUser, InputChannel],
        message_ids: Union[int, Iterable[int]],
        *,
        disable_notification: Optional[bool] = None,
        background: Optional[bool] = None,
        with_my_score: Optional[bool] = None,
        drop_author: Optional[bool] = None,
        drop_media_captions: Optional[bool] = None,
        protect_content: Optional[bool] = None,
        schedule_date: Optional[int] = None,
    ) -> Union[Message, List[Message]]:
        """
        Forward messages of any kind.

        Args:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use
                "me" or "self".
                For a contact that exists in your Telegram address book you
                can use his phone number (str).

            from_chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the source chat
                where the original message was sent.
                For your personal cloud (Saved Messages) you can simply use
                "me" or "self".
                For a contact that exists in your Telegram address book you
                can use his phone number (str).

            message_ids (``int`` | List of ``int``):
                A list of Message identifiers in the chat specified in
                *from_chat_id* or a single message id.
                Iterators and Generators are also accepted.

            disable_notification (``Optional[bool]``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            background (``Optional[bool]``, *optional*):
                Whether to send the message in background.

            with_my_score (``Optional[bool]``, *optional*):
                When forwarding games, whether to include your score in the
                game.

            drop_author	(``Optional[bool]``, *optional*):
                Whether to forward messages without quoting the original
                author.

            drop_media_captions	(``Optional[bool]``, *optional*):
                Whether to strip captions from media.

            protect_content (``Optional[bool]``, *optional*):
                Protects the contents of the sent message from forwarding and
                saving.

            schedule_date (``Optional[int]``, *optional*):
                Date when the message will be automatically sent. Unix time.

        Returns:
            :obj:`~pyrogram.types.Message` | List of
            :obj:`~pyrogram.types.Message`: In case *message_ids* was an
            integer, the single forwarded message is returned, otherwise, in
            case *message_ids* was an iterable, the returned value will be a
            list of messages, even if such iterable contained just a single
            element.

        Example:
            .. code-block:: python

                # Forward a single message
                app.forward_messages("me", "pyrogram", 20)

                # Forward multiple messages at once
                app.forward_messages("me", "pyrogram", [3, 20, 27])
        """
        is_iterable = not isinstance(message_ids, int)
        message_ids = list(message_ids) if is_iterable else [message_ids]

        response = await self.send(
            RawForwardMessages(
                to_peer=await self.resolve_peer(chat_id),
                from_peer=await self.resolve_peer(from_chat_id),
                id=message_ids,
                silent=disable_notification,
                background=background,
                with_my_score=with_my_score,
                drop_author=drop_author,
                drop_media_captions=drop_media_captions,
                random_id=[self.rnd_id() for _ in message_ids],
                schedule_date=schedule_date,
                noforwards=protect_content,
            )
        )

        user_ids = {i.id: i for i in response.users}
        chat_ids = {i.id: i for i in response.chats}
        forwarded_messages = List(
            [
                await Message._parse(self, i.message, user_ids, chat_ids)
                for i in response.updates
                if isinstance(i, (UNM, UNCM, UNSM))
            ]
        )

        return forwarded_messages if is_iterable else forwarded_messages[0]
