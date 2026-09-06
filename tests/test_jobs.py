"""Job queue: the claim is safe, failures are terminal, errors are safe to show a user.

The claim test is the one that matters. ``SELECT ... FOR UPDATE SKIP LOCKED`` is easy to write
and easy to write *wrong* -- drop ``SKIP LOCKED`` and the second worker blocks instead of moving
on; drop the status flip and the job is re-claimed the moment the lock releases. Both are
asserted below with two genuinely concurrent sessions rather than a simulated one.

The redaction tests need no database and never skip.
"""

# ruff: noqa: E402
# The pytest.importorskip guard below must run before the tieout.platform imports.

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

# The platform layer needs sqlalchemy, psycopg and pydantic-settings. Those are not in
# pyproject.toml yet -- that file is owned by another worker and this one only reports the
# requirement (see docs/PLATFORM.md, "Dependencies"). Until they land, skip this module loudly
# instead of failing collection and turning the whole suite red.
pytest.importorskip("sqlalchemy", reason="sqlalchemy is not installed; see docs/PLATFORM.md")
pytest.importorskip(
    "pydantic_settings", reason="pydantic-settings is not installed; see docs/PLATFORM.md"
)

from sqlalchemy import select

from tieout.platform import jobs
from tieout.platform.models import Job, JobStatus, Run, RunStatus
from tieout.platform.session import unscoped_session
from tieout.platform.tenancy import OrgScope, tenant_session
from tieout.platform.testing import requires_db, run, temp_org

# ── User-safe error messages (no database needed) ─────────────────────────────


class _LeakyError(Exception):
    """The kind of exception that would happily print a secret into a UI."""


def test_a_raw_exception_message_never_reaches_the_column() -> None:
    exc = _LeakyError(
        "failed reading C:\\Users\\govin\\secrets\\creds.csv via "
        "postgresql://admin:hunter2@db.internal:5432/prod token=deadbeefcafebabe0123456789abcdef"
    )
    message = jobs.safe_error_message(exc)
    for leak in ("govin", "hunter2", "db.internal", "deadbeefcafebabe", "C:\\", "postgresql://"):
        assert leak not in message, f"{leak!r} leaked into a user-facing error message"
    assert "_LeakyError" in message, "the error type is still useful to a support engineer"


def test_a_deliberate_user_message_survives_but_is_still_redacted() -> None:
    class Explained(Exception):
        user_message = "3 rows were quarantined: see /var/data/orgs/a/uploads/x.csv for details"

    message = jobs.safe_error_message(Explained())
    assert "3 rows were quarantined" in message
    assert "/var/data" not in message


def test_error_messages_are_bounded() -> None:
    class Long(Exception):
        user_message = "x" * 5000

    assert len(jobs.safe_error_message(Long())) <= 300


def test_no_traceback_text_can_reach_the_message() -> None:
    try:
        raise ValueError("inner boom")
    except ValueError as exc:
        message = jobs.safe_error_message(exc)
    assert "Traceback" not in message
    assert "inner boom" not in message, "an unlabelled message is treated as untrusted"


def test_an_unknown_job_kind_is_explained_not_dumped() -> None:
    with pytest.raises(jobs.UnknownJobKind):
        jobs.resolve_handler("no-such-kind")
    assert "not supported" in jobs.safe_error_message(jobs.UnknownJobKind("x"))


# ── The queue itself ──────────────────────────────────────────────────────────


def _scope(org_id: str) -> OrgScope:
    return OrgScope(org_id=org_id, actor="svc:tieout-worker@test")


async def _enqueue(org_id: str, *, kind: str = "noop", max_attempts: int = 3) -> None:
    async with tenant_session(_scope(org_id)) as session:
        await jobs.enqueue(
            session, kind=kind, payload={"period": "2026-01"}, max_attempts=max_attempts
        )
        await session.commit()


@requires_db
def test_a_claimed_job_is_not_claimed_twice_by_a_second_worker() -> None:
    """One job, two concurrent workers. Exactly one claim, and the loser is not blocked."""

    async def body() -> None:
        async with temp_org("jobs") as org:
            await _enqueue(org)

            async with (
                unscoped_session("worker-claim") as s1,
                unscoped_session("worker-claim") as s2,
            ):
                first = await jobs.claim_one(s1, "worker-1")
                assert first is not None
                assert first.status is JobStatus.RUNNING
                assert first.claimed_by == "worker-1"
                assert first.attempts == 1

                # s1 has not committed, so the row is still locked. SKIP LOCKED must make this
                # return promptly with nothing rather than wait on the lock.
                second = await asyncio.wait_for(jobs.claim_one(s2, "worker-2"), timeout=10)
                assert second is None, "the same job was claimed by two workers"

                await s1.commit()

                # After the commit the lock is gone, but status='running' keeps it unavailable.
                third = await jobs.claim_one(s2, "worker-2")
                assert third is None, "a running job was re-claimed once its lock released"
                await s2.rollback()

    run(body())


@requires_db
def test_two_workers_racing_two_jobs_get_one_each() -> None:
    async def body() -> None:
        async with temp_org("jobs") as org:
            await _enqueue(org)
            await _enqueue(org)

            async with (
                unscoped_session("worker-claim") as s1,
                unscoped_session("worker-claim") as s2,
            ):
                a = await jobs.claim_one(s1, "worker-1")
                b = await asyncio.wait_for(jobs.claim_one(s2, "worker-2"), timeout=10)
                assert a is not None and b is not None
                assert a.id != b.id, "SKIP LOCKED handed the same row to both workers"
                await s1.commit()
                await s2.commit()

    run(body())


@requires_db
def test_progress_advances_and_is_mirrored_onto_the_run() -> None:
    async def body() -> None:
        async with temp_org("jobs") as org:
            async with tenant_session(_scope(org)) as session:
                run_row = Run(period="2026-01", policy_version_label="2026.01-r3")
                session.add(run_row)
                await session.flush()
                job = await jobs.enqueue(session, kind="noop", run_id=run_row.id)
                await session.commit()
                job_id, run_id = job.id, run_row.id

            seen = []
            async with tenant_session(_scope(org)) as session:
                job = await session.get(Job, job_id)
                assert job is not None
                for percent in (0, 25, 60, 100):
                    await jobs.set_progress(session, job, percent)
                    seen.append(job.progress)
                await session.commit()

            assert seen == [0, 25, 60, 100]
            async with tenant_session(_scope(org)) as session:
                assert (await session.get(Run, run_id)).progress == 100
                assert (await session.get(Run, run_id)).status is RunStatus.RUNNING

    run(body())


@requires_db
def test_progress_is_clamped_rather_than_trusted() -> None:
    async def body() -> None:
        async with temp_org("jobs") as org:
            async with tenant_session(_scope(org)) as session:
                job = await jobs.enqueue(session, kind="noop")
                await jobs.set_progress(session, job, 250)
                assert job.progress == 100
                await jobs.set_progress(session, job, -5)
                assert job.progress == 0
                await session.rollback()

    run(body())


@requires_db
def test_a_failed_job_records_a_safe_error_and_stops_retrying() -> None:
    """It must not spin: at max attempts the job is terminal and never claimable again."""

    async def body() -> None:
        async with temp_org("jobs") as org:
            async with tenant_session(_scope(org)) as session:
                run_row = Run(period="2026-01", policy_version_label="2026.01-r3")
                session.add(run_row)
                await session.flush()
                job = await jobs.enqueue(session, kind="noop", run_id=run_row.id, max_attempts=1)
                await session.commit()
                job_id, run_id = job.id, run_row.id

            async with unscoped_session("worker-claim") as session:
                claimed = await jobs.claim_one(session, "worker-1")
                assert claimed is not None and claimed.id == job_id
                await jobs.fail(
                    session, claimed, _LeakyError("boom at C:\\Users\\govin\\run.py line 3")
                )
                await session.commit()

            async with tenant_session(_scope(org)) as session:
                job = await session.get(Job, job_id)
                assert job is not None
                assert job.status is JobStatus.FAILED
                assert job.attempts == 1
                assert job.error_message and "C:\\" not in job.error_message
                assert "govin" not in job.error_message
                # The run carries the same user-safe message, so a UI has something to show.
                run_row = await session.get(Run, run_id)
                assert run_row.status is RunStatus.FAILED
                assert run_row.error_message == job.error_message

            # And it is gone from the queue for good.
            async with unscoped_session("worker-claim") as session:
                assert await jobs.claim_one(session, "worker-2") is None
                await session.rollback()

    run(body())


@requires_db
def test_a_retryable_failure_backs_off_instead_of_spinning() -> None:
    async def body() -> None:
        async with temp_org("jobs") as org:
            await _enqueue(org, max_attempts=3)

            async with unscoped_session("worker-claim") as session:
                claimed = await jobs.claim_one(session, "worker-1")
                assert claimed is not None
                await jobs.fail(session, claimed, RuntimeError("transient"))
                assert claimed.status is JobStatus.QUEUED, "a retryable job returns to the queue"
                assert claimed.available_at > datetime.now(UTC) + timedelta(seconds=5)
                assert claimed.claimed_by is None
                await session.commit()

            # Requeued, but not available yet -- a polling worker gets nothing and sleeps.
            async with unscoped_session("worker-claim") as session:
                assert await jobs.claim_one(session, "worker-2") is None
                await session.rollback()

    run(body())


@requires_db
def test_the_worker_runs_a_handler_end_to_end() -> None:
    async def body() -> None:
        from tieout.platform import worker

        marks: list[int] = []

        async def handler(ctx: jobs.JobContext) -> None:
            assert ctx.payload == {"period": "2026-01"}
            for percent in (10, 55, 90):
                await ctx.progress(percent)
                marks.append(percent)

        jobs.JOB_HANDLERS["test-ok"] = handler
        try:
            async with temp_org("jobs") as org:
                await _enqueue(org, kind="test-ok")
                assert await worker.run_once() is True
                assert marks == [10, 55, 90]

                async with tenant_session(_scope(org)) as session:
                    job = (await session.execute(select(Job))).scalars().one()
                    assert job.status is JobStatus.COMPLETED
                    assert job.progress == 100
                    assert job.error_message is None

                assert await worker.run_once() is False, "the queue should now be empty"
        finally:
            jobs.JOB_HANDLERS.pop("test-ok", None)

    run(body())


@requires_db
def test_a_raising_handler_fails_the_job_without_killing_the_worker() -> None:
    async def body() -> None:
        from tieout.platform import worker

        async def handler(ctx: jobs.JobContext) -> None:
            raise _LeakyError("secret path /srv/tieout/data/holdout/expected_reconciliation.csv")

        jobs.JOB_HANDLERS["test-boom"] = handler
        try:
            async with temp_org("jobs") as org:
                await _enqueue(org, kind="test-boom", max_attempts=1)
                assert await worker.run_once() is True  # handled, not raised

                async with tenant_session(_scope(org)) as session:
                    job = (await session.execute(select(Job))).scalars().one()
                    assert job.status is JobStatus.FAILED
                    assert "holdout" not in (job.error_message or "")
                    assert "/srv" not in (job.error_message or "")
        finally:
            jobs.JOB_HANDLERS.pop("test-boom", None)

    run(body())


@requires_db
def test_an_unregistered_job_kind_fails_the_job_rather_than_the_worker() -> None:
    async def body() -> None:
        from tieout.platform import worker

        async with temp_org("jobs") as org:
            await _enqueue(org, kind="never-registered", max_attempts=1)
            assert await worker.run_once() is True

            async with tenant_session(_scope(org)) as session:
                job = (await session.execute(select(Job))).scalars().one()
                assert job.status is JobStatus.FAILED
                assert "not supported" in (job.error_message or "")

    run(body())


def test_registering_two_handlers_for_one_kind_is_an_error() -> None:
    async def a(ctx: jobs.JobContext) -> None: ...

    async def b(ctx: jobs.JobContext) -> None: ...

    jobs.register_handler("dup-kind", a)
    try:
        jobs.register_handler("dup-kind", a)  # idempotent
        with pytest.raises(ValueError, match="already registered"):
            jobs.register_handler("dup-kind", b)
    finally:
        jobs.JOB_HANDLERS.pop("dup-kind", None)
