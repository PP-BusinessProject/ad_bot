from asyncio import AbstractEventLoop, Lock, Semaphore, Task, get_event_loop
from concurrent.futures import Executor, ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
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
    Set,
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
from sqlalchemy.event.api import remove

from .ad_bot_handler import AdBotHandler
from .ad_bot_session import AdBotSession
from .jobs import Jobs
from .messages import Commands, Messages
from .methods import Methods
from .models.base_interface import BaseInterface
from .sqlalchemy_storage import SQLAlchemyStorage
from .utils.cached_morph_analyzer import CachedMorphAnalyzer
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
    _workers_locks: ClassVar[Dict[int, Lock]] = {}
    _workers_count: ClassVar[Dict[int, int]] = {}
    _workers_must_stop: ClassVar[Set[int]] = set()
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

    def __del__(self: Self, /) -> None:
        with suppress(AttributeError):
            super().__del__()
        for model in self.listeners:
            for name, listeners in self.listeners[model].items():
                for listener in listeners:
                    remove(model, name, listener)

    async def start(self: Self, /) -> Self:
        with suppress(SchedulerAlreadyRunningError):
            self.scheduler.start()
        return await super().start()

    async def stop(self: Self, /) -> Self:
        try:
            return await super().stop()
        finally:
            if not self.storage.is_nested:
                with suppress(SchedulerNotRunningError):
                    self.scheduler.shutdown(wait=False)
                for worker in list(self.__class__._workers.values()):
                    async with self.worker(
                        worker.phone_number,
                        start=False,
                        stop=True,
                        suppress=True,
                    ):
                        pass
                await self.storage.Session.remove()

    @asynccontextmanager
    async def worker(
        self: Self,
        phone_number: int,
        /,
        *,
        start: bool = True,
        stop: Optional[bool] = True,
        only_connect: bool = False,
        suppress: bool = False,
        **kwargs: Any,
    ):
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
        if phone_number not in (cls := self.__class__)._workers:
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
            if 'no_updates' not in kwargs:
                kwargs['no_updates'] = True
            cls._workers[phone_number] = cls(**kwargs)

        is_initialized: Optional[bool] = None
        client = cls._workers[phone_number]
        try:
            if phone_number not in cls._workers_locks:
                cls._workers_locks[phone_number] = Lock()
            async with cls._workers_locks[phone_number]:
                if stop is None:
                    is_initialized = not client.is_initialized
                if start and (
                    not client.is_initialized and not client.is_connected
                ):
                    try:
                        if only_connect:
                            await client.connect()
                        else:
                            await client.start()
                    except BaseException as _:
                        if not suppress:
                            raise
                if phone_number not in cls._workers_count:
                    cls._workers_count[phone_number] = 0
                cls._workers_count[phone_number] += 1
                if stop or stop is None and is_initialized:
                    cls._workers_must_stop.add(phone_number)
            yield client
        finally:
            if phone_number not in cls._workers_locks:
                cls._workers_locks[phone_number] = Lock()
            async with cls._workers_locks[phone_number]:
                if phone_number not in cls._workers_count:
                    cls._workers_count[phone_number] = 1
                cls._workers_count[phone_number] -= 1
                if cls._workers_count[phone_number] <= 0 and (
                    phone_number in cls._workers_must_stop
                ):
                    try:
                        if client.is_initialized:
                            await client.stop()
                        elif client.is_connected:
                            await client.disconnect()
                    except BaseException as _:
                        if not suppress:
                            raise
                    cls._workers_must_stop.remove(phone_number)
