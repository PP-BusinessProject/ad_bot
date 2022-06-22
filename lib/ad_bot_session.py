from asyncio import Event, Task, TimeoutError, sleep, wait_for
from contextlib import suppress
from ctypes import Union
from datetime import datetime
from hashlib import sha1
from io import BytesIO
from os import urandom
from traceback import print_exc
from typing import TYPE_CHECKING, Final, Optional

from apscheduler.job import Job
from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.interval import IntervalTrigger
from pyrogram import crypto_executor
from pyrogram.client import Client
from pyrogram.crypto.mtproto import pack, unpack
from pyrogram.errors import AuthKeyDuplicated
from pyrogram.errors import BadMsgNotification as BadMsgNotificationError
from pyrogram.errors import (
    FloodWait,
    InternalServerError,
    RPCError,
    SecurityCheckMismatch,
    ServiceUnavailable,
)
from pyrogram.raw.all import layer
from pyrogram.raw.core import FutureSalts, Int, MsgContainer, TLObject
from pyrogram.raw.functions.help.get_config import GetConfig
from pyrogram.raw.functions.init_connection import InitConnection
from pyrogram.raw.functions.invoke_with_layer import InvokeWithLayer
from pyrogram.raw.functions.invoke_with_takeout import InvokeWithTakeout
from pyrogram.raw.functions.invoke_without_updates import InvokeWithoutUpdates
from pyrogram.raw.functions.ping import Ping
from pyrogram.raw.functions.ping_delay_disconnect import PingDelayDisconnect
from pyrogram.raw.functions.updates.get_difference import GetDifference
from pyrogram.raw.types.bad_msg_notification import BadMsgNotification
from pyrogram.raw.types.bad_server_salt import BadServerSalt
from pyrogram.raw.types.channel import Channel
from pyrogram.raw.types.chat import Chat
from pyrogram.raw.types.msg_detailed_info import MsgDetailedInfo
from pyrogram.raw.types.msg_new_detailed_info import MsgNewDetailedInfo
from pyrogram.raw.types.msgs_ack import MsgsAck
from pyrogram.raw.types.new_session_created import NewSessionCreated
from pyrogram.raw.types.peer_user import PeerUser
from pyrogram.raw.types.pong import Pong
from pyrogram.raw.types.rpc_error import RpcError
from pyrogram.raw.types.rpc_result import RpcResult
from pyrogram.raw.types.update_bot_callback_query import UpdateBotCallbackQuery
from pyrogram.raw.types.update_delete_channel_messages import (
    UpdateDeleteChannelMessages,
)
from pyrogram.raw.types.update_delete_messages import UpdateDeleteMessages
from pyrogram.raw.types.update_edit_channel_message import (
    UpdateEditChannelMessage,
)
from pyrogram.raw.types.update_edit_message import UpdateEditMessage
from pyrogram.raw.types.update_inline_bot_callback_query import (
    UpdateInlineBotCallbackQuery,
)
from pyrogram.raw.types.update_new_channel_message import (
    UpdateNewChannelMessage,
)
from pyrogram.raw.types.update_new_message import UpdateNewMessage
from pyrogram.raw.types.update_new_scheduled_message import (
    UpdateNewScheduledMessage,
)
from pyrogram.raw.types.update_short import UpdateShort
from pyrogram.raw.types.update_short_chat_message import UpdateShortChatMessage
from pyrogram.raw.types.update_short_message import UpdateShortMessage
from pyrogram.raw.types.updates_combined import UpdatesCombined
from pyrogram.raw.types.updates_t import Updates
from pyrogram.raw.types.user import User
from pyrogram.session.internals import MsgFactory, MsgId
from pyrogram.session.session import Session, log
from pyrogram.types.messages_and_media.message import Message
from pyrogram.utils import get_peer_id
from typing_extensions import Self

from .ad_bot_auth import AdBotAuth
from .ad_bot_connection import AdBotConnection
from .ad_bot_handler import AdBotHandler
from .utils.query import Query

if TYPE_CHECKING:
    from .ad_bot_client import AdBotClient


class Result(object):
    def __init__(self: Self, /) -> None:
        self.value = None
        self.event = Event()


class AdBotSession(Session):

    START_TIMEOUT: Final[int] = 1
    WAIT_TIMEOUT: Final[int] = 15
    SLEEP_THRESHOLD: Final[int] = 10
    MAX_RETRIES: Final[int] = 5
    ACKS_THRESHOLD: Final[int] = 8
    PING_INTERVAL: Final[int] = 5

    client: Final['AdBotClient']
    connection: Optional[AdBotConnection] = None
    ping_job: Optional[Job] = None

    def __init__(
        self,
        client: Client,
        dc_id: int,
        test_mode: bool,
        auth_key: str,
        is_media: bool = False,
        is_cdn: bool = False,
    ) -> None:
        self.client = client
        self.is_media = is_media
        self.is_cdn = is_cdn
        self.dc_id = dc_id
        self.test_mode = test_mode
        self.auth_key = auth_key

        self.connection = None
        self.session_id = urandom(8)
        self.msg_factory = MsgFactory()
        self.salt = 0
        self.pending_acks = set()
        self.results = {}
        self.stored_msg_ids = []
        self.ping_job = None
        self.network_task = None
        self.auth_key_id = None
        self.is_connected = Event()

    async def start(self: Self, /) -> None:
        self.connection = AdBotConnection(
            self.dc_id,
            self.test_mode,
            self.client.ipv6,
            self.client.proxy,
            self.is_media,
            # mode=0,
        )

        while True:
            try:
                await self.connection.connect()
                if self.auth_key is None or self.auth_key_id is None:
                    self.auth_key = await self.client.storage.auth_key()
                    if self.auth_key is None:
                        self.auth_key = await AdBotAuth(
                            self.connection
                        ).create()
                        await self.client.storage.auth_key(self.auth_key)
                    self.auth_key_id = sha1(
                        self.auth_key, usedforsecurity=False
                    ).digest()[-8:]
                self.network_task = self.client.loop.create_task(
                    self.network_worker()
                )
                await self._send(Ping(ping_id=0), self.START_TIMEOUT)

                if not self.is_cdn:
                    await self._send(
                        InvokeWithLayer(
                            layer=layer,
                            query=InitConnection(
                                api_id=self.client.api_id,
                                app_version=self.client.app_version,
                                device_model=self.client.device_model,
                                system_version=self.client.system_version,
                                system_lang_code=self.client.lang_code,
                                lang_code=self.client.lang_code,
                                lang_pack='',
                                query=GetConfig(),
                            ),
                        ),
                        self.START_TIMEOUT,
                    )

                self.ping_job = self.client.scheduler.add_job(
                    self.ping_worker.__func__,
                    IntervalTrigger(seconds=self.PING_INTERVAL),
                    args=(self,),
                    id=f'ping_job:{self.client.storage.phone_number}',
                    max_instances=1,
                    replace_existing=True,
                    next_run_time=datetime.now(),
                )

                log.info(f'Session initialized: Layer {layer}')
                log.info(
                    f'Device: {self.client.device_model} - '
                    f'{self.client.app_version}'
                )
                log.info(
                    f'System: {self.client.system_version} '
                    f'({self.client.lang_code.upper()})'
                )

            except (OSError, TimeoutError, RPCError):
                await self.stop()
            except (AuthKeyDuplicated, BaseException):
                await self.stop()
                raise
            else:
                break

        self.is_connected.set()

    async def stop(self: Self, /) -> None:
        chats = self.client.Registry.get(self.client.storage.phone_number, {})
        for chat in chats.values():
            for tasks in chat.values():
                for task in tasks:
                    task.cancel()

        self.is_connected.clear()
        if self.ping_job is not None:
            with suppress(JobLookupError):
                self.ping_job.remove()

        self.connection.close()
        if self.network_task is not None:
            await self.network_task

        for i in self.results.values():
            i.event.set()

        if not self.is_media and callable(self.client.disconnect_handler):
            try:
                await self.client.disconnect_handler(self.client)
            except BaseException:
                print_exc()

    async def restart(self: Self, /) -> None:
        await self.stop()
        await self.start()

    async def handle_packet(self: Self, packet: bytes, /) -> None:
        try:
            data = await self.client.loop.run_in_executor(
                crypto_executor,
                unpack,
                BytesIO(packet),
                self.session_id,
                self.auth_key,
                self.auth_key_id,
                self.stored_msg_ids,
            )
        except SecurityCheckMismatch:
            return self.connection.close()

        updates: list[TLObject] = []
        peers: list[Union[User, Chat, Channel]] = []
        for message in (
            data.body.messages
            if isinstance(data.body, MsgContainer)
            else (data,)
        ):
            if message.seq_no == 0:
                MsgId.set_server_time(message.msg_id / (2**32))
            elif message.seq_no % 2 != 0:
                if message.msg_id not in self.pending_acks:
                    self.pending_acks.add(message.msg_id)

            if isinstance(message.body, (MsgDetailedInfo, MsgNewDetailedInfo)):
                self.pending_acks.add(message.body.answer_msg_id)
            elif isinstance(message.body, NewSessionCreated):
                pass
            elif isinstance(message.body, (Updates, UpdatesCombined)):
                peers += message.body.users
                peers += message.body.chats
                updates += message.body.updates
            elif isinstance(
                message.body, (UpdateShortMessage, UpdateShortChatMessage)
            ):
                if message.body.out is False:
                    updates.append(message.body)
            elif isinstance(message.body, UpdateShort):
                updates.append(message.body.update)
            else:
                if isinstance(
                    message.body, (BadMsgNotification, BadServerSalt)
                ):
                    msg_id = message.body.bad_msg_id
                elif isinstance(message.body, (FutureSalts, RpcResult)):
                    msg_id = message.body.req_msg_id
                elif isinstance(message.body, Pong):
                    msg_id = message.body.msg_id
                else:
                    continue
                if msg_id in self.results:
                    self.results[msg_id].value = getattr(
                        message.body, 'result', message.body
                    )
                    self.results[msg_id].event.set()

        if len(self.pending_acks) >= self.ACKS_THRESHOLD:
            log.debug(f'Send {len(self.pending_acks)} acks')
            with suppress(BaseException):
                msg_ids = list(self.pending_acks)
                await self._send(MsgsAck(msg_ids=msg_ids), wait_response=False)
                self.pending_acks.clear()

        for update in updates:
            pts = getattr(update, 'pts', None)
            pts_count = getattr(update, 'pts_count', None)
            if pts is None or pts_count is None:
                continue
            elif isinstance(
                update, (UpdateShortMessage, UpdateShortChatMessage)
            ):
                if (date := getattr(update, 'date', None)) is None:
                    continue
                log.info(f'GetDifference (pts={pts}, pts_count={pts_count})')
                difference = await self.invoke(
                    GetDifference(pts=pts - pts_count, date=date, qts=-1)
                )
                updates += difference.other_updates
                updates += [
                    UpdateNewMessage(
                        message=message,
                        pts=pts,
                        pts_count=pts_count,
                    )
                    for message in difference.new_messages
                ]
                peers += difference.users + difference.chats

        if peers:
            await self.client.fetch_peers(peers)
            await self.client.storage.Session.remove()

        peers_ids = {_.id: _ for _ in peers}
        for update in updates:
            chat_id = message_id = data = text = query_id = is_private = None
            try:
                if isinstance(update, UpdateShortMessage):
                    chat_id, message_id = update.user_id, update.id
                    text, is_private = update.message, True

                elif isinstance(update, UpdateShortChatMessage):
                    chat_id, message_id = update.chat_id, update.id
                    text, is_private = update.message, False

                elif isinstance(
                    update,
                    (
                        UpdateNewMessage,
                        UpdateNewChannelMessage,
                        UpdateNewScheduledMessage,
                        UpdateEditMessage,
                        UpdateEditChannelMessage,
                        UpdateDeleteMessages,
                        UpdateDeleteChannelMessages,
                    ),
                ):
                    chat_id = get_peer_id(update.message.peer_id)
                    message_id = await Message._parse(
                        self.client,
                        update.message,
                        peers_ids,
                        peers_ids,
                        isinstance(update, UpdateNewScheduledMessage),
                    )
                    text = update.message.message
                    is_private = isinstance(update.message.peer_id, PeerUser)

                elif isinstance(
                    update,
                    (UpdateBotCallbackQuery, UpdateInlineBotCallbackQuery),
                ):
                    chat_id = get_peer_id(update.peer)
                    message_id = update.msg_id
                    data = Query.parse(update.data)
                    text = data.command
                    query_id = update.query_id
                    is_private = isinstance(update.peer, PeerUser)

                else:
                    continue
            except AttributeError as _:
                continue

            for group in sorted(self.client.groups):
                for handler in self.client.groups[group]:
                    if isinstance(handler, AdBotHandler) and (
                        await handler.check(
                            self.client,
                            chat_id=chat_id,
                            data=text,
                            query_id=query_id,
                            is_private=is_private,
                        )
                    ):
                        r = self.client.Registry
                        phone_number = self.client.storage.phone_number
                        name = handler.callback_name
                        task = self.client.loop.create_task(
                            handler(
                                self.client,
                                chat_id=chat_id,
                                message_id=message_id,
                                data=data,
                                query_id=query_id,
                            )
                        )
                        if phone_number not in r:
                            r[phone_number] = {}
                        if chat_id not in r[phone_number]:
                            r[phone_number][chat_id] = {}
                        if name not in r[phone_number][chat_id]:
                            r[phone_number][chat_id][name] = []
                        r[phone_number][chat_id][name].append(task)

                        def remove_task(task: Task, /) -> None:
                            nonlocal r, phone_number, chat_id, name
                            with suppress(BaseException):
                                r[phone_number][chat_id][name].remove(task)
                                if not r[phone_number][chat_id][name]:
                                    del r[phone_number][chat_id][name]
                                if not r[phone_number][chat_id]:
                                    del r[phone_number][chat_id]
                                if not r[phone_number]:
                                    del r[phone_number]

                            try:
                                task.result()
                            except BaseException:
                                print_exc()

                        task.add_done_callback(remove_task)
                        break

    async def ping_worker(self: Self, /) -> None:
        await self._send(
            PingDelayDisconnect(
                ping_id=0,
                disconnect_delay=int(self.WAIT_TIMEOUT + 10),
            ),
            wait_response=False,
        )

    async def network_worker(self: Self, /) -> None:
        log.info('NetworkTask started')

        def print_exception(task: Task, /) -> None:
            try:
                task.result()
            except BaseException:
                print_exc()

        while True:
            packet = await self.connection.recv()
            if packet is None or len(packet) == 4:
                if packet:
                    print(f"Server sent '{Int.read(BytesIO(packet))}'")
                if self.is_connected.is_set():
                    self.client.loop.create_task(self.restart())
                break

            task = self.client.loop.create_task(self.handle_packet(packet))
            task.add_done_callback(print_exception)

        log.info('NetworkTask stopped')

    async def _send(
        self: Self,
        /,
        data: TLObject,
        timeout: float = WAIT_TIMEOUT,
        *,
        wait_response: bool = True,
    ) -> TLObject:
        # Call log.debug twice because calling it once by appending 'data' to
        # the previous string (i.e. f'Kind: {data}') will cause 'data' to be
        # evaluated as string every time instead of  only when debug is
        # actually enabled.
        # log.debug('Sent:')
        # log.debug(message)

        payload = await self.client.loop.run_in_executor(
            crypto_executor,
            pack,
            message := self.msg_factory(data),
            self.salt,
            self.session_id,
            self.auth_key,
            self.auth_key_id,
        )

        await self.connection.send(payload)
        if not wait_response:
            return

        self.results[message.msg_id] = Result()
        with suppress(TimeoutError):
            await wait_for(self.results[message.msg_id].event.wait(), timeout)

        if (result := self.results.pop(message.msg_id).value) is None:
            raise TimeoutError
        elif isinstance(result, RpcError):
            if isinstance(data, (InvokeWithoutUpdates, InvokeWithTakeout)):
                data = data.query
            RPCError.raise_it(result, type(data))
        elif isinstance(result, BadMsgNotification):
            raise BadMsgNotificationError(result.error_code)
        elif isinstance(result, BadServerSalt):
            self.salt = result.new_server_salt
            return await self._send(data, timeout, wait_response=wait_response)
        else:
            return result

    async def send(
        self: Self,
        /,
        data: TLObject,
        retries: int = MAX_RETRIES,
        timeout: float = WAIT_TIMEOUT,
        sleep_threshold: float = SLEEP_THRESHOLD,
    ) -> TLObject:
        with suppress(TimeoutError):
            await wait_for(self.is_connected.wait(), self.WAIT_TIMEOUT)

        query = data
        if isinstance(data, (InvokeWithoutUpdates, InvokeWithTakeout)):
            query = data.query
        query = '.'.join(query.QUALNAME.split('.')[1:])

        while True:
            try:
                return await self._send(data, timeout=timeout)
            except FloodWait as e:
                if (amount := e.value) > (
                    sleep_threshold or self.SLEEP_THRESHOLD
                ):
                    raise

                log.warning(
                    f'[{self.client.storage.phone_number}] Waiting for '
                    f'{amount} seconds before continuing '
                    f"(required by '{query}')"
                )

                await sleep(amount)
            except (
                OSError,
                TimeoutError,
                InternalServerError,
                ServiceUnavailable,
            ) as e:
                if retries == 0:
                    raise e from None

                (log.warning if retries < 2 else log.info)(
                    f'[{Session.MAX_RETRIES - retries + 1}] Retrying '
                    f"'{query}' due to {str(e) or repr(e)}'"
                )

                await sleep(0.5)
                return await self.invoke(data, retries - 1, timeout)
