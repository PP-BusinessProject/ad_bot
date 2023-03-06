from asyncio import current_task, run
from logging import DEBUG, Filter, LogRecord, basicConfig, getLogger, root
from os import environ
from typing import Final, Self

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram.methods.utilities.idle import idle
from sqlalchemy.event.api import listen
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlalchemy.ext.asyncio.scoping import async_scoped_session
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.pool.impl import AsyncAdaptedQueuePool
from sqlalchemy.sql.expression import select
from sqlalchemy.sql.functions import now
from sqlalchemy.sql.sqltypes import String


async def main() -> None:
    from lib.ad_bot_client import AdBotClient
    from lib.ad_bot_handler import AdBotHandler
    from lib.models.base_interface import Base
    from lib.models.clients.user_model import UserModel, UserRole
    from lib.models.misc.input_model import InputModel
    from lib.models.misc.settings_model import SettingsModel
    from lib.sqlalchemy_storage import SQLAlchemyStorage

    class _CustomFilter(Filter):
        def filter(client: Self, record: LogRecord, /) -> bool:
            return super().filter(record) and not (
                record.args[0].id.startswith('ping_job')
                or record.msg.endswith('executed successfully')
            )

    basicConfig(level=environ.get('LOGGING', 'DEBUG').strip(), force=True)
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
                            'postgres:postgres@localhost:5433/ad_bot',
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
    client.groups[0] = [
        AdBotHandler(
            client.input_message,
            client.INPUT,
            replace=True,
            private=False,
        ),
        AdBotHandler(client.page_message, client.PAGE, is_query=True),
        #
        AdBotHandler(client.start_message, '/start', is_query=False),
        AdBotHandler(
            client.start_message,
            client.SERVICE._SELF,
            is_query=True,
        ),
        #
        AdBotHandler(
            client.service_help,
            client.HELP,
            private=False,
            is_query=True,
        ),
        AdBotHandler(
            client.service_validation,
            client.SERVICE,
            private=False,
            is_query=True,
        ),
        AdBotHandler(
            client.service_subscription,
            client.SUBSCRIPTION,
            private=False,
            is_query=True,
        ),
        #
        AdBotHandler(
            client.chats_list,
            client.CHAT.LIST,
            check_user=UserRole.USER,
            is_query=True,
        ),
        AdBotHandler(
            client.chat_message,
            client.CHAT,
            check_user=UserRole.USER,
            is_query=True,
        ),
        #
        AdBotHandler(
            client.clients_list,
            client.CLIENT.LIST,
            check_user=UserRole.SUPPORT,
            is_query=True,
        ),
        AdBotHandler(
            client.client_message,
            client.CLIENT,
            check_user=UserRole.USER,
            is_query=True,
        ),
        #
        AdBotHandler(
            client.bots_list,
            client.BOT.LIST,
            check_user=UserRole.SUPPORT,
            is_query=True,
        ),
        AdBotHandler(
            client.bot_message,
            client.BOT,
            check_user=UserRole.USER,
            is_query=True,
        ),
        #
        AdBotHandler(
            client.settings_message,
            (client.SETTINGS, client.SETTINGS_DELETE),
            check_user=UserRole.USER,
            is_query=True,
        ),
        #
        AdBotHandler(
            client.ad_message,
            client.AD,
            check_user=UserRole.USER,
            is_query=True,
        ),
    ]
    async with client:
        client.scheduler.pause()
        settings = await client.storage.Session.get(SettingsModel, True)
        client.input_create_listeners()
        client.user_create_listeners(settings.notify_subscription_end)
        for model, value in client.listeners.items():
            for name, listeners in value.items():
                for listener in listeners:
                    listen(model, name, listener, propagate=True)

        async for input in await client.storage.Session.stream_scalars(
            select(InputModel).filter_by(success=None)
        ):
            client.add_input_handler(
                input.chat_id,
                input.group,
                query_pattern=input.query_pattern,
                user_role=input.user_role,
                calls_count=input.calls_count,
                action=input.action,
                replace_calls=input.replace_calls,
            )

        async for user in await client.storage.Session.stream_scalars(
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
            client.notify_subscription_end_job_init(
                user, settings.notify_subscription_end
            )

        client.sender_job_init(settings.send_interval, run_now=True)
        # client.checker_job_init(settings.check_interval)
        await client.storage.Session.remove()
        client.scheduler.resume()
        await idle()


if __name__ == '__main__':
    run(main())
