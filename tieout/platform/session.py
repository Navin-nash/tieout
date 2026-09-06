"""Engine and session factory.

Nothing in here is tenant-aware on purpose. Tenant scoping lives in
:mod:`tieout.platform.tenancy`, which wraps the factory built here. The only session this
module hands out unscoped is :func:`unscoped_session`, whose name and required ``reason``
argument exist to make it obvious in review when someone reaches for it.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tieout.platform.settings import PlatformSettings, get_settings


def configure_event_loop_policy() -> None:
    """Windows only: psycopg's async mode cannot run on the ProactorEventLoop.

    Python 3.8+ defaults to Proactor on Windows and ``psycopg.connect`` raises
    ``InterfaceError`` on it. Any process that talks to Postgres through this package must be
    on a selector loop, so the policy is set at import rather than left to each entry point to
    remember. No-op everywhere else.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


configure_event_loop_policy()


def _connect_args(settings: PlatformSettings) -> dict[str, object]:
    args: dict[str, object] = {
        # Hosted poolers (Neon, Supabase, pgbouncer) multiplex server connections, so a
        # prepared statement cached on one backend is missing on the next. Disable the cache.
        "prepare_threshold": None,
    }
    if settings.db_hostaddr:
        # libpq still sends the URL's hostname for SNI and certificate verification; only the
        # address lookup is bypassed. See PlatformSettings.db_hostaddr.
        args["hostaddr"] = settings.db_hostaddr
    return args


def create_engine(settings: PlatformSettings | None = None) -> AsyncEngine:
    """Build an engine. Callers that want the process-wide one should use :func:`get_engine`."""
    settings = settings or get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.sql_echo,
        # Hosted Postgres autosuspends idle computes; a stale pooled connection surfaces as a
        # confusing mid-query disconnect without this.
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args=_connect_args(settings),
    )


_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """The raw, **unscoped** session factory.

    Private by convention to everything except :mod:`tieout.platform.tenancy` and
    :func:`unscoped_session`. Domain code must not call this: a session from here has no org
    filter attached and will happily read every tenant's rows.
    """
    global _factory
    if _factory is None:
        _factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _factory


async def dispose_engine() -> None:
    """Close the pool. Call on shutdown, and between tests that swap the database URL."""
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _factory = None


#: The only reasons an unscoped session is legitimate. Anything else is a tenancy bug.
UNSCOPED_REASONS = frozenset(
    {
        "worker-claim",  # the job queue claims across orgs before it knows whose job it is
        "provisioning",  # creating an Organisation row, which by definition has no org yet
        "migration",  # schema work
        "test",
    }
)


class UnscopedAccessError(RuntimeError):
    """An unscoped session was requested for a reason that is not on the allowlist."""


@asynccontextmanager
async def unscoped_session(reason: str) -> AsyncIterator[AsyncSession]:
    """A session with **no tenant filter**. Do not use this for domain reads.

    The ``reason`` argument is not logging decoration -- it is checked against
    :data:`UNSCOPED_REASONS` and an unrecognised value raises. The point is that reaching for
    an unscoped session has to be a deliberate, greppable, reviewable act rather than the
    thing you get by importing the obvious name.

    Rows read through this session are **not** org-filtered. A caller that goes on to return
    them to a user has just written a cross-tenant leak.
    """
    if reason not in UNSCOPED_REASONS:
        raise UnscopedAccessError(
            f"unscoped database access requires a recognised reason; {reason!r} is not one of "
            f"{sorted(UNSCOPED_REASONS)}. If you are reading domain data, use "
            "tieout.platform.tenancy.tenant_session(scope) instead."
        )
    async with get_sessionmaker()() as session:
        yield session
