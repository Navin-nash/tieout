"""Tests for policy schema, validation, provenance, immutability, and version resolution.

Enforces AS 2105, SAB 99 provenance requirements, and SPEC section 14 invariant tests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from tieout.policy.loader import (
    PolicyError,
    PolicyRefusal,
    load_policy,
    require_fee_policy,
    require_write_off_authority,
    resolve_for_date,
    resolve_for_period,
)
from tieout.policy.schema import (
    Aging,
    ConfidenceTier,
    ConfidenceTiers,
    Materiality,
    Policy,
    Threshold,
    Tolerance,
)


@pytest.fixture
def valid_threshold_data() -> dict:
    return {
        "value": Decimal("750000.00"),
        "basis": "0.5% of planning revenue",
        "set_by": "controller@acme",
        "set_at": datetime(2026, 1, 2, 9, 14, tzinfo=UTC),
        "rationale": "FY26 planning revenue $150M; conservative end of 0.5-7% band",
    }


@pytest.fixture
def valid_materiality() -> Materiality:
    ts = datetime(2026, 1, 2, 9, 14, tzinfo=UTC)
    return Materiality(
        overall=Threshold(
            value=Decimal("750000.00"),
            basis="0.5% of revenue",
            set_by="controller@acme",
            set_at=ts,
            rationale="FY26 planning revenue $150M",
        ),
        performance=Threshold(
            value=Decimal("450000.00"),
            basis="60% of overall",
            set_by="controller@acme",
            set_at=ts,
            rationale="Aggregation risk across entities",
        ),
        clearly_trivial=Threshold(
            value=Decimal("30000.00"),
            basis="4% of overall",
            set_by="controller@acme",
            set_at=ts,
            rationale="Trivial accumulation floor",
        ),
    )


@pytest.fixture
def sample_policy(valid_materiality: Materiality) -> Policy:
    return Policy(
        version="2026.01-r3",
        effective_from=date(2026, 1, 1),
        entity="ACME-US",
        illustrative=True,
        materiality=valid_materiality,
        tolerances=(
            Tolerance(
                category="card_settlement",
                amount_abs=Decimal("0.02"),
                amount_pct=Decimal("0.0005"),
                date_window_days=3,
                rationale="Processor rounding + T+2 settlement",
            ),
            Tolerance(
                category="wire",
                amount_abs=Decimal("0.00"),
                date_window_days=1,
            ),
        ),
        confidence_tiers=ConfidenceTiers(
            auto=ConfidenceTier(min_confidence=Decimal("0.95"), max_amount="clearly_trivial"),
            auto_sampled=ConfidenceTier(
                min_confidence=Decimal("0.90"),
                max_amount="performance",
                sample_rate=Decimal("0.05"),
            ),
            escalate=ConfidenceTier(min_confidence=Decimal("0.60")),
        ),
        qualitative_overrides=(
            "crosses_covenant_threshold",
            "changes_sign_income_to_loss",
            "related_party_counterparty",
            "masks_trend_reversal",
            "affects_management_compensation",
            "conceals_unlawful_transaction",
        ),
        je_red_flags=(
            "round_number_amount",
            "seldom_used_account",
            "post_close_timing",
            "unusual_initiator",
            "no_supporting_explanation",
        ),
        aging=Aging(
            reconcile_within_working_days=30,
            suspense_resolve_within_days=60,
            escalate_to_controller_after_days=30,
            buckets=(30, 60, 90, 120),
        ),
    )


# --- Provenance & Validation Tests --------------------------------------------------------


def test_threshold_requires_all_provenance_fields():
    """SAB 99: every threshold must carry full provenance."""
    ts = datetime(2026, 1, 2, 9, 14, tzinfo=UTC)
    # Missing basis
    with pytest.raises(ValidationError):
        Threshold(
            value=Decimal("100.00"),
            set_by="user",
            set_at=ts,
            rationale="reason",  # type: ignore[call-arg]
        )

    # Missing set_by
    with pytest.raises(ValidationError):
        Threshold(
            value=Decimal("100.00"),
            basis="basis",
            set_at=ts,
            rationale="reason",  # type: ignore[call-arg]
        )

    # Missing set_at
    with pytest.raises(ValidationError):
        Threshold(
            value=Decimal("100.00"),
            basis="basis",
            set_by="user",
            rationale="reason",  # type: ignore[call-arg]
        )

    # Missing rationale
    with pytest.raises(ValidationError):
        Threshold(
            value=Decimal("100.00"),
            basis="basis",
            set_by="user",
            set_at=ts,  # type: ignore[call-arg]
        )


def test_threshold_rejects_float():
    """Standing rule 3 & SPEC section 14: floats are strictly forbidden for money amounts."""
    ts = datetime(2026, 1, 2, 9, 14, tzinfo=UTC)
    with pytest.raises(ValidationError) as excinfo:
        Threshold(
            value=750000.00,  # type: ignore[arg-type]
            basis="basis",
            set_by="user",
            set_at=ts,
            rationale="reason",
        )
    assert "float is not an acceptable money input" in str(excinfo.value)


def test_threshold_rejects_naive_datetime():
    """Unanchored timestamp is not valid audit evidence."""
    naive_dt = datetime(2026, 1, 2, 9, 14)
    with pytest.raises(ValidationError) as excinfo:
        Threshold(
            value=Decimal("750000.00"),
            basis="basis",
            set_by="user",
            set_at=naive_dt,
            rationale="reason",
        )
    assert "timezone-aware" in str(excinfo.value)


# --- AS 2105 Materiality Sanity Checks ----------------------------------------------------


def test_as2105_overall_materiality_must_be_positive():
    """AS 2105: overall materiality must be a specified positive amount."""
    ts = datetime(2026, 1, 2, 9, 14, tzinfo=UTC)
    with pytest.raises(ValidationError) as excinfo:
        Materiality(
            overall=Threshold(
                value=Decimal("0.00"),
                basis="0%",
                set_by="user",
                set_at=ts,
                rationale="none",
            ),
            performance=Threshold(
                value=Decimal("10.00"),
                basis="basis",
                set_by="user",
                set_at=ts,
                rationale="reason",
            ),
            clearly_trivial=Threshold(
                value=Decimal("1.00"),
                basis="basis",
                set_by="user",
                set_at=ts,
                rationale="reason",
            ),
        )
    assert "AS 2105: overall materiality must be a specified amount greater than zero" in str(
        excinfo.value
    )


def test_as2105_performance_materiality_must_be_strictly_less_than_overall():
    """AS 2105: performance materiality must be strictly less than overall materiality."""
    ts = datetime(2026, 1, 2, 9, 14, tzinfo=UTC)
    # Equality is invalid
    with pytest.raises(ValidationError) as excinfo:
        Materiality(
            overall=Threshold(
                value=Decimal("500000.00"),
                basis="basis",
                set_by="user",
                set_at=ts,
                rationale="reason",
            ),
            performance=Threshold(
                value=Decimal("500000.00"),
                basis="basis",
                set_by="user",
                set_at=ts,
                rationale="reason",
            ),
            clearly_trivial=Threshold(
                value=Decimal("10000.00"),
                basis="basis",
                set_by="user",
                set_at=ts,
                rationale="reason",
            ),
        )
    assert "performance materiality must be strictly less than overall" in str(excinfo.value)

    # Greater than is invalid
    with pytest.raises(ValidationError) as excinfo:
        Materiality(
            overall=Threshold(
                value=Decimal("500000.00"),
                basis="basis",
                set_by="user",
                set_at=ts,
                rationale="reason",
            ),
            performance=Threshold(
                value=Decimal("600000.00"),
                basis="basis",
                set_by="user",
                set_at=ts,
                rationale="reason",
            ),
            clearly_trivial=Threshold(
                value=Decimal("10000.00"),
                basis="basis",
                set_by="user",
                set_at=ts,
                rationale="reason",
            ),
        )
    assert "performance materiality must be strictly less than overall" in str(excinfo.value)


def test_clearly_trivial_must_be_below_performance():
    """Clearly trivial must be positive and below performance materiality."""
    ts = datetime(2026, 1, 2, 9, 14, tzinfo=UTC)
    with pytest.raises(ValidationError) as excinfo:
        Materiality(
            overall=Threshold(
                value=Decimal("500000.00"),
                basis="basis",
                set_by="user",
                set_at=ts,
                rationale="reason",
            ),
            performance=Threshold(
                value=Decimal("300000.00"),
                basis="basis",
                set_by="user",
                set_at=ts,
                rationale="reason",
            ),
            clearly_trivial=Threshold(
                value=Decimal("350000.00"),
                basis="basis",
                set_by="user",
                set_at=ts,
                rationale="reason",
            ),
        )
    assert "clearly-trivial must be greater than zero and below performance" in str(excinfo.value)


# --- SPEC Section 14: test_agent_cannot_mutate_policy -------------------------------------


def test_agent_cannot_mutate_policy(sample_policy: Policy):
    """SPEC section 14: Policy objects are frozen; the agent's tool surface exposes no setter."""
    # Direct field assignment fails
    with pytest.raises(ValidationError):
        sample_policy.version = "2026.02"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        sample_policy.entity = "OTHER"  # type: ignore[misc]

    # Nested objects are also frozen
    with pytest.raises(ValidationError):
        sample_policy.materiality.overall = sample_policy.materiality.performance  # type: ignore[misc]

    # No mutating methods exist
    assert not hasattr(sample_policy, "set_threshold")
    assert not hasattr(sample_policy, "update_threshold")
    assert not hasattr(sample_policy, "set_materiality")
    assert not hasattr(sample_policy, "with_threshold")


# --- Negative Research Finding: Write-Off Authority ---------------------------------------


def test_write_off_authority_has_no_default_and_refuses(sample_policy: Policy):
    """SPEC section 10: write-off authority has NO default value and refuses until set."""
    assert sample_policy.write_off_authority is None

    with pytest.raises(PolicyRefusal) as excinfo:
        require_write_off_authority(sample_policy)
    assert "sets no write-off authority, and this system ships no default" in str(excinfo.value)


def test_fee_policy_refusal_when_unresolved(sample_policy: Policy):
    """SPEC section 19: fee policy refuses if manifest was not found."""
    assert sample_policy.fee_policy is None

    with pytest.raises(PolicyRefusal) as excinfo:
        require_fee_policy(sample_policy)
    assert "fee policy is unresolved" in str(excinfo.value)


# --- Version Resolution Tests -------------------------------------------------------------


def test_policy_version_resolution_by_date(valid_materiality: Materiality, sample_policy: Policy):
    """Version resolution resolves the policy in force for a given date."""
    p1 = sample_policy.model_copy(
        update={"version": "2025.01", "effective_from": date(2025, 1, 1), "supersedes": None}
    )
    p2 = sample_policy.model_copy(
        update={"version": "2026.01", "effective_from": date(2026, 1, 1), "supersedes": "2025.01"}
    )
    p3 = sample_policy.model_copy(
        update={"version": "2026.07", "effective_from": date(2026, 7, 1), "supersedes": "2026.01"}
    )

    policies = (p1, p2, p3)

    # Date in 2025
    assert resolve_for_date(policies, date(2025, 6, 15)).version == "2025.01"
    # Exact start date of 2026.01
    assert resolve_for_date(policies, date(2026, 1, 1)).version == "2026.01"
    # Date before 2026.07
    assert resolve_for_date(policies, date(2026, 6, 30)).version == "2026.01"
    # Date after 2026.07
    assert resolve_for_date(policies, date(2026, 8, 1)).version == "2026.07"


def test_policy_version_resolution_by_period(sample_policy: Policy):
    """Period resolution resolves to policy in effect on the 1st of the period."""
    p1 = sample_policy.model_copy(
        update={"version": "2025.01", "effective_from": date(2025, 1, 1), "supersedes": None}
    )
    p2 = sample_policy.model_copy(
        update={"version": "2026.01", "effective_from": date(2026, 1, 1), "supersedes": "2025.01"}
    )
    policies = (p1, p2)

    assert resolve_for_period(policies, "2025-12").version == "2025.01"
    assert resolve_for_period(policies, "2026-01").version == "2026.01"
    assert resolve_for_period(policies, "2026-06").version == "2026.01"


def test_policy_resolution_fails_on_broken_supersedes_chain(sample_policy: Policy):
    p1 = sample_policy.model_copy(
        update={
            "version": "2026.01",
            "effective_from": date(2026, 1, 1),
            "supersedes": "NONEXISTENT",
        }
    )
    with pytest.raises(PolicyError) as excinfo:
        resolve_for_date((p1,), date(2026, 1, 1))
    assert "supersedes 'NONEXISTENT', which is not in this set" in str(excinfo.value)


# --- Load Real policy.yaml Test -----------------------------------------------------------


def test_load_real_policy_yaml():
    """Verify repo-root policy.yaml parses and satisfies all AS 2105 rules."""
    policy = load_policy(Path("policy.yaml"))
    assert policy.version == "2026.01-r3"
    assert policy.entity == "ACME-US"
    assert policy.illustrative is True
    assert policy.materiality.overall.value == Decimal("750000.00")
    assert policy.materiality.performance.value == Decimal("450000.00")
    assert policy.materiality.clearly_trivial.value == Decimal("30000.00")
    assert len(policy.tolerances) >= 3
    assert policy.tolerance_for("card_settlement") is not None
    assert policy.tolerance_for("wire") is not None
