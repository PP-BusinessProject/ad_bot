from asyncio import current_task
from logging import DEBUG, basicConfig, root
from os import environ
from typing import Final

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlalchemy.ext.asyncio.scoping import async_scoped_session
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.pool.impl import AsyncAdaptedQueuePool

from ..lib.ad_bot_client import AdBotClient
from ..lib.models.base_interface import Base
from ..lib.sqlalchemy_storage import SQLAlchemyStorage

#
basicConfig(level=environ.get('LOGGING', 'INFO').strip())
client: Final[AdBotClient] = AdBotClient(
    api_id=int(environ['ADBOT_API_ID'].strip()),
    api_hash=environ['ADBOT_API_HASH'].strip(),
    bot_token=environ['ADBOT_TOKEN'].strip(),
    scheduler=AsyncIOScheduler(
        executors=dict(default=AsyncIOExecutor()),
        jobstores=dict(default=MemoryJobStore()),
        job_defaults=dict(
            coalesce=True,
            max_instances=1,
            replace_existing=True,
        ),
    ),
    storage=SQLAlchemyStorage(
        phone_number=0,
        api_id=int(environ['ADBOT_API_ID'].strip()),
        metadata=Base.metadata,
        bind=async_scoped_session(
            sessionmaker(
                create_async_engine(
                    echo=root.level == DEBUG,
                    url='postgresql+asyncpg://'
                    + environ.get(
                        'DATABASE_URL',
                        'postgres:postgres@localhost:5432/ad_bot',
                    ).split('://')[-1],
                    poolclass=AsyncAdaptedQueuePool,
                    pool_size=1,
                    max_overflow=-1,
                    pool_recycle=3600,
                    pool_pre_ping=True,
                    pool_use_lifo=True,
                    connect_args=dict(server_settings=dict(jit='off')),
                ),
                class_=AsyncSession,
                expire_on_commit=False,
                future=True,
            ),
            scopefunc=current_task,
        ),
    ),
)
client.run()
