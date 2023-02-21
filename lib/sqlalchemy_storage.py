"""The module for Pyrogram SQLAlchemy storage based on Asyncio extension."""

from __future__ import annotations

from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timedelta
from logging import Logger
from os import remove
from os.path import isfile
from struct import pack
from typing import (
    Awaitable,
    Callable,
    Final,
    Optional,
    ParamSpec,
    Self,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from dateutil.tz.tz import tzlocal
from pyrogram.raw.types.input_peer_channel import InputPeerChannel
from pyrogram.raw.types.input_peer_chat import InputPeerChat
from pyrogram.raw.types.input_peer_user import InputPeerUser
from pyrogram.storage import Storage
from pyrogram.utils import MAX_USER_ID_OLD
from sqlalchemy.dialects.postgresql.dml import insert
from sqlalchemy.engine.base import Connection, Engine
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.ext.asyncio.engine import AsyncConnection, AsyncEngine
from sqlalchemy.ext.asyncio.scoping import async_scoped_session
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import Session as SyncSession
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.sql.expression import delete, exists, select
from sqlalchemy.sql.schema import Column, MetaData

from .models.misc.settings_model import SettingsModel
from .models.sessions.peer_model import PeerModel
from .models.sessions.session_model import SessionModel
from .utils.pyrogram import get_input_peer

#
P = ParamSpec('P')
T = TypeVar('T')


@dataclass(init=False, frozen=True)
class SQLAlchemyStorage(Storage):
    """The Pyrogram storage in SQLAlchemy asyncio."""

    USERNAME_TTL: Final[float] = timedelta(hours=8).total_seconds()

    phone_number: Final[int]
    _api_id: Final[int]
    logger: Final[Logger]
    engine: Final[Union[Engine, AsyncEngine]]
    Session: Final[
        Union[None, sessionmaker, scoped_session, async_scoped_session]
    ]
    metadata: Final[MetaData]

    @property
    def is_nested(self: Self, /) -> bool:
        return self.phone_number > 0

    def __init__(
        self: Self,
        /,
        phone_number: int,
        api_id: int,
        bind: Union[
            Union[scoped_session, SyncSession, Connection, Engine],
            async_scoped_session,
            AsyncSession,
            AsyncConnection,
            AsyncEngine,
        ],
        metadata: MetaData,
    ) -> None:
        if not isinstance(metadata, MetaData):
            raise ValueError(f'Invalid metadata: {metadata}')

        session = None
        while not isinstance(bind, (Engine, AsyncEngine)):
            if isinstance(bind, (scoped_session, async_scoped_session)):
                if session is None:
                    session = bind
                bind = bind.session_factory
            elif isinstance(bind, sessionmaker):
                if session is None:
                    session = bind
                bind = bind.kw['bind']
            elif isinstance(bind, (SyncSession, AsyncSession)):
                bind = bind.bind
            elif isinstance(bind, (Connection, AsyncConnection)):
                bind = bind.engine
            else:
                raise ValueError(f'Invalid bind: {bind}')

        object.__setattr__(self, 'phone_number', phone_number)
        object.__setattr__(self, '_api_id', api_id)
        object.__setattr__(
            self,
            'logger',
            Logger(f'{self.__class__.__name__}:{self.phone_number}'),
        )
        object.__setattr__(self, 'engine', bind)
        object.__setattr__(self, 'Session', session)
        object.__setattr__(self, 'metadata', metadata)

    async def open(self: Self, /) -> None:
        if self.is_nested:
            return
        async with self.engine.begin() as connection:
            await connection.run_sync(self.metadata.create_all)
        if await self.Session.scalar(select(~exists(SettingsModel))):
            self.Session.add(SettingsModel())
            await self.Session.commit()

    async def save(self: Self, /) -> None:
        pass

    async def close(self: Self, /) -> None:
        if not self.is_nested:
            await self.engine.dispose()

    async def delete(self: Self, /) -> None:
        await self.Session.execute(
            delete(SessionModel).filter_by(phone_number=self.phone_number)
        )
        await self.Session.commit()
        await self.close()
        if not self.is_nested and isfile(self.engine.url.database):
            remove(self.engine.url.database)

    async def update_peers(
        self: Self,
        /,
        peers: list[Tuple[int, int, str, str, int]],
    ) -> None:
        if not peers:
            return
        peer_mapper, statement = inspect(PeerModel), insert(PeerModel)
        await self.Session.execute(
            statement.on_conflict_do_update(
                index_elements=[col.name for col in peer_mapper.primary_key],
                set_={
                    column.name: statement.excluded[column.key]
                    for column in peer_mapper.columns
                    if column not in peer_mapper.primary_key
                    and column != peer_mapper.columns.created_at
                },
            ),
            [
                dict(
                    zip(
                        peer_mapper.columns.keys()[:-2],
                        (self.phone_number, *peer),
                    )
                )
                for peer in peers
            ],
        )
        await self.Session.commit()

    async def get_peer_by_id(
        self: Self,
        /,
        peer_id: int,
    ) -> Union[InputPeerUser, InputPeerChat, InputPeerChannel]:
        peer = await self.Session.get(PeerModel, (self.phone_number, peer_id))
        if peer is None:
            raise KeyError(f'ID not found: {peer_id}')
        return get_input_peer(peer)

    async def get_peer_by_username(
        self: Self,
        /,
        username: str,
    ) -> Union[InputPeerUser, InputPeerChat, InputPeerChannel]:
        peer_query = select(PeerModel).filter_by(
            session_phone_number=self.phone_number,
            username=username,
        )
        if (peer := await self.Session.scalar(peer_query)) is None:
            raise KeyError(f'Username not found: {username}')
        time_gone = datetime.now(tzlocal()) - peer.updated_at
        if time_gone.total_seconds() > self.USERNAME_TTL:
            raise KeyError(f'Username expired: {username}')
        return get_input_peer(peer)

    async def get_peer_by_phone_number(
        self: Self,
        /,
        phone_number: str,
    ) -> Union[InputPeerUser, InputPeerChat, InputPeerChannel]:
        peer_query = select(PeerModel).filter_by(
            session_phone_number=self.phone_number,
            phone_number=int(phone_number.removeprefix('+')),
        )
        if (peer := await self.Session.scalar(peer_query)) is None:
            raise KeyError(f'Phone number not found: {phone_number}')
        return get_input_peer(peer)

    async def _get_session(self: Self, /) -> SessionModel:
        session = await self.Session.get(SessionModel, self.phone_number)
        if not session:
            self.Session.add(
                session := SessionModel(
                    phone_number=self.phone_number,
                    api_id=self._api_id,
                )
            )
            await self.Session.commit()
        return session

    async def _get_or_update(
        self: Self,
        column: Column[T],
        /,
        value: Union[Type[object], T] = object,
    ) -> Optional[T]:
        session = await self._get_session()
        if value is object:
            try:
                return getattr(session, column.key, None)
            except MissingGreenlet:
                await self.Session.refresh(session)
                return getattr(session, column.key, None)

        setattr(session, column.key, value)
        await self.Session.commit()

    async def dc_id(
        self: Self,
        /,
        value: Union[Type[object], int] = object,
    ) -> Optional[int]:
        return await self._get_or_update(SessionModel.dc_id, value)

    async def api_id(
        self: Self,
        /,
        value: Union[Type[object], int] = object,
    ) -> Optional[int]:
        return await self._get_or_update(SessionModel.api_id, value)

    async def test_mode(
        self: Self,
        /,
        value: Union[Type[object], bool] = object,
    ) -> Optional[bool]:
        return await self._get_or_update(SessionModel.test_mode, value)

    async def auth_key(
        self: Self,
        /,
        value: Union[Type[object], bytes] = object,
    ) -> Optional[bytes]:
        return await self._get_or_update(SessionModel.auth_key, value)

    async def date(
        self: Self,
        /,
        value: Union[Type[object], int] = object,
    ) -> Optional[int]:
        if value is object:
            return await self._get_or_update(SessionModel.updated_at, value)

    async def user_id(
        self: Self,
        /,
        value: Union[Type[object], int] = object,
    ) -> Optional[int]:
        return await self._get_or_update(SessionModel.user_id, value)

    async def is_bot(
        self: Self,
        /,
        value: Union[Type[object], bool] = object,
    ) -> Optional[bool]:
        return await self._get_or_update(SessionModel.is_bot, value)

    async def export_session_string(self: Self, /) -> str:
        session = await self.Session.get(SessionModel, self.phone_number)
        return (
            urlsafe_b64encode(
                pack(
                    self.SESSION_STRING_FORMAT
                    if session.user_id < MAX_USER_ID_OLD
                    else self.SESSION_STRING_FORMAT_64,
                    session.dc_id,
                    session.test_mode,
                    session.auth_key,
                    session.user_id,
                    session.is_bot,
                )
            )
            .decode()
            .rstrip('=')
        )

    def scoped(
        self: Self,
        callable: Callable[P, Awaitable[T]],
        /,
    ) -> Callable[P, Awaitable[T]]:
        async def _callable(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await callable(*args, **kwargs)
            finally:
                await self.Session.remove()

        return _callable
