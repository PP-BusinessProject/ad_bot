from asyncio import AbstractEventLoop, Lock, Semaphore, Task, get_event_loop
from concurrent.futures import Executor, ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from http import client
from logging import Logger, getLogger
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Final,
    List,
    Optional,
    Self,
    Type,
)

from apscheduler.schedulers import (
    SchedulerAlreadyRunningError,
    SchedulerNotRunningError,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram.client import Cache, Client
from pyrogram.enums.parse_mode import ParseMode
from pyrogram.parser import Parser
from pyrogram.session.internals import MsgId
from pyrogram.session.session import Session
from sqlalchemy.event.api import listen, remove
from sqlalchemy.sql.expression import select
from sqlalchemy.sql.functions import now
from sqlalchemy.sql.sqltypes import String

from .ad_bot_handler import AdBotHandler
from .ad_bot_session import AdBotSession
from .jobs import Jobs
from .messages import Commands, Messages
from .methods import Methods
from .models.base_interface import BaseInterface
from .models.clients.user_model import UserModel, UserRole
from .models.misc.input_model import InputModel
from .models.misc.settings_model import SettingsModel
from .sqlalchemy_storage import SQLAlchemyStorage
from .utils.cached_morph_analyzer import CachedMorphAnalyzer
from .utils.pyrogram import auto_init
from .utils.sqlalchemy_pg_compiler_patch import PGCompiler  # noqa: F401


@dataclass(init=False)
class AdBotClient(Commands, Jobs, Messages, Methods, Client):
    loop: Final[AbstractEventLoop]
    storage: Final[SQLAlchemyStorage]
    scheduler: Final[AsyncIOScheduler]
    logger: Final[Logger]
    name: Final[str]
    api_id: Final[int]
    api_hash: Final[str]
    app_version: Final[str]
    device_model: Final[str]
    system_version: Final[str]
    lang_code: Final[str]
    ipv6: Final[bool]
    proxy: Final[dict]
    test_mode: Final[bool]
    bot_token: Final[str]
    session_string: Final[str]
    in_memory: Final[bool]
    phone_number: Final[str]
    phone_code: Final[Optional[str]]
    password: Final[Optional[str]]
    workers: Final[int]
    workdir: Final[Path]
    plugins: Final[dict]
    parse_mode: Final[ParseMode]
    no_updates: Final[bool]
    takeout: Final[bool]
    sleep_threshold: Final[int]
    hide_password: Final[bool]
    executor: Final[Executor]
    dispatcher: Final[None]
    rnd_id: Final[Type[MsgId]]
    parser: Final[Parser]
    message_cache: Final[Cache]
    session: Final[AdBotSession]
    media_sessions: Final[dict]
    media_sessions_lock: Final[Lock]
    save_file_semaphore: Final[Semaphore]
    get_file_semaphore: Final[Semaphore]
    is_connected: Optional[bool]
    is_initialized: Optional[bool]
    takeout_id: Optional[int]
    disconnect_handler: Optional[Any]
    username: Optional[str]
    is_bot: Optional[bool]

    groups: Final[Dict[int, List[AdBotHandler]]]
    listeners: Final[
        Dict[
            BaseInterface,
            Dict[str, List[Callable[[Any, Any, BaseInterface], None]]],
        ]
    ]
    morph: Final[Type[CachedMorphAnalyzer]]
    _workers: ClassVar[Dict[int, Self]] = {}
    Registry: ClassVar[Dict[int, Dict[int, Dict[str, List[Task]]]]] = {}

    def __init__(
        self: Self,
        /,
        storage: SQLAlchemyStorage,
        scheduler: Optional[AsyncIOScheduler] = None,
        logger: Optional[Logger] = None,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        app_version: str = Client.APP_VERSION,
        device_model: str = Client.DEVICE_MODEL,
        system_version: str = Client.SYSTEM_VERSION,
        lang_code: str = Client.LANG_CODE,
        proxy: Optional[dict] = None,
        bot_token: Optional[str] = None,
        workers: int = Client.WORKERS,
        plugins: Optional[dict] = None,
        parse_mode: ParseMode = ParseMode.DEFAULT,
        sleep_threshold: int = AdBotSession.SLEEP_THRESHOLD,
        max_concurrent_transmissions: int = Client.MAX_CONCURRENT_TRANSMISSIONS,
        executor: Optional[Executor] = None,
        *,
        ipv6: bool = False,
        no_updates: bool = False,
        takeout: bool = False,
        loop: Optional[AbstractEventLoop] = None,
    ):
        object.__setattr__(self, 'loop', loop or get_event_loop())
        object.__setattr__(self, 'storage', storage)
        object.__setattr__(self, 'name', str(storage.phone_number))
        object.__setattr__(self, 'api_id', api_id)
        object.__setattr__(self, 'api_hash', api_hash)
        object.__setattr__(self, 'app_version', app_version)
        object.__setattr__(self, 'device_model', device_model)
        object.__setattr__(self, 'system_version', system_version)
        object.__setattr__(self, 'lang_code', lang_code)
        object.__setattr__(self, 'ipv6', ipv6)
        object.__setattr__(self, 'proxy', proxy)
        object.__setattr__(self, 'test_mode', False)
        object.__setattr__(self, 'bot_token', bot_token)
        object.__setattr__(self, 'session_string', None)
        object.__setattr__(self, 'in_memory', False)
        object.__setattr__(self, 'phone_number', str(storage.phone_number))
        object.__setattr__(self, 'phone_code', None)
        object.__setattr__(self, 'password', None)
        object.__setattr__(self, 'workers', workers)
        object.__setattr__(self, 'workdir', self.WORKDIR)
        object.__setattr__(self, 'plugins', plugins)
        object.__setattr__(self, 'parse_mode', parse_mode)
        object.__setattr__(self, 'no_updates', no_updates)
        object.__setattr__(self, 'takeout', takeout)
        object.__setattr__(self, 'sleep_threshold', sleep_threshold)
        object.__setattr__(self, 'hide_password', True)
        object.__setattr__(
            self, 'max_concurrent_transmissions', max_concurrent_transmissions
        )
        object.__setattr__(
            self,
            'executor',
            executor
            if executor is not None
            else ThreadPoolExecutor(1, thread_name_prefix='Handler'),
        )
        object.__setattr__(self, 'dispatcher', None)
        object.__setattr__(self, 'rnd_id', MsgId)
        object.__setattr__(self, 'parser', Parser(self))
        object.__setattr__(self, 'message_cache', Cache(10000))
        object.__setattr__(self, 'scheduler', scheduler or AsyncIOScheduler())
        object.__setattr__(self, 'logger', logger or getLogger('client'))
        object.__setattr__(self, 'morph', CachedMorphAnalyzer)
        object.__setattr__(self, 'groups', {})
        object.__setattr__(self, 'listeners', {})
        object.__setattr__(self, 'media_sessions', {})
        object.__setattr__(self, 'media_sessions_lock', Lock())
        object.__setattr__(
            self,
            'save_file_semaphore',
            Semaphore(self.max_concurrent_transmissions),
        )
        object.__setattr__(
            self,
            'get_file_semaphore',
            Semaphore(self.max_concurrent_transmissions),
        )
        object.__setattr__(self, 'is_connected', None)
        object.__setattr__(self, 'is_initialized', None)
        object.__setattr__(self, 'takeout_id', None)
        object.__setattr__(self, 'disconnect_handler', None)
        object.__setattr__(self, 'username', None)
        object.__setattr__(self, 'is_bot', None)
        if self.storage.is_nested:
            # self.groups[0] = [
            #     AdBotHandler(self.reply_to_user, action=None, is_query=False)
            # ]
            return

        self.groups[0] = [
            AdBotHandler(
                self.input_message,
                self.INPUT,
                replace=True,
                private=False,
            ),
            AdBotHandler(self.page_message, self.PAGE, is_query=True),
            #
            AdBotHandler(self.start_message, '/start', is_query=False),
            AdBotHandler(
                self.start_message,
                self.SERVICE._SELF,
                is_query=True,
            ),
            #
            AdBotHandler(
                self.service_help,
                self.HELP,
                private=False,
                is_query=True,
            ),
            AdBotHandler(
                self.service_validation,
                self.SERVICE,
                private=False,
                is_query=True,
            ),
            AdBotHandler(
                self.service_subscription,
                self.SUBSCRIPTION,
                private=False,
                is_query=True,
            ),
            #
            AdBotHandler(
                self.chats_list,
                self.SENDER_CHAT.LIST,
                check_user=UserRole.SUPPORT,
                is_query=True,
            ),
            AdBotHandler(
                self.chat_message,
                self.SENDER_CHAT,
                check_user=UserRole.SUPPORT,
                is_query=True,
            ),
            #
            AdBotHandler(
                self.clients_list,
                self.SENDER_CLIENT.LIST,
                check_user=UserRole.SUPPORT,
                is_query=True,
            ),
            AdBotHandler(
                self.client_message,
                self.SENDER_CLIENT,
                check_user=UserRole.SUPPORT,
                is_query=True,
            ),
            #
            AdBotHandler(
                self.bots_list,
                self.BOT.LIST,
                check_user=UserRole.SUPPORT,
                is_query=True,
            ),
            AdBotHandler(
                self.bot_message,
                self.BOT,
                check_user=UserRole.USER,
                is_query=True,
            ),
            #
            AdBotHandler(
                self.settings_message,
                (self.SETTINGS, self.SETTINGS_DELETE),
                check_user=UserRole.USER,
                is_query=True,
            ),
            #
            AdBotHandler(
                self.ad_message,
                self.AD,
                check_user=UserRole.USER,
                is_query=True,
            ),
        ]

    def __del__(self: Self, /) -> None:
        with suppress(AttributeError):
            super().__del__()
        for model in self.listeners:
            for name, listeners in self.listeners[model].items():
                for listener in listeners:
                    remove(model, name, listener)

    async def start(self: Self, /) -> Self:
        with suppress(SchedulerAlreadyRunningError):
            self.scheduler.start(paused=True)
        if (self := await super().start()).storage.is_nested:
            return self

        settings: SettingsModel
        settings = await self.storage.Session.get(SettingsModel, True)
        self.input_create_listeners()
        self.user_create_listeners(settings.notify_subscription_end)
        for model, value in self.listeners.items():
            for name, listeners in value.items():
                for listener in listeners:
                    listen(model, name, listener, propagate=True)

        async for input in await self.storage.Session.stream_scalars(
            select(InputModel).filter_by(success=None)
        ):
            self.add_input_handler(
                input.chat_id,
                input.group,
                query_pattern=input.query_pattern,
                user_role=input.user_role,
                calls_count=input.calls_count,
                action=input.action,
                replace_calls=input.replace_calls,
            )

        async for user in await self.storage.Session.stream_scalars(
            select(UserModel).filter(
                UserModel.role.cast(String).not_in(
                    {UserRole.SUPPORT, UserRole.ADMIN}
                ),
                UserModel.subscription_from.is_not(None),
                UserModel.subscription_period.is_not(None),
                UserModel.subscription_from
                > now()
                - UserModel.subscription_period
                + settings.notify_subscription_end,
            )
        ):
            self.notify_subscription_end_job_init(
                user, settings.notify_subscription_end
            )

        self.sender_job_init(settings.send_interval)
        self.warmup_job_init(settings.warmup_interval)
        await self.storage.Session.remove()
        self.scheduler.resume()
        return self

    async def stop(self: Self, /) -> Self:
        try:
            return await super().stop()
        finally:
            if not self.storage.is_nested:
                with suppress(SchedulerNotRunningError):
                    self.scheduler.shutdown(wait=False)
                for worker in self.__class__._workers.values():
                    async with auto_init(worker, start=False, stop=True):
                        pass
                await self.storage.Session.remove()

    def get_worker(
        self: Self,
        phone_number: int,
        /,
        **kwargs: Any,
    ) -> Self:
        """
        Return the worker client by the `phone_number` for this `client`.

        Args:
            phone_number (``int``):
                The phone number to init the client by.

            kwargs (``dict[str, Any]``):
                The key-word arguments to init the client with.

        Returns:
            The cached worker self.

        Raises:
            ValueError, in case phone number is invalid.
        """
        if phone_number not in self.__class__._workers:
            if 'api_id' not in kwargs:
                kwargs['api_id'] = self.api_id
            if 'api_hash' not in kwargs:
                kwargs['api_hash'] = self.api_hash
            if 'storage' not in kwargs:
                kwargs['storage'] = SQLAlchemyStorage(
                    phone_number,
                    self.api_id,
                    self.storage.Session or self.storage.engine,
                    self.storage.metadata,
                )
            if 'scheduler' not in kwargs:
                kwargs['scheduler'] = self.scheduler
            self.__class__._workers[phone_number] = self.__class__(
                **kwargs, no_updates=True
            )
        return self.__class__._workers[phone_number]
