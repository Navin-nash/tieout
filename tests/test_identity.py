"""SPEC section 14: test_four_eyes_enforced, plus the service-vs-human identity separation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from tieout.audit.identity import (
    Approval,
    DecisionTimestamps,
    FourEyesViolation,
    HumanIdentity,
    ServiceIdentity,
    principal_of,
    to_utc_iso,
    utc_now,
)

AGENT = ServiceIdentity(name="tieout-agent", version="v0.3.1")
CONTROLLER = HumanIdentity(user="controller", org="acme")
MANAGER = HumanIdentity(user="manager", org="acme")
AT = datetime(2026, 9, 6, 4, 12, 9, tzinfo=UTC)


# ── distinct actors ───────────────────────────────────────────────────────────


def test_principals_render_as_the_spec_says():
    assert AGENT.principal == "svc:tieout-agent@v0.3.1"
    assert CONTROLLER.principal == "human:controller@acme"
    assert principal_of(AGENT) == AGENT.principal


def test_service_identity_is_per_version_not_a_shared_account():
    assert AGENT.principal != ServiceIdentity(name="tieout-agent", version="v0.4.0").principal


def test_identities_are_frozen():
    with pytest.raises(ValidationError):
        AGENT.name = "someone-else"


def test_a_service_identity_cannot_be_a_human_approver():
    """The substitution is a mypy error and a runtime ValidationError. Not a shared string."""
    with pytest.raises(ValidationError):
        Approval(initiator=CONTROLLER, approver=AGENT, at=AT)


def test_a_human_cannot_be_passed_as_a_service_identity():
    with pytest.raises(ValidationError):
        ServiceIdentity(user="controller", org="acme")


# ── four eyes ─────────────────────────────────────────────────────────────────


def test_four_eyes_enforced():
    """SPEC section 14: approver_id == initiator_id is rejected at write time."""
    with pytest.raises(FourEyesViolation, match="four-eyes violation"):
        Approval(initiator=CONTROLLER, approver=CONTROLLER, at=AT)


def test_four_eyes_rejects_a_re_created_equal_identity():
    """Equality is on the principal, not on object identity."""
    twin = HumanIdentity(user="controller", org="acme")
    with pytest.raises(FourEyesViolation):
        Approval(initiator=CONTROLLER, approver=twin, at=AT)


def test_a_distinct_approver_is_accepted():
    approval = Approval(initiator=AGENT, approver=CONTROLLER, at=AT, note="reviewed the pack")
    assert approval.approver.principal == "human:controller@acme"
    assert approval.initiator.principal == "svc:tieout-agent@v0.3.1"


def test_approval_is_immutable_once_written():
    approval = Approval(initiator=AGENT, approver=CONTROLLER, at=AT)
    with pytest.raises(ValidationError):
        approval.approver = MANAGER


# ── timestamps ────────────────────────────────────────────────────────────────


def test_timestamps_are_utc_iso_8601():
    times = DecisionTimestamps(
        created_at=AT,
        reviewed_at=AT + timedelta(minutes=30),
        posted_at=AT + timedelta(hours=1),
    )
    assert times.as_iso() == {
        "created_at": "2026-09-06T04:12:09.000000Z",
        "reviewed_at": "2026-09-06T04:42:09.000000Z",
        "posted_at": "2026-09-06T05:12:09.000000Z",
    }


def test_local_time_is_never_admissible():
    with pytest.raises(ValueError, match="naive datetime"):
        DecisionTimestamps(created_at=datetime(2026, 9, 6, 4, 12, 9))  # noqa: DTZ001
    with pytest.raises(ValueError, match="naive datetime"):
        to_utc_iso(datetime(2026, 9, 6, 4, 12, 9))  # noqa: DTZ001


def test_an_offset_timestamp_is_normalised_to_utc():
    ist = timezone(timedelta(hours=5, minutes=30))
    times = DecisionTimestamps(created_at=datetime(2026, 9, 6, 9, 42, 9, tzinfo=ist))
    assert times.as_iso()["created_at"] == "2026-09-06T04:12:09.000000Z"


def test_review_cannot_precede_creation():
    with pytest.raises(ValueError, match="reviewed_at precedes created_at"):
        DecisionTimestamps(created_at=AT, reviewed_at=AT - timedelta(seconds=1))


def test_posting_cannot_precede_review():
    with pytest.raises(ValueError, match="posted_at precedes reviewed_at"):
        DecisionTimestamps(
            created_at=AT,
            reviewed_at=AT + timedelta(minutes=5),
            posted_at=AT + timedelta(minutes=1),
        )


def test_utc_now_is_aware():
    assert utc_now().tzinfo is not None
