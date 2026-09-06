"""Test support for the platform layer.

This lives in the package rather than in ``tests/conftest.py`` because ``conftest.py`` is
shared with every other worker's tests and this package owns none of it.

Two things it provides:

* :data:`requires_db` -- a skip marker. The platform tests need a real Postgres: ``NUMERIC``
  semantics, ``FOR UPDATE SKIP LOCKED`` and ``with_loader_criteria`` against actual SQL are the
  things under test, and a SQLite stand-in would test a different system. Where a guarantee can
  be checked without a database (the metadata has no float column; a path cannot escape its
  org root) it is checked without one, and those tests never skip.
* :func:`temp_org` -- an isolated organisation per test, dropped afterwards. Tenant rows cascade
  from ``organisation``, so cleanup is one delete.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import pytest

from tieout.platform.session import configure_event_loop_policy

configure_event_loop_policy()

T = TypeVar("T")

#: Tables the migration must have created before the DB tests mean anything.
_REQUIRED_TABLES = ("organisation", "run", "work_item", "disposition", "job")

_probe: tuple[bool, str] | None = None


def run(coro: Coroutine[Any, Any, T]) -> T:
    """Drive an async test body.

    Plain ``asyncio.run`` rather than pytest-asyncio: the plugin needs an ``asyncio_mode``
    setting in ``pyproject.toml``, which this worker does not own. One wrapper per test is
    cheaper than a contended config change.
    """
    return asyncio.run(coro)


async def _probe_database() -> tuple[bool, str]:
    if not os.environ.get("DATABASE_URL"):
        return False, "DATABASE_URL is not set; platform database tests need a real Postgres"
    try:
        from sqlalchemy import text

        from tieout.platform.session import dispose_engine, get_engine

        try:
            async with get_engine().connect() as conn:
                found = set(
                    (
                        await conn.execute(
                            text(
                                "select table_name from information_schema.tables "
                                "where table_schema = 'public'"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
        finally:
            await dispose_engine()
    except Exception as exc:  # noqa: BLE001 - any connection failure means "skip", not "fail"
        return False, f"cannot reach DATABASE_URL ({type(exc).__name__})"

    missing = [t for t in _REQUIRED_TABLES if t not in found]
    if missing:
        return (
            False,
            f"schema not migrated (missing {', '.join(missing)}); run `alembic upgrade head`",
        )
    return True, ""


def database_available() -> tuple[bool, str]:
    """Probe once per process."""
    global _probe
    if _probe is None:
        _probe = run(_probe_database())
    return _probe


def _skip_reason() -> str:
    return database_available()[1]


requires_db = pytest.mark.skipif(not database_available()[0], reason=_skip_reason())


def new_org_id(label: str) -> str:
    """A collision-proof org id. Tests share one database; they must not share a tenant."""
    return f"{label}-{uuid.uuid4().hex[:12]}"


@asynccontextmanager
async def temp_org(label: str = "org") -> AsyncIterator[str]:
    """Create an organisation, yield its id, delete it (and everything under it) afterwards."""
    from sqlalchemy import delete

    from tieout.platform.models import Organisation
    from tieout.platform.session import unscoped_session

    org_id = new_org_id(label)
    async with unscoped_session("test") as session:
        session.add(Organisation(id=org_id, slug=org_id, name=f"Test org {org_id}", is_demo=True))
        await session.commit()
    try:
        yield org_id
    finally:
        async with unscoped_session("test") as session:
            await session.execute(delete(Organisation).where(Organisation.id == org_id))
            await session.commit()


@asynccontextmanager
async def two_orgs() -> AsyncIterator[tuple[str, str]]:
    """Two isolated tenants. The setup for every cross-tenant assertion."""
    async with temp_org("orga") as a, temp_org("orgb") as b:
        yield a, b
