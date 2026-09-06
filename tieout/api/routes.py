"""HTTP routes — the dashboard's JSON surface (SPEC section 12)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from tieout.api.deps import (
    InMemoryPlatform,
    SessionContext,
    apply_review,
    attempt_close,
    build_close_report,
    build_queue_report,
    build_scoreboard_report,
    dump_jsonable,
    fetch_evidence,
    get_platform,
    get_session,
    store_upload,
    verify_audit,
    write_policy,
)
from tieout.api.schemas import PolicyWriteRequest, ReviewRequest, RunCreateRequest

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/close")
def close_status(
    period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    session: SessionContext = Depends(get_session),
    platform: InMemoryPlatform = Depends(get_platform),
) -> dict:
    """Close status screen — disposition breakdown, STP + fabrication, blocking list."""
    return build_close_report(session.org_id, period, platform)


@router.post("/close")
def close_period(
    period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    session: SessionContext = Depends(get_session),
    platform: InMemoryPlatform = Depends(get_platform),
) -> dict:
    """Attempt to close a period. No force/override parameters exist (I4)."""
    return attempt_close(session, period, platform)


@router.get("/queue")
def review_queue(
    blocking: bool = Query(False),
    aging: bool = Query(False),
    session: SessionContext = Depends(get_session),
    platform: InMemoryPlatform = Depends(get_platform),
) -> dict:
    """Review queue sorted by materiality x age."""
    return build_queue_report(
        session.org_id, blocking_only=blocking, with_aging=aging, platform=platform
    )


@router.post("/review/{work_key}")
def review_item(
    work_key: str,
    body: ReviewRequest,
    session: SessionContext = Depends(get_session),
    platform: InMemoryPlatform = Depends(get_platform),
) -> dict:
    """Approve, reject or reclassify — identity required, four-eyes enforced."""
    return apply_review(
        session,
        work_key,
        action=body.action,
        initiator=body.initiator,
        note=body.note,
        reclassify_to=body.reclassify_to,
        platform=platform,
    )


@router.get("/scoreboard")
def scoreboard(session: SessionContext = Depends(get_session)) -> dict:
    """Seven metrics, three baselines, chart data, per-class precision/recall."""
    return build_scoreboard_report(session.org_id)


@router.post("/runs")
def create_run(
    body: RunCreateRequest,
    session: SessionContext = Depends(get_session),
    platform: InMemoryPlatform = Depends(get_platform),
) -> dict:
    """Enqueue a reconcile run for the authenticated org."""
    run = platform.create_run(session.org_id, body.period)
    return dump_jsonable(run.model_dump())


@router.get("/runs")
def list_runs(
    session: SessionContext = Depends(get_session),
    platform: InMemoryPlatform = Depends(get_platform),
) -> dict:
    runs = platform.list_runs(session.org_id)
    return {"runs": dump_jsonable([r.model_dump() for r in runs])}


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    session: SessionContext = Depends(get_session),
    platform: InMemoryPlatform = Depends(get_platform),
) -> dict:
    run = platform.scoped_run(session, run_id)
    return dump_jsonable(run.model_dump())


@router.put("/runs/{run_id}/uploads/{kind}")
async def upload_file(
    run_id: str,
    kind: Literal["internal", "processor", "bank"],
    request: Request,
    session: SessionContext = Depends(get_session),
    platform: InMemoryPlatform = Depends(get_platform),
) -> dict:
    """Accept one ReconRiver-shaped CSV. Content type and size validated at the boundary."""
    content = await request.body()
    return store_upload(
        session,
        run_id,
        kind,
        content,
        request.headers.get("content-type"),
        platform,
    )


@router.get("/audit/verify")
def audit_verify(
    session: SessionContext = Depends(get_session),
    platform: InMemoryPlatform = Depends(get_platform),
) -> dict:
    return verify_audit(session.org_id, platform)


@router.get("/audit/evidence/{work_key}")
def audit_evidence(
    work_key: str,
    session: SessionContext = Depends(get_session),
    platform: InMemoryPlatform = Depends(get_platform),
) -> dict:
    return fetch_evidence(session.org_id, work_key, platform)


@router.put("/policy")
def policy_write(
    body: PolicyWriteRequest,
    session: SessionContext = Depends(get_session),
    platform: InMemoryPlatform = Depends(get_platform),
) -> dict:
    """Human-only policy write with provenance. Agent identities are rejected."""
    expected = f"{session.actor.user}@{session.actor.org}"
    if body.identity.lower() != expected.lower():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="identity must match the authenticated session",
        )
    return write_policy(
        session,
        version=body.version,
        rationale=body.rationale,
        yaml_body=body.yaml_body,
        platform=platform,
    )
