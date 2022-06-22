from typing import TYPE_CHECKING, Dict, Optional, Union

from pyrogram.types.bots_and_keyboards.inline_keyboard_button import (
    InlineKeyboardButton as IKB,
)
from pyrogram.types.bots_and_keyboards.inline_keyboard_markup import (
    InlineKeyboardMarkup as IKM,
)
from pyrogram.types.messages_and_media.message import Message
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import select

from ...models.misc.category_model import CategoryModel
from ...models.misc.input_model import InputModel
from ...utils.query import Query

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class CategoryMessage(object):
    async def category_message(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
        *,
        prefix_text: str = '',
        cancel_command: str = '',
        kwarg: str = 's',
    ):
        """
        Select category from the list of `categories`.

        Args:
            query (``Query``):
                The query that initiates selection.

            categories (``dict[str, Any]``):
                The recursive dictionary of dictionaries that represents a
                category tree.

            cancel_command (``str``, *optional*):
                The command to return from the selection.

            text (``str``, *optional*):
                The text of the selector message.

            kwarg (``str``, *optional*):
                The key-word argument that will be used to store values of this
                selection.

            kwarg_sep (``str``, *optional*):
                The separator for the `kwarg` arguments.

        Returns:
            If the category has not been selected yet, returns the text and
            reply markup of the next category message. Otherwise, returns the
            selected category.
        """
        if isinstance(chat_id, InputModel):
            input, chat_id = chat_id, chat_id.chat_id
            if input.message_id is not None:
                message_id = input.message_id
        if isinstance(message_id, Message):
            message_id = message_id.id

        def _query(id: int, /) -> Query:
            return data.__copy__(kwargs=data.kwargs | {kwarg: id})

        async def abort(text: str, /) -> Optional[Message]:
            return await self.answer_edit_send(query_id, chat_id, text=text)

        category: Optional[CategoryModel] = None
        category_id: int = 0
        if data is not None and data.kwargs.get(kwarg) is not None:
            category_id = int(data.kwargs.get(kwarg))
        if category_id != 0:
            category = await self.storage.Session.scalar(
                select(CategoryModel)
                .where(CategoryModel.id == abs(category_id))
                .options(joinedload(CategoryModel.children))
            )
            if category is None:
                return await abort(
                    f'Категория с Id#{abs(category_id)} не существует.'
                )
            categories = category.children
        else:
            categories = await self.storage.Session.scalars(
                select(CategoryModel)
            )
            if not (categories := categories.all()):
                return await abort(
                    'На данный момент нет категорий для выбора.'
                )

        if category_id < 0:
            return category
        elif category_id > 0 and not categories:
            reply_markup = [[IKB('Подтвердить выбор', _query(-category.id))]]
        else:
            reply_markup = [
                [IKB(category.name, _query(category.id))]
                for category in categories
            ]
        if data is not None:
            back = IKB(
                f'Назад в "{category.name}"'
                if category is not None
                else 'Назад',
                _query(category.id)
                if category is not None
                else data.__copy__(
                    cancel_command,
                    kwargs={
                        k: v for k, v in data.kwargs.items() if k != kwarg
                    },
                ),
            )
            reply_markup.append([back])

        category_parents = []
        if (_category := category) is None:
            category_parents.append('Отсутствует')
        else:
            category_parents.append(_category.name)
            while _category.parent is not None:
                category_parents.append((_category := _category.parent).name)

        return await self.send_or_edit(
            *(chat_id, message_id),
            text='\n\n'.join(
                _
                for _ in (
                    prefix_text,
                    f"Текущая категория: **{' > '.join(category_parents)}**",
                )
                if _
            ),
            reply_markup=IKM(reply_markup),
        )