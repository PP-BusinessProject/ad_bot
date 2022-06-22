"""The module with helper functions for awaiting user input."""

from __future__ import annotations

from asyncio import current_task
from typing import TYPE_CHECKING, Any, Optional, TypeVar, Union

from pyrogram.types.messages_and_media.message import Message
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.state import InstanceState
from sqlalchemy.sql.expression import select

from ...ad_bot_handler import AdBotHandler
from ...models import InputMessageModel, InputModel, UserRole
from ...utils.query import Query

if TYPE_CHECKING:
    from ...ad_bot_client import AdBotClient
#
T = TypeVar('T')


class InputMessage(object):
    async def input_message(
        self: 'AdBotClient',
        /,
        chat_id: Union[int, InputModel[T]],
        message_id: Optional[Union[int, Message]] = None,
        data: Optional[Query] = None,
        query_id: Optional[int] = None,
    ) -> Optional[T]:
        """
        Handle the :class:`InputModel` for update.

        Handle for both the :class:`CallbackQuery` and :class:`Message`.

        Gets the :meth:`chat.id` from update and it's :class:`InputModel`.

        If the `update` is of type :class:`Message`, calls
        :meth:`InputModel.on_response` if any exists. If result is True,
        finishes.

        If the `update` is of type :class:`CallbackQuery`, checks if the
        :meth:`Query.command` is one of the successful in the
        :class:`INPUT` and then finishes anyway.

        When the :class:`InputModel` finishes:
        1. Calls :meth:`InputModel.on_finished` if any exists.
        2. If :meth:`InputModel.clear_used_messages` is True, `client`
        deletes all of the messages in :meth:`InputModel.used_messages`.
        3. Deletes the :class:`InputModel` from the database.
        4. Removes the :meth:`InputModel.handler` from the `client`.

        Args:
            chat_id (``Union[int, InputModel]``):
                The id of a chat to await this input from or the input itself.

            message_id (``Optional[Union[int, Message]]``, *optional*):
                The id of the message that was used to request the input .

            data (``Optional[Query]``, *optional*):
                The data used for creating the input.

            query_id (``Optional[int]``, *optional*):
                The id of a :class:`CallbackQuery` that has requested this
                input.

        Returns:
            The result of :meth:`InputModel.on_finished` if input has
            finished successfully.
        """
        if isinstance(_message_id := message_id, Message):
            message_id = message_id.id
        if not isinstance(chat_id, InputModel):
            input = await self.storage.Session.get(InputModel, chat_id)
            if input is None:
                if (data is not None and message_id is not None) and (
                    data.command == self.INPUT.CANCEL
                ):
                    await self.delete_messages(chat_id, message_id)
                return None
        else:
            input, chat_id = chat_id, chat_id.chat_id
            if inspect(input).deleted:
                return

        if data is None and input.do_add_message:
            used_message = InputMessageModel(
                message_id=message_id, input=input
            )
            self.storage.Session.add(used_message)
            await self.storage.Session.commit()

        on_response = input.on_response
        if isinstance(getattr(on_response, '__self__', None), self.__class__):
            on_response = on_response.__func__

        if data is not None and (
            data.command in self.INPUT._member_map_.values()
        ):
            input.success = data.command == self.INPUT._SELF
        elif on_response is None or await on_response(
            *(self, input),
            message_id=_message_id,
            data=data,
            query_id=query_id,
        ):
            input.success = True
        else:
            return None

        if on_response is not None:
            check_response = self.input_message
            cb_name = check_response.__module__, check_response.__qualname__
            chats = self.__class__.Registry.get(self.storage.phone_number, {})
            tasks = chats.get(chat_id, {}).get(':'.join(cb_name), [])
            scope_task = current_task()
            for task in tasks:
                if task != scope_task:
                    task.cancel()

        on_finished = input.on_finished
        if isinstance(getattr(on_finished, '__self__', None), self.__class__):
            on_finished = on_finished.__func__
        try:
            try:
                if on_finished is not None:
                    return await on_finished(
                        *(self, input),
                        message_id=_message_id,
                        data=data,
                        query_id=query_id,
                    )
            finally:
                if input.clear_used_messages:
                    used_msg_ids = await self.storage.Session.scalars(
                        select(InputMessageModel.message_id).filter_by(
                            chat_id=input.chat_id
                        )
                    )
                    if used_msg_ids := used_msg_ids.all():
                        await self.delete_messages(input.chat_id, used_msg_ids)
        finally:
            await self.storage.Session.delete(input)
            await self.storage.Session.commit()

    def input_create_listeners(self: 'AdBotClient', /) -> None:
        """Bind :class:`InputModel` events with `client` handler."""

        def _after_insert(_: Any, __: Any, input: InputModel, /) -> None:
            self.add_input_handler(
                input.chat_id,
                input.group,
                query_pattern=input.query_pattern,
                user_role=input.user_role,
                calls_count=input.calls_count,
                action=input.action,
                replace_calls=input.replace_calls,
            )

        def _after_delete(_: Any, __: Any, input: InputModel, /) -> None:
            self.remove_input_handler(input.chat_id, input.group)

        def _after_update(_: Any, __: Any, input: InputModel, /) -> None:
            state: InstanceState = inspect(input)
            if not state.modified:
                return

            prev_input = InputModel.from_previous_state(state)
            self.remove_input_handler(
                prev_input.chat_id,
                prev_input.group,
            )
            if input.success is None:
                self.add_input_handler(
                    input.chat_id,
                    input.group,
                    query_pattern=input.query_pattern,
                    user_role=input.user_role,
                    calls_count=input.calls_count,
                    action=input.action,
                    replace_calls=input.replace_calls,
                )

        if InputModel not in self.listeners:
            self.listeners[InputModel] = {}
        if 'after_insert' not in self.listeners[InputModel]:
            self.listeners[InputModel]['after_insert'] = [_after_insert]
        if 'after_delete' not in self.listeners[InputModel]:
            self.listeners[InputModel]['after_delete'] = [_after_delete]
        if 'after_update' not in self.listeners[InputModel]:
            self.listeners[InputModel]['after_update'] = [_after_update]

    def add_input_handler(
        self: 'AdBotClient',
        /,
        chat_id: int,
        group: int = 0,
        query_pattern: Optional[str] = None,
        user_role: Optional[UserRole] = None,
        calls_count: Optional[int] = None,
        action: Optional[str] = None,
        *,
        replace_calls: bool = False,
    ) -> None:
        """Add the :class:`InputModel` handler if it does not exist yet."""
        message_handler: bool = False
        query_handler: bool = query_pattern is None
        for handler in self.groups.get(group, ()):
            if not isinstance(handler, AdBotHandler) or not (
                handler.callback == self.input_message
                and handler.chat_id == chat_id
            ):
                continue
            elif not message_handler and handler.is_query is False:
                message_handler = True
            elif not query_handler and handler.is_query is True:
                query_handler = True
            if message_handler and query_handler:
                return

        if group not in self.groups:
            self.groups[group] = []
        if not message_handler:
            self.groups[group].insert(
                min(len(self.groups[group]), 1),
                AdBotHandler(
                    self.input_message,
                    r'^((?!\/start).)*$',
                    chat_id=chat_id,
                    check_user=user_role,
                    calls_count=calls_count,
                    action=action,
                    replace=replace_calls,
                    is_query=False,
                ),
            )
        if not query_handler and query_pattern is not None:
            self.groups[group].insert(
                min(len(self.groups[group]), 1),
                AdBotHandler(
                    self.input_message,
                    query_pattern,
                    chat_id=chat_id,
                    check_user=user_role,
                    calls_count=calls_count,
                    action=action,
                    replace=replace_calls,
                    is_query=True,
                ),
            )

    def remove_input_handler(
        self: 'AdBotClient',
        /,
        chat_id: int,
        group: int = 0,
    ) -> None:
        """Remove the :class:`InputModel` handler if any exists."""
        for handler in self.groups.get(group, ()):
            if isinstance(handler, AdBotHandler) and (
                handler.callback == self.input_message
                and handler.chat_id == chat_id
            ):
                self.groups[group].remove(handler)
