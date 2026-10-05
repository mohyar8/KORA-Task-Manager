import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from kora_api.access import models as access_models
from kora_api.core.config import get_settings
from kora_api.core.database import Base

# Every domain model module must be imported here so its tables are on Base.metadata.
MODEL_MODULES = (access_models,)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
# A caller (e.g. the test suite) may target another database via `sqlalchemy.url`.
database_url = (
    config.get_main_option("sqlalchemy.url") or get_settings().database_url.get_secret_value()
)


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a database connection (`alembic upgrade head --sql`)."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(database_url, poolclass=pool.NullPool)

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
