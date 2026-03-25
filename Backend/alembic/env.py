import asyncio
import sys
from os.path import abspath , dirname , join
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import Connection, engine_from_config, pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.database.models import *
from app.database.db import Base

sys.path.insert(0, abspath(join(dirname(__file__), '..')))


config = context.config


if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", "postgresql+asyncpg://postgres:1234@localhost:5432/modifai")

target_metadata = Base.metadata




def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    # Asenkron engine oluşturma
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())