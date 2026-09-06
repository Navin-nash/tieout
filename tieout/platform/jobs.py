"""Postgres-backed job queue. No Redis, no Celery (ADR-003).

    # ponytail: single polling worker, SKIP LOCKED claim. Fine to ~1 run/sec.
    # Run N workers if throughput matters -- the claim is already safe.

The claim is one statement::

    SELECT ... FROM job
     WHERE status = 'queued' AND available_at <= now()
     ORDER BY available_at, created_at
     LIMIT 1
       FOR UPDATE SKIP LOCKED

``FOR UPDATE`` takes a row lock inside the transaction; ``SKIP LOCKED`` makes a second worker
step over the locked row instead of blocking on it. Two workers polling at the same instant get
two different jobs, or one gets a job and the other gets nothing. Neither gets the same job.

Error messages stored on a job are **safe to show a user**: no traceback, no filesystem path,
no connection string. See :func:`safe_error_message` -- redaction happens on the way in, so
there is no path by which a raw exception string reaches the column.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tieout.platform.models import Job, JobStatus, Run, RunStatus

#: Handler signature: given the claimed job and its session, do the work.
#: Progress is reported by calling :func:`set_progress`.
JobHandler = Callable[["JobContext"], Awaitable[None]]

#: Registered by whoever owns the work. This module deliberately knows nothing about
#: reconciliation -- ``tieout/api`` and the close pipeline register their handlers here.
JOB_HANDLERS: dict[str, JobHandler] = {}

#: Backoff between attempts. Short, because a run either works or has a real defect.
RETRY_BACKOFF = (timedelta(seconds=10), timedelta(seconds=60), timedelta(minutes=5))

_GENERIC_FAILURE = "The run failed because of an internal error. Support can look it up by run id."


class UnknownJobKind(Exception):
    """No handler is registered for a job's ``kind``."""

    user_message = "This job type is not supported by the running worker version."


# ── User-safe error messages ──────────────────────────────────────────────────

#: Anything that looks like a path, a URL with credentials, or a long hex blob.
_REDACT = (
    re.compile(r"[A-Za-z]:\\[^\s\"']*"),  # C:\Users\...
    re.compile(r"(?<![\w.])/(?:[\w.\-]+/)+[\w.\-]*"),  # /var/lib/...
    re.compile(r"\b\w+://[^\s\"']*"),  # postgresql://user:pw@host/db
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),  # hashes, tokens
)

_MAX_MESSAGE = 300


def safe_error_message(exc: BaseException) -> str:
    """A message safe to render to a user.

    An exception may carry an explicit ``user_message`` attribute -- domain errors that were
    written to be shown to somebody do, and those pass through. Everything else is treated as
    potentially leaky: only the exception's class name survives, and even that goes through
    redaction in case it was formatted into a message.

    The conservative direction matters. A stack trace in a UI is an information disclosure;
    a vague message is an annoyance.
    """
    explicit = getattr(exc, "user_message", None)
    if isinstance(explicit, str) and explicit.strip():
        return _redact(explicit)[:_MAX_MESSAGE]
    return f"{_GENERIC_FAILURE} ({type(exc).__name__})"


def _redact(text: str) -> str:
    for pattern in _REDACT:
        text = pattern.sub("[redacted]", text)
    return " ".join(text.split())


# ── Enqueue ───────────────────────────────────────────────────────────────────


async def enqueue(
    session: AsyncSession,
    *,
    kind: str,
    payload: dict[str, Any] | None = None,
    run_id: UUID | None = None,
    max_attempts: int = 3,
    org_id: str | None = None,
) -> Job:
    """Queue a job. ``org_id`` is stamped by the tenant session; pass it only when unscoped."""
    job = Job(
        kind=kind,
        payload=payload or {},
        run_id=run_id,
        max_attempts=max_attempts,
        status=JobStatus.QUEUED,
        available_at=datetime.now(UTC),
    )
    if org_id is not None:
        job.org_id = org_id
    session.add(job)
    await session.flush()
    return job


# ── Claim ─────────────────────────────────────────────────────────────────────


async def claim_one(session: AsyncSession, worker_id: str) -> Job | None:
    """Claim the oldest available queued job, or return None.

    Must run inside a transaction: the row lock ``FOR UPDATE`` takes is released at commit, and
    the status flip to ``running`` is what stops the job being claimed again after that. The
    caller commits.

    This is a cross-tenant query by necessity -- the worker does not know whose job is next
    until it has one. It is the reason :func:`tieout.platform.session.unscoped_session` exists
    and why ``"worker-claim"`` is on its allowlist. Everything the *handler* then does runs in
    a tenant session scoped to the claimed job's org.
    """
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.QUEUED, Job.available_at <= datetime.now(UTC))
        .order_by(Job.available_at, Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = (await session.execute(stmt)).scalars().first()
    if job is None:
        return None

    job.status = JobStatus.RUNNING
    job.attempts += 1
    job.claimed_at = datetime.now(UTC)
    job.claimed_by = worker_id
    job.progress = 0
    job.error_message = None
    await session.flush()
    return job


# ── Progress and terminal states ──────────────────────────────────────────────


async def set_progress(session: AsyncSession, job: Job, percent: int) -> None:
    """Advance progress. Clamped, and mirrored onto the run so the UI has one thing to poll."""
    value = max(0, min(100, percent))
    job.progress = value
    if job.run_id is not None:
        await session.execute(
            update(Run).where(Run.id == job.run_id).values(progress=value, status=RunStatus.RUNNING)
        )
    await session.flush()


async def complete(session: AsyncSession, job: Job) -> None:
    job.status = JobStatus.COMPLETED
    job.progress = 100
    job.finished_at = datetime.now(UTC)
    job.error_message = None
    if job.run_id is not None:
        await session.execute(
            update(Run)
            .where(Run.id == job.run_id)
            .values(
                status=RunStatus.COMPLETED,
                progress=100,
                finished_at=job.finished_at,
                error_message=None,
            )
        )
    await session.flush()


async def fail(session: AsyncSession, job: Job, exc: BaseException) -> None:
    """Record a failure. Retries with backoff until ``max_attempts``, then stops.

    A job that has exhausted its attempts is left ``failed`` with ``available_at`` untouched,
    so the claim query -- which only looks at ``status = 'queued'`` -- never sees it again. It
    does not spin.
    """
    message = safe_error_message(exc)
    job.error_message = message
    job.finished_at = datetime.now(UTC)

    if job.attempts < job.max_attempts:
        backoff = RETRY_BACKOFF[min(job.attempts - 1, len(RETRY_BACKOFF) - 1)]
        job.status = JobStatus.QUEUED
        job.available_at = datetime.now(UTC) + backoff
        job.claimed_at = None
        job.claimed_by = None
    else:
        job.status = JobStatus.FAILED

    if job.run_id is not None and job.status is JobStatus.FAILED:
        await session.execute(
            update(Run)
            .where(Run.id == job.run_id)
            .values(status=RunStatus.FAILED, finished_at=job.finished_at, error_message=message)
        )
    await session.flush()


# ── Handler context ───────────────────────────────────────────────────────────


class JobContext:
    """What a handler gets: the job, a tenant-scoped session, and a progress callback."""

    def __init__(self, job: Job, session: AsyncSession) -> None:
        self.job = job
        self.session = session

    @property
    def org_id(self) -> str:
        return self.job.org_id

    @property
    def payload(self) -> dict[str, Any]:
        return dict(self.job.payload)

    async def progress(self, percent: int) -> None:
        await set_progress(self.session, self.job, percent)


def register_handler(kind: str, handler: JobHandler) -> None:
    """Register a handler for a job kind. Re-registration is an error, not a silent overwrite."""
    if kind in JOB_HANDLERS and JOB_HANDLERS[kind] is not handler:
        raise ValueError(f"a different handler is already registered for job kind {kind!r}")
    JOB_HANDLERS[kind] = handler


def resolve_handler(kind: str) -> JobHandler:
    try:
        return JOB_HANDLERS[kind]
    except KeyError:
        raise UnknownJobKind(f"no handler registered for job kind {kind!r}") from None
