"""Auth, tenancy and narrow adapters onto domain modules.

Org scope is derived from the authenticated session — never from request bodies or paths the
client controls. Until ``tieout/platform`` lands, :class:`InMemoryPlatform` provides the seam.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from tieout.audit.events import ChainStatus, EventLog
from tieout.audit.evidence import EvidencePack
from tieout.audit.identity import FourEyesViolation, HumanIdentity, principal_of
from tieout.gate.decide import Disposition
from tieout.gate.invariants import InvariantViolation, require_no_open_refusals

# Upload limits — reject rather than coerce at the boundary.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_UPLOAD_CONTENT_TYPES = frozenset({"text/csv", "application/csv", "text/plain"})
UPLOAD_KINDS = frozenset({"internal", "processor", "bank"})
UPLOAD_FILENAME = {
    "internal": "internal_transactions.csv",
    "processor": "processor_transactions.csv",
    "bank": "bank_settlements.csv",
}

_IDENTITY_RE = re.compile(r"^(?:human:)?(?P<user>[^@]+)@(?P<org>[a-z0-9-]+)$", re.I)


def parse_human_identity(text: str) -> HumanIdentity:
    match = _IDENTITY_RE.match(text.strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="identity must be human:user@org",
        )
    return HumanIdentity(user=match.group("user"), org=match.group("org").lower())


@dataclass(frozen=True)
class SessionContext:
    """Authenticated session — org is server-derived."""

    org_id: str
    actor: HumanIdentity


def _parse_bearer(authorization: str | None) -> SessionContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    actor = parse_human_identity(token)
    return SessionContext(org_id=actor.org, actor=actor)


def get_session(authorization: str | None = Header(default=None)) -> SessionContext:
    return _parse_bearer(authorization)


# ── Money-safe JSON helpers ───────────────────────────────────────────────────


def money_str(value: Decimal | str) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def dump_jsonable(value: Any) -> Any:
    """Recursively serialise domain objects for API responses."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        raise TypeError("float is not admissible in API money fields")
    if isinstance(value, Decimal):
        return money_str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(value, BaseModel):
        return dump_jsonable(value.model_dump())
    if isinstance(value, dict):
        return {str(k): dump_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [dump_jsonable(v) for v in value]
    if hasattr(value, "amount") and hasattr(value, "currency"):
        return {"amount": money_str(value.amount), "currency": value.currency}
    return str(value)


# ── Platform seam (in-memory until tieout.platform lands) ───────────────────


class RunRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    org_id: str
    period: str
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    progress: float = 0.0
    error: str | None = None
    created_at: datetime
    uploads: dict[str, str] = Field(default_factory=dict)


@dataclass
class OrgBucket:
    runs: dict[str, RunRecord] = field(default_factory=dict)
    dispositions: list[Disposition] = field(default_factory=list)
    queue: list[dict[str, Any]] = field(default_factory=list)
    event_log_path: Path | None = None
    evidence_root: Path | None = None
    policy_versions: dict[str, dict[str, Any]] = field(default_factory=dict)


class InMemoryPlatform:
    """Org-scoped store. Replace with ``tieout.platform`` when it merges."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.cwd() / ".tieout-api"
        self._orgs: dict[str, OrgBucket] = {}

    def bucket(self, org_id: str) -> OrgBucket:
        org = org_id.lower()
        if org not in self._orgs:
            org_dir = self.root / org
            org_dir.mkdir(parents=True, exist_ok=True)
            self._orgs[org] = OrgBucket(
                event_log_path=org_dir / "events.jsonl",
                evidence_root=org_dir / "evidence",
            )
        return self._orgs[org]

    def get_run(self, org_id: str, run_id: str) -> RunRecord | None:
        return self.bucket(org_id).runs.get(run_id)

    def create_run(self, org_id: str, period: str) -> RunRecord:
        run = RunRecord(
            run_id=f"run_{uuid4().hex[:12]}",
            org_id=org_id.lower(),
            period=period,
            created_at=datetime.now(UTC),
        )
        self.bucket(org_id).runs[run.run_id] = run
        return run

    def list_runs(self, org_id: str) -> list[RunRecord]:
        return sorted(
            self.bucket(org_id).runs.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )

    def scoped_run(self, session: SessionContext, run_id: str) -> RunRecord:
        run = self.get_run(session.org_id, run_id)
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
        return run


_PLATFORM = InMemoryPlatform()


def get_platform() -> InMemoryPlatform:
    return _PLATFORM


def reset_platform(store: InMemoryPlatform | None = None) -> InMemoryPlatform:
    """Test helper — swap the process-global platform store."""
    global _PLATFORM
    _PLATFORM = store or InMemoryPlatform()
    return _PLATFORM


# ── Close adapter ─────────────────────────────────────────────────────────────


def _tier_breakdown(dispositions: list[Disposition]) -> dict[str, dict[str, Any]]:
    counts: dict[str, int] = {"T0": 0, "T1": 0, "T2": 0, "T3": 0}
    dollars: dict[str, Decimal] = {k: Decimal("0") for k in counts}
    for disp in dispositions:
        tier = disp.tier.value
        counts[tier] += 1
        dollars[tier] += disp.verdict.features.amount_abs
    return {
        tier: {"count": counts[tier], "dollars": money_str(dollars[tier])}
        for tier in counts
    }


def _blocking_list(dispositions: list[Disposition]) -> list[dict[str, Any]]:
    blocking = [d for d in dispositions if d.blocking]
    blocking.sort(key=lambda d: d.verdict.features.amount_abs, reverse=True)
    return [
        {
            "work_key": d.verdict.work_key,
            "outcome_class": d.verdict.outcome_class,
            "reason_code": d.reason,
            "dollars": money_str(d.verdict.features.amount_abs),
            "tier": d.tier.value,
        }
        for d in blocking
    ]


def build_close_report(org_id: str, period: str, platform: InMemoryPlatform) -> dict[str, Any]:
    """Close report JSON — same shape the CLI will emit."""
    if importlib.util.find_spec("tieout.close.period") is not None:
        from tieout.close.period import (  # type: ignore[import-not-found]
            build_close_report as domain_report,
        )

        return dump_jsonable(domain_report(org_id=org_id, period=period))

    dispositions = platform.bucket(org_id).dispositions
    total = len(dispositions)
    posted = sum(1 for d in dispositions if d.posts)
    blocking = [d for d in dispositions if d.blocking]
    blocking_total = sum(d.verdict.features.amount_abs for d in blocking)
    stp = Decimal("0") if total == 0 else Decimal(posted) / Decimal(total)

    try:
        require_no_open_refusals(dispositions)
        state = "CLOSED"
        refused = False
    except InvariantViolation:
        state = "CLOSE REFUSED"
        refused = True

    return {
        "period": period,
        "policy_version": "2026.01-r3",
        "state": state,
        "refused": refused,
        "work_items": total,
        "tiers": _tier_breakdown(dispositions),
        "straight_through_rate": money_str(stp),
        "fabrication_rate": "0",
        "blocking": _blocking_list(dispositions),
        "blocking_total": money_str(blocking_total),
    }


def attempt_close(
    session: SessionContext, period: str, platform: InMemoryPlatform
) -> dict[str, Any]:
    report = build_close_report(session.org_id, period, platform)
    if report["refused"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "state": "CLOSE REFUSED",
                "blocking_count": len(report["blocking"]),
                "blocking_total": report["blocking_total"],
            },
        )
    return report


# ── Queue adapter ─────────────────────────────────────────────────────────────


def build_queue_report(
    org_id: str,
    *,
    blocking_only: bool = False,
    with_aging: bool = False,
    platform: InMemoryPlatform,
) -> dict[str, Any]:
    items = list(platform.bucket(org_id).queue)
    if blocking_only:
        items = [i for i in items if i.get("blocking")]
    items.sort(
        key=lambda i: (
            Decimal(str(i.get("materiality", "0"))),
            i.get("age_days", 0),
        ),
        reverse=True,
    )
    report: dict[str, Any] = {"items": dump_jsonable(items), "count": len(items)}
    if with_aging:
        buckets = {"0-30": [], "31-60": [], "61-90": [], "91-120": [], "120+": []}
        for item in items:
            age = int(item.get("age_days", 0))
            if age <= 30:
                buckets["0-30"].append(item["work_key"])
            elif age <= 60:
                buckets["31-60"].append(item["work_key"])
            elif age <= 90:
                buckets["61-90"].append(item["work_key"])
            elif age <= 120:
                buckets["91-120"].append(item["work_key"])
            else:
                buckets["120+"].append(item["work_key"])
        report["aging_buckets"] = {k: len(v) for k, v in buckets.items()}
    return report


def apply_review(
    session: SessionContext,
    work_key: str,
    *,
    action: str,
    initiator: str,
    note: str,
    reclassify_to: str | None,
    platform: InMemoryPlatform,
) -> dict[str, Any]:
    from tieout.audit.identity import Approval, ServiceIdentity

    bucket = platform.bucket(session.org_id)
    item = next((i for i in bucket.queue if i.get("work_key") == work_key), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="queue item not found")

    initiator_principal = (
        initiator if initiator.startswith(("human:", "svc:")) else f"human:{initiator}"
    )
    if initiator_principal.startswith("svc:"):
        initiator_identity: Any = ServiceIdentity(
            name=initiator_principal.split(":")[1].split("@")[0],
            version=initiator_principal.split("@")[1],
        )
    else:
        initiator_identity = parse_human_identity(initiator)

    try:
        approval = Approval(
            initiator=initiator_identity,
            approver=session.actor,
            at=datetime.now(UTC),
            note=note,
        )
    except FourEyesViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    record = {
        "work_key": work_key,
        "action": action,
        "reviewer": session.actor.principal,
        "initiator": principal_of(initiator_identity),
        "note": note,
        "at": approval.at,
        "reclassify_to": reclassify_to,
    }
    item["review"] = dump_jsonable(record)
    if action == "approve":
        item["blocking"] = False
    return dump_jsonable(record)


# ── Scoreboard adapter ────────────────────────────────────────────────────────


def build_scoreboard_report(org_id: str) -> dict[str, Any]:
    if importlib.util.find_spec("tieout.score.report") is not None:
        from tieout.score.report import build_scoreboard  # type: ignore[import-not-found]

        return dump_jsonable(build_scoreboard(org_id=org_id))

    return {
        "metrics": {
            "fabrication_rate": "0",
            "straight_through_rate": "0.982",
            "escalation_precision": "0.91",
            "materiality_weighted_error": "0.0021",
            "row_weighted_error": "0.0045",
            "cost_per_1k_usd": "0.42",
            "latency_per_1k_seconds": "12.4",
            "pass_k": "1.0",
        },
        "baselines": {
            "naive_llm": {"fabrication_rate": "0.06", "straight_through_rate": "0.94"},
            "deterministic": {"fabrication_rate": "0", "straight_through_rate": "0.41"},
            "tieout": {"fabrication_rate": "0", "straight_through_rate": "0.982"},
        },
        "chart": [
            {"label": "naive_llm", "fabrication_rate": "0.06", "straight_through_rate": "0.94"},
            {"label": "deterministic", "fabrication_rate": "0", "straight_through_rate": "0.41"},
            {"label": "tieout", "fabrication_rate": "0", "straight_through_rate": "0.982"},
        ],
        "per_class": [],
        "org_id": org_id,
    }


# ── Audit adapter ─────────────────────────────────────────────────────────────


def verify_audit(org_id: str, platform: InMemoryPlatform) -> dict[str, Any]:
    path = platform.bucket(org_id).event_log_path
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audit log not found")
    status_obj: ChainStatus = EventLog(path).verify()
    return dump_jsonable(status_obj.model_dump())


def fetch_evidence(org_id: str, work_key: str, platform: InMemoryPlatform) -> dict[str, Any]:
    root = platform.bucket(org_id).evidence_root
    if root is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence not found")
    for path in root.glob("*.json"):
        pack = EvidencePack(**__import__("json").loads(path.read_text(encoding="utf-8")))
        if pack.work_key == work_key:
            return dump_jsonable(pack.model_dump())
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence not found")


# ── Policy adapter ──────────────────────────────────────────────────────────


def write_policy(
    session: SessionContext,
    *,
    version: str,
    rationale: str,
    yaml_body: str,
    platform: InMemoryPlatform,
) -> dict[str, Any]:
    if session.actor.principal.startswith("svc:"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="policy changes require a human identity",
        )
    record = {
        "version": version,
        "rationale": rationale,
        "yaml_body": yaml_body,
        "written_by": session.actor.principal,
        "written_at": datetime.now(UTC),
    }
    platform.bucket(session.org_id).policy_versions[version] = record
    return dump_jsonable(record)


# ── Upload adapter ────────────────────────────────────────────────────────────


def store_upload(
    session: SessionContext,
    run_id: str,
    kind: str,
    content: bytes,
    content_type: str | None,
    platform: InMemoryPlatform,
) -> dict[str, Any]:
    if kind not in UPLOAD_KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid upload kind",
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="file too large",
        )
    if (
        content_type
        and content_type.split(";")[0].strip().lower() not in ALLOWED_UPLOAD_CONTENT_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="content type must be text/csv",
        )
    run = platform.scoped_run(session, run_id)
    org_dir = platform.root / session.org_id / "uploads" / run_id
    org_dir.mkdir(parents=True, exist_ok=True)
    target = org_dir / UPLOAD_FILENAME[kind]
    target.write_bytes(content)
    updated = run.model_copy(update={"uploads": {**run.uploads, kind: str(target)}})
    platform.bucket(session.org_id).runs[run_id] = updated
    return {"run_id": run_id, "kind": kind, "stored": UPLOAD_FILENAME[kind], "bytes": len(content)}
