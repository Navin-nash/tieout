"""The job worker. Runnable entry point.

    python -m tieout.platform.worker

    # ponytail: single polling worker, SKIP LOCKED claim. Fine to ~1 run/sec.
    # Run N workers if throughput matters -- the claim is already safe.

One loop, one job at a time. Each iteration is two transactions:

1. **Claim** -- an unscoped transaction, because the worker cannot know whose job is next until
   it holds one. Commits immediately so the row lock is released and the ``running`` status is
   what keeps other workers off it.
2. **Execute** -- a tenant session scoped to the claimed job's org. Everything the handler
   touches is filtered to that org, so a handler bug cannot read across tenants.

Splitting them matters: holding the claim transaction open for the length of a reconcile would
keep a row lock for minutes and turn a crashed worker into a stuck queue.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import signal
import socket
from uuid import UUID

from tieout.platform import jobs
from tieout.platform.models import Job
from tieout.platform.session import dispose_engine, unscoped_session
from tieout.platform.tenancy import OrgScope, tenant_session

log = logging.getLogger("tieout.worker")

DEFAULT_POLL_SECONDS = 1.0

#: The principal a worker acts as. A distinct service identity, never a shared account
#: (AS 1105 requirement 1 -- see tieout/audit/identity.py).
WORKER_SERVICE_NAME = "tieout-worker"


def worker_id() -> str:
    """Host and pid, so ``job.claimed_by`` points at something you can go and look at."""
    return f"{socket.gethostname()}:{os.getpid()}"


async def _claim() -> tuple[UUID, str, str] | None:
    """Claim a job and return its identity. Returns None when the queue is empty.

    Only ids come back, not the ORM object: the claim session closes here, and the execute step
    re-loads the job inside a tenant-scoped session so that even the worker's own handling goes
    through the tenant filter.
    """
    async with unscoped_session("worker-claim") as session:
        job = await jobs.claim_one(session, worker_id())
        if job is None:
            await session.rollback()
            return None
        identity = (job.id, job.org_id, job.kind)
        await session.commit()
        return identity


async def _execute(job_id: UUID, org_id: str, kind: str) -> None:
    """Run one claimed job inside its own tenant scope."""
    scope = OrgScope(org_id=org_id, actor=f"svc:{WORKER_SERVICE_NAME}@{worker_id()}")
    async with tenant_session(scope) as session:
        job = await session.get(Job, job_id)
        if job is None:
            # Filtered out by the tenant scope, or deleted between claim and execute. Either
            # way there is nothing safe to do with it here.
            log.warning("claimed job %s is not visible in org %s; skipping", job_id, org_id)
            return
        try:
            handler = jobs.resolve_handler(kind)
            await handler(jobs.JobContext(job, session))
            await jobs.complete(session, job)
        except Exception as exc:  # noqa: BLE001 - the worker must survive any handler
            # log.exception keeps the detail server-side; only the redacted form is persisted.
            log.exception("job %s (%s) failed on attempt %s", job_id, kind, job.attempts)
            await jobs.fail(session, job, exc)
        await session.commit()


async def run_once() -> bool:
    """Claim and run at most one job. Returns True if a job was processed."""
    claimed = await _claim()
    if claimed is None:
        return False
    await _execute(*claimed)
    return True


async def run_worker(
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    stop: asyncio.Event | None = None,
    max_jobs: int | None = None,
) -> int:
    """Poll until stopped. Returns the number of jobs processed.

    ``max_jobs`` bounds the loop, which is what the tests use instead of racing a signal.
    """
    stop = stop or asyncio.Event()
    processed = 0
    log.info("worker %s polling every %.1fs", worker_id(), poll_seconds)
    while not stop.is_set():
        if max_jobs is not None and processed >= max_jobs:
            break
        try:
            did_work = await run_once()
        except Exception:  # noqa: BLE001 - a transient database error must not kill the worker
            log.exception("worker iteration failed; backing off")
            did_work = False
        if did_work:
            processed += 1
            continue
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
    log.info("worker %s stopping after %d job(s)", worker_id(), processed)
    return processed


def _install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows has no add_signal_handler
            loop.add_signal_handler(sig, stop.set)


async def _main(poll_seconds: float) -> int:
    stop = asyncio.Event()
    _install_signal_handlers(stop)
    try:
        return await run_worker(poll_seconds=poll_seconds, stop=stop)
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="Tieout background job worker.")
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(
        level=args.log_level.upper(), format="%(asctime)s %(levelname)-7s %(name)s %(message)s"
    )
    asyncio.run(_main(args.poll_seconds))


if __name__ == "__main__":
    main()
