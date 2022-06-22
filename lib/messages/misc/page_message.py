from typing import TYPE_CHECKING, Optional, Type, Union

from pyrogram.types.bots_and_keyboards.inline_keyboard_button import (
    InlineKeyboardButton as IKB,
)
from pyrogram.types.messages_and_media.message import Message

from ...models.misc.input_model import InputModel
from ...utils.query import Query

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient


class PageMessage(object):
    async def page_message(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ):
        """Switch page to the right error."""
        if data is None or query_id is None:
            return
        elif data.command == self.PAGE.INFO:
            _text = f'Страница {data.args[-1]+1}'
        elif data.command == self.PAGE.ERROR_LEFT:
            _text = 'Листать можно только в правую сторону.'
        elif data.command == self.PAGE.ERROR_RIGHT:
            _text = 'Листать можно только в левую сторону.'
        else:
            raise NotImplementedError(
                f'Command {data.command} is not supported.'
            )
        return await self.answer_callback_query(query_id, _text)

    @classmethod
    def hpages(
        cls: Type['AdBotClient'],
        current_page: int,
        total_pages: int,
        /,
        query: Optional[Query] = None,
        kwarg: str = 'p',
        *,
        infinite_scroll: bool = True,
    ) -> list[list[IKB]]:
        """
        Scroll the pages "horizontally".

        Args:
            current_page (``int``):
                The index of the current page that is being shown.
                Must be smaller than `total_pages`.

            total_pages (``int``):
                The total count of pages that are being shown. If it is one or
                smaller, the switcher isn't returned.

            query (``Query``, *optional*):
                The command for the `~pyrogram.types.CallbackQuery`.

            infinite_scroll (``bool``, *optional*):
                If the pages should be scrolled infinitely in a loop or stopped
                at the end.

            kwarg (``str``, *optional*):
                If the new page should be provided with key-word argument.

        Returns:
            The inline keyboard buttons for switching.
        """
        if total_pages <= 1:
            return []
        elif query is None:
            query = Query(cls.PAGE.INFO)

        left_page = right_page = None
        if current_page >= 1:
            left_page = current_page - 1
        elif infinite_scroll:
            left_page = total_pages - 1

        if current_page + 1 < total_pages:
            right_page = current_page + 1
        elif infinite_scroll:
            right_page = 0

        if left_page is None:
            left = Query(cls.PAGE.ERROR_LEFT)
        elif isinstance(kwarg, str) and kwarg:
            left = query.__copy__(kwargs={**query.kwargs, kwarg: left_page})
        else:
            left = query.__copy__(args=(*query.args, left_page))

        if right_page is None:
            right = Query(cls.PAGE.ERROR_RIGHT)
        elif isinstance(kwarg, str) and kwarg:
            right = query.__copy__(kwargs={**query.kwargs, kwarg: right_page})
        else:
            right = query.__copy__(args=(*query.args, right_page))

        page_index = f'{current_page + 1} / {total_pages}'
        info = query.__copy__(command=cls.PAGE.INFO, args=(current_page,))
        return [[IKB('⬅️', left), IKB(page_index, info), IKB('➡️', right)]]
