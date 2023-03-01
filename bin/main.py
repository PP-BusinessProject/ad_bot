from asyncio import current_task
from logging import DEBUG, Filter, LogRecord, basicConfig, getLogger, root
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
from typing_extensions import Self

if __name__ == '__main__':
    from lib.ad_bot_client import AdBotClient
    from lib.models.base_interface import Base
    from lib.sqlalchemy_storage import SQLAlchemyStorage

    class _CustomFilter(Filter):
        def filter(self: Self, record: LogRecord, /) -> bool:
            return super().filter(record) and not (
                record.args[0].id.startswith('ping_job')
                or record.msg.endswith('executed successfully')
            )

    basicConfig(level=environ.get('LOGGING', 'INFO').strip())
    getLogger('apscheduler.executors.default').addFilter(_CustomFilter())
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
        # proxy=dict(
        #     scheme='http',
        #     hostname='0.0.0.0',
        #     port=int(environ['PORT'].strip()),
        # )
        # if environ.get('PORT')
        # else None,
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
                            'timmy:postgres@localhost:5432/ad_bot',
                        )
                        .split('://')[-1]
                        .split('?')[0],
                        poolclass=AsyncAdaptedQueuePool,
                        pool_size=20,
                        max_overflow=0,
                        pool_recycle=3600,
                        pool_pre_ping=True,
                        pool_use_lifo=True,
                        connect_args=dict(
                            ssl=False,
                            server_settings=dict(jit='off'),
                        ),
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
