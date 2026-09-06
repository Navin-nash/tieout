"""Alembic environment -- async, psycopg 3, URL from the environment only.

``alembic.ini`` carries no ``sqlalchemy.url``. The URL comes from ``DATABASE_URL`` through
:mod:`tieout.platform.settings`, which is also what the application uses, so a migration can
never run against a different database than the one the app talks to.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from tieout.platform.models import Base
from tieout.platform.session import configure_event_loop_policy
from tieout.platform.settings import get_settings

configure_event_loop_policy()  # Windows: psycopg async cannot run on the ProactorEventLoop

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_settings = get_settings()
config.set_main_option("sqlalchemy.url", _settings.database_url)


def _engine_kwargs() -> dict[str, object]:
    connect_args: dict[str, object] = {"prepare_threshold": None}
    if _settings.db_hostaddr:
        connect_args["hostaddr"] = _settings.db_hostaddr
    return {"poolclass": pool.NullPool, "connect_args": connect_args}


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting. ``alembic upgrade head --sql``."""
    context.configure(
        url=_settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Catch a NUMERIC that someone quietly widened, or worse, turned into a float.
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        **_engine_kwargs(),
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Support being driven from an already-running loop, as well as standalone."""
    connectable = config.attributes.get("connection", None)
    if connectable is None:
        asyncio.run(run_async_migrations())
    else:
        do_run_migrations(connectable)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
