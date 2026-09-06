"""API layer tests — route constraints, org scope, and JSON contracts."""

from __future__ import annotations

import inspect
import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel, ValidationError

from tieout.api.app import app
from tieout.api.deps import (
    InMemoryPlatform,
    SessionContext,
    apply_review,
    attempt_close,
    build_close_report,
    parse_human_identity,
    reset_platform,
)
from tieout.api.schemas import PolicyWriteRequest, ReviewRequest, RunCreateRequest
from tieout.audit.identity import FourEyesViolation
from tieout.gate.decide import Disposition, GateFeatures, GateVerdict
from tieout.gate.invariants import OVERRIDE_PARAMETER_NAMES
from tieout.gate.tiers import Action, Tier
from tieout.post.tools import ABSENT_TOOLS

SESSION_A = SessionContext(org_id="acme", actor=parse_human_identity("controller@acme"))
SESSION_B = SessionContext(org_id="beta", actor=parse_human_identity("manager@beta"))


def _blocking_disposition(work_key: str = "wk_refuse_1") -> Disposition:
    verdict = GateVerdict(
        work_key=work_key,
        outcome_class="AMBIGUOUS_MATCH",
        reason_code="L2_TWO_CANDIDATES_WITHIN_TOLERANCE",
        confidence=0.95,
        adjudicator="DETERMINISTIC",
        features=GateFeatures(
            amount_abs=Decimal("47900.00"),
            candidate_count=2,
            ref_match="EXACT",
            batch_completeness=Decimal("1"),
        ),
    )
    return Disposition(
        verdict=verdict,
        tier=Tier.T3,
        action=Action.REFUSE,
        blocking=True,
        triggers=("L2_TWO_CANDIDATES_WITHIN_TOLERANCE",),
    )


def _clean_disposition(work_key: str = "wk_ok_1") -> Disposition:
    verdict = GateVerdict(
        work_key=work_key,
        outcome_class="MATCHED",
        reason_code="L0_EXACT_MATCH",
        confidence=0.99,
        adjudicator="DETERMINISTIC",
        features=GateFeatures(
            amount_abs=Decimal("100.00"),
            candidate_count=1,
            ref_match="EXACT",
            batch_completeness=Decimal("1"),
        ),
    )
    return Disposition(
        verdict=verdict,
        tier=Tier.T0,
        action=Action.AUTO_POST,
        blocking=False,
    )


@pytest.fixture
def platform(tmp_path: Path) -> InMemoryPlatform:
    return reset_platform(InMemoryPlatform(root=tmp_path / "platform"))


# ── Route introspection ───────────────────────────────────────────────────────


def _all_api_routes() -> list[APIRoute]:
    routes: list[APIRoute] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append(route)
        elif hasattr(route, "routes"):
            for sub in route.routes:
                if isinstance(sub, APIRoute):
                    routes.append(sub)
    return routes


def _all_request_models() -> list[type[BaseModel]]:
    models: list[type[BaseModel]] = []
    for route in _all_api_routes():
        for dependant in route.dependant.body_params:
            if isinstance(dependant.type_, type) and issubclass(dependant.type_, BaseModel):
                models.append(dependant.type_)
    models.extend([ReviewRequest, PolicyWriteRequest, RunCreateRequest])
    return models


def test_no_route_accepts_override_parameters():
    """I4: no handler or request model accepts force/override/skip_gate/ignore_refusals."""
    offenders: list[str] = []
    for route in _all_api_routes():
        for name in inspect.signature(route.endpoint).parameters:
            if name in OVERRIDE_PARAMETER_NAMES:
                offenders.append(f"{route.path} handler param {name}")
    for model in _all_request_models():
        for name in model.model_fields:
            if name in OVERRIDE_PARAMETER_NAMES:
                offenders.append(f"{model.__name__}.{name}")
    assert offenders == []


def test_no_route_posts_free_text_amount():
    """SPEC section 7: posting by amount is unrepresentable over HTTP."""
    forbidden_paths = {"/post", "/journal", "/entries"}
    for route in _all_api_routes():
        assert not any(part in route.path for part in forbidden_paths)
        for model in _all_request_models():
            assert "amount" not in model.model_fields
    for name in ABSENT_TOOLS:
        if "amount" in name or "adjusting" in name:
            assert not any(name.replace("_", "-") in r.path for r in _all_api_routes())


def test_no_ground_truth_route():
    for route in _all_api_routes():
        assert "ground-truth" not in route.path
        assert "expected_reconciliation" not in route.path


def test_app_starts():
    """The FastAPI app imports and exposes routes."""
    assert app.title == "Tieout API"
    paths = set(app.openapi()["paths"])
    assert "/close" in paths
    assert "/scoreboard" in paths


# ── Close gate ────────────────────────────────────────────────────────────────


def test_close_with_open_refuse_returns_refused(platform: InMemoryPlatform):
    platform.bucket("acme").dispositions.append(_blocking_disposition())
    report = build_close_report("acme", "2026-01", platform)
    assert report["state"] == "CLOSE REFUSED"
    assert report["refused"] is True
    assert len(report["blocking"]) >= 1

    with pytest.raises(Exception) as exc:
        attempt_close(SESSION_A, "2026-01", platform)
    assert getattr(exc.value, "status_code", None) == 409


def test_close_succeeds_without_blocking(platform: InMemoryPlatform):
    platform.bucket("acme").dispositions.append(_clean_disposition())
    report = attempt_close(SESSION_A, "2026-01", platform)
    assert report["state"] == "CLOSED"


# ── Review / four-eyes ────────────────────────────────────────────────────────


def test_review_request_requires_identity():
    with pytest.raises(ValidationError):
        ReviewRequest(action="approve", identity="", initiator="manager@acme")


def test_four_eyes_rejects_same_approver(platform: InMemoryPlatform):
    platform.bucket("acme").queue.append(
        {"work_key": "wk_refuse_1", "blocking": True, "materiality": "47900.00"}
    )
    with pytest.raises(Exception) as exc:
        apply_review(
            SESSION_A,
            "wk_refuse_1",
            action="approve",
            initiator="controller@acme",
            note="self",
            reclassify_to=None,
            platform=platform,
        )
    assert getattr(exc.value, "status_code", None) == 422
    assert "four-eyes" in str(exc.value.detail).lower()


def test_review_accepts_distinct_approver(platform: InMemoryPlatform):
    platform.bucket("acme").queue.append(
        {"work_key": "wk_refuse_1", "blocking": True, "materiality": "47900.00"}
    )
    record = apply_review(
        SESSION_A,
        "wk_refuse_1",
        action="approve",
        initiator="manager@acme",
        note="reviewed",
        reclassify_to=None,
        platform=platform,
    )
    assert record["reviewer"] == "human:controller@acme"


def test_four_eyes_at_identity_layer():
    from datetime import UTC, datetime

    from tieout.audit.identity import Approval

    with pytest.raises(FourEyesViolation):
        Approval(
            initiator=SESSION_A.actor,
            approver=SESSION_A.actor,
            at=datetime.now(UTC),
        )


# ── Money serialisation ───────────────────────────────────────────────────────


def test_money_fields_are_strings_not_floats(platform: InMemoryPlatform):
    platform.bucket("acme").dispositions.append(_blocking_disposition())
    body = build_close_report("acme", "2026-01", platform)
    text = json.dumps(body)
    assert isinstance(body["blocking_total"], str)
    assert isinstance(body["straight_through_rate"], str)
    for tier in body["tiers"].values():
        assert isinstance(tier["dollars"], str)
    parsed = json.loads(text)
    for value in parsed["tiers"].values():
        assert not isinstance(value["dollars"], float)


# ── Org scoping ───────────────────────────────────────────────────────────────


def test_org_a_cannot_read_org_b_run(platform: InMemoryPlatform):
    run = platform.create_run("beta", "2026-02")
    with pytest.raises(Exception) as exc:
        platform.scoped_run(SESSION_A, run.run_id)
    assert getattr(exc.value, "status_code", None) == 404


def test_org_a_cannot_review_org_b_queue_item(platform: InMemoryPlatform):
    platform.bucket("beta").queue.append({"work_key": "wk_beta_only", "blocking": True})
    with pytest.raises(Exception) as exc:
        apply_review(
            SESSION_A,
            "wk_beta_only",
            action="approve",
            initiator="manager@beta",
            note="cross-org",
            reclassify_to=None,
            platform=platform,
        )
    assert getattr(exc.value, "status_code", None) == 404


# ── Runs ──────────────────────────────────────────────────────────────────────


def test_create_and_list_runs(platform: InMemoryPlatform):
    run = platform.create_run("acme", "2026-01")
    runs = platform.list_runs("acme")
    assert any(r.run_id == run.run_id for r in runs)
