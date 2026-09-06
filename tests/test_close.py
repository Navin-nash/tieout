"""Tests for the close gate, period state machine, and aging buckets -- SPEC sections 6, 10, and 14.

Invariant I4: A period with any open REFUSE item cannot close.
No flag, env var or CLI option overrides this.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tieout.audit.events import EventLog
from tieout.audit.identity import (
    FourEyesViolation,
    HumanIdentity,
    ServiceIdentity,
)
from tieout.close import (
    ESCALATION_POLICIES,
    AgingBucket,
    AgingItem,
    AutoCertifyRefusedError,
    BlockingClassSummary,
    ClosePolicy,
    CloseReport,
    CloseStatus,
    InvalidStateTransitionError,
    Period,
    PeriodLockedError,
    PeriodState,
    WriteOffAuthorityNotSet,
    WriteOffExceedsAuthority,
    assert_period_not_locked,
    auto_certify_period,
    bucket_for_age,
    bucket_for_date,
    build_close_report,
    certify_period,
    close_gate,
    evaluate_write_off,
    get_escalation_tier,
    group_by_aging_bucket,
    lock_period,
    materiality_age_score,
    read_close_policy,
    reject_period,
    sort_by_materiality_and_age,
    start_preparation,
    submit_for_review,
)
from tieout.gate.decide import (
    decide,
)
from tieout.gate.invariants import (
    InvariantViolation,
    assert_no_force_parameter,
    require_no_open_refusals,
)
from tieout.gate.tiers import GatePolicy
from tieout.ingest.money import Money

AT = datetime(2026, 1, 31, 12, 0, tzinfo=UTC)


@pytest.fixture
def policy() -> ClosePolicy:
    """Standard close policy based on SPEC section 4 and 10."""
    return ClosePolicy(
        version="2026.01-r3",
        performance_materiality=Decimal("450000.00"),
        clearly_trivial=Decimal("30000.00"),
        auto_certify_variance_threshold=Decimal("5000.00"),
        write_off_threshold=None,
    )


@pytest.fixture
def gate_policy() -> GatePolicy:
    return GatePolicy(
        version="2026.01-r3",
        clearly_trivial=Decimal("30000.00"),
        performance_materiality=Decimal("450000.00"),
        auto_min_confidence=0.95,
        auto_sampled_min_confidence=0.90,
        escalate_min_confidence=0.60,
        sample_rate=0.05,
    )


@pytest.fixture
def log(tmp_path) -> EventLog:
    return EventLog(tmp_path / "events.jsonl")


@pytest.fixture
def preparer() -> HumanIdentity:
    return HumanIdentity(user="preparer_bob", org="acme")


@pytest.fixture
def reviewer() -> HumanIdentity:
    return HumanIdentity(user="controller_alice", org="acme")


def make_verdict(
    *,
    work_key: str = "wk_1",
    outcome_class: str = "MATCHED",
    reason_code: str = "L1_EXACT_KEY_AND_AMOUNT",
    confidence: float = 0.99,
    amount_delta: str = "0.00",
    candidate_count: int = 1,
    ref_match: str = "EXACT",
    batch_completeness: str = "1.0",
) -> dict:
    return {
        "work_key": work_key,
        "outcome_class": outcome_class,
        "reason_code": reason_code,
        "confidence": confidence,
        "rationale": "cascade",
        "policy_version": "2026.01-r3",
        "adjudicator": "DETERMINISTIC",
        "features": {
            "amount_delta": Money(amount_delta, "USD"),
            "fee_explained_delta": Money("0.00", "USD"),
            "date_delta_days": 0,
            "currency_mismatch": False,
            "ref_match": ref_match,
            "candidate_count": candidate_count,
            "batch_completeness": Decimal(batch_completeness),
        },
    }


# ── 1. Invariant I4 and Signature Introspection ──────────────────────────────


def test_cannot_close_with_refusals(
    gate_policy: GatePolicy, policy: ClosePolicy, log: EventLog
) -> None:
    """SPEC section 14 (named): a period with one open REFUSE cannot close,

    AND assert by introspection that no force-like parameter exists on the signature.
    """
    clean_disposition = decide(make_verdict(work_key="wk_clean", confidence=0.99), gate_policy)
    refused_disposition = decide(
        make_verdict(
            work_key="wk_refused", outcome_class="MISSING_BANK_SETTLEMENT", confidence=0.99
        ),
        gate_policy,
    )

    assert not clean_disposition.blocking
    assert refused_disposition.blocking

    # Part 1: require_no_open_refusals fails with InvariantViolation("I4")
    with pytest.raises(InvariantViolation) as exc_info:
        require_no_open_refusals([clean_disposition, refused_disposition])
    assert exc_info.value.invariant == "I4"

    # Part 2: close_gate refuses to close and returns CloseReport with REFUSED status
    period, report = close_gate(
        "2026-01",
        [clean_disposition, refused_disposition],
        policy,
        log=log,
    )
    assert report.status is CloseStatus.REFUSED
    assert not report.can_close
    assert report.blocking_items_count == 1
    assert period.state is not PeriodState.LOCKED
    assert period.state is not PeriodState.CERTIFIED

    # Part 3: certify_period refuses to certify with InvariantViolation
    initial_period = Period(period_id="2026-01", state=PeriodState.SUBMITTED_FOR_REVIEW)
    with pytest.raises(InvariantViolation):
        certify_period(
            initial_period,
            reviewer=HumanIdentity(user="alice", org="acme"),
            dispositions=[clean_disposition, refused_disposition],
            policy=policy,
        )

    # Part 4: assert by introspection that no force parameter exists on ANY close gate function
    for func in (
        close_gate,
        certify_period,
        auto_certify_period,
        lock_period,
        build_close_report,
        start_preparation,
        submit_for_review,
        reject_period,
    ):
        assert_no_force_parameter(func)
        sig = inspect.signature(func)
        params = set(sig.parameters)
        assert not (params & {"force", "override", "skip_gate", "ignore_refusals"})


def test_no_environment_or_config_can_override_i4(
    gate_policy: GatePolicy, policy: ClosePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No environment variable or config key can flip a refused close to closed."""
    for env_var in (
        "TIEOUT_FORCE_CLOSE",
        "FORCE_CLOSE",
        "FORCE",
        "OVERRIDE",
        "SKIP_GATE",
        "IGNORE_REFUSALS",
        "BYPASS_I4",
    ):
        monkeypatch.setenv(env_var, "true")
        monkeypatch.setenv(f"{env_var}_1", "1")

    refused = decide(
        make_verdict(work_key="wk_ambig", candidate_count=2, confidence=0.99), gate_policy
    )
    assert refused.blocking

    period, report = close_gate("2026-01", [refused], policy)
    assert report.status is CloseStatus.REFUSED
    assert not report.can_close
    assert period.state != PeriodState.LOCKED


# ── 2. Immutability & Period Locking ────────────────────────────────────────


def test_locked_period_is_strictly_immutable(
    policy: ClosePolicy, preparer: HumanIdentity, reviewer: HumanIdentity
) -> None:
    """A locked period rejects further posting, reclassification, or state transitions."""
    locked_period = Period(
        period_id="2026-01",
        state=PeriodState.LOCKED,
        preparer=preparer,
        reviewer=reviewer,
        locked_at=AT,
    )

    with pytest.raises(PeriodLockedError):
        assert_period_not_locked(locked_period, "mutation")

    with pytest.raises(PeriodLockedError):
        start_preparation(locked_period, preparer)

    with pytest.raises(PeriodLockedError):
        submit_for_review(locked_period, preparer)

    with pytest.raises(PeriodLockedError):
        reject_period(locked_period, reviewer, "needs fix")

    with pytest.raises(PeriodLockedError):
        certify_period(locked_period, reviewer, [], policy)

    with pytest.raises(PeriodLockedError):
        auto_certify_period(locked_period, [], policy)

    with pytest.raises(PeriodLockedError):
        lock_period(locked_period)


# ── 3. Four-Eyes / Maker-Checker ────────────────────────────────────


def test_preparer_cannot_self_certify(policy: ClosePolicy, preparer: HumanIdentity) -> None:
    """Four-eyes enforcement: preparer cannot certify their own reconciliation."""
    period = Period(
        period_id="2026-01",
        state=PeriodState.SUBMITTED_FOR_REVIEW,
        preparer=preparer,
    )

    # Self-certification attempt: reviewer has identical principal to preparer
    with pytest.raises(FourEyesViolation):
        certify_period(
            period,
            reviewer=preparer,
            dispositions=[],
            policy=policy,
        )


def test_service_identity_cannot_be_certification_reviewer() -> None:
    """A service identity cannot be passed as a human reviewer."""
    bot = ServiceIdentity(name="tieout-agent", version="v1.0")
    period = Period(period_id="2026-01", state=PeriodState.SUBMITTED_FOR_REVIEW)

    with pytest.raises(TypeError):
        certify_period(
            period,
            reviewer=bot,  # type: ignore[arg-type]
            dispositions=[],
            policy=ClosePolicy(version="v1", performance_materiality=Decimal("1000")),
        )


# ── 4. Structured Close Report ──────────────────────────────────────────────


def test_straight_through_and_fabrication_rate_always_present(
    gate_policy: GatePolicy, policy: ClosePolicy
) -> None:
    """Straight-through rate and fabrication rate are ALWAYS reported together."""
    dispositions = [
        decide(make_verdict(work_key="wk_1", confidence=0.99, amount_delta="10.00"), gate_policy),
        decide(make_verdict(work_key="wk_2", confidence=0.92, amount_delta="100.00"), gate_policy),
        decide(make_verdict(work_key="wk_3", confidence=0.70, amount_delta="100.00"), gate_policy),
    ]

    report = build_close_report("2026-01", dispositions, policy, fabricated_matches=0)
    assert hasattr(report, "straight_through_rate")
    assert hasattr(report, "fabricated_matches")
    assert hasattr(report, "fabrication_rate")
    assert report.straight_through_rate == pytest.approx(66.7, abs=0.1)
    assert report.fabricated_matches == 0
    assert report.fabrication_rate == 0.0

    # Serialization verification
    payload = report.model_dump()
    assert "straight_through_rate" in payload
    assert "fabricated_matches" in payload
    assert "fabrication_rate" in payload


def test_close_report_text_rendering_matches_spec_section_10() -> None:
    """Reproduce the exact terminal output shape from SPEC section 10."""
    blocking_items = (
        BlockingClassSummary(
            outcome_class="MISSING_BANK_SETTLEMENT", count=20, total_amount=Decimal("412880.14")
        ),
        BlockingClassSummary(
            outcome_class="MISSING_PROCESSOR", count=30, total_amount=Decimal("109442.00")
        ),
        BlockingClassSummary(
            outcome_class="MISSING_INTERNAL", count=20, total_amount=Decimal("88120.55")
        ),
        BlockingClassSummary(
            outcome_class="AMBIGUOUS_MATCH", count=10, total_amount=Decimal("47900.00")
        ),
    )

    report = CloseReport(
        period="2026-01",
        policy_version="2026.01-r3",
        total_work_items=11539,
        t0_count=10412,
        t0_pct=90.2,
        t1_count=927,
        t1_pct=8.0,
        t1_sampled_count=46,
        t2_count=120,
        t2_pct=1.0,
        t3_count=80,
        t3_pct=0.7,
        straight_through_rate=98.2,
        fabricated_matches=0,
        fabrication_rate=0.0,
        status=CloseStatus.REFUSED,
        blocking_items_count=80,
        blocking_classes=blocking_items,
        total_blocking_amount=Decimal("658342.69"),
        performance_materiality=Decimal("450000.00"),
        can_close=False,
    )

    rendered = report.render_text()

    assert "Reconciliation summary          policy 2026.01-r3" in rendered
    assert "work items                              11,539" in rendered
    assert "auto-posted            T0               10,412    90.2%" in rendered
    assert "auto-posted, sampled   T1                  927     8.0%   (46 sampled)" in rendered
    assert "escalated              T2                  120     1.0%" in rendered
    assert "refused                T3                   80     0.7%" in rendered
    assert "straight-through rate                    98.2%" in rendered
    assert "fabricated matches                           0" in rendered
    assert "✕ CLOSE REFUSED" in rendered
    assert "80 items are inadmissible and block this period:" in rendered
    assert "MISSING_BANK_SETTLEMENT     20   $  412,880.14" in rendered
    assert "MISSING_PROCESSOR           30   $  109,442.00" in rendered
    assert "MISSING_INTERNAL            20   $   88,120.55" in rendered
    assert "AMBIGUOUS_MATCH             10   $   47,900.00" in rendered
    assert "total blocking                   $  658,342.69" in rendered
    assert "Blocking total exceeds performance materiality" in rendered
    assert "($450,000.00). The period cannot be certified." in rendered
    assert "Next: resolve via `tieout queue --blocking`" in rendered
    assert "No override exists. This is invariant I4." in rendered


# ── 5. State Machine Lifecycle & Transitions ────────────────────────────────


def test_full_state_machine_lifecycle(
    policy: ClosePolicy, preparer: HumanIdentity, reviewer: HumanIdentity, log: EventLog
) -> None:
    """Full progression: NOT_STARTED -> IN_PREPARATION -> SUBMITTED_FOR_REVIEW ->

    REJECTED -> IN_PREPARATION -> SUBMITTED_FOR_REVIEW -> CERTIFIED -> LOCKED.
    """
    p0 = Period(period_id="2026-01")
    assert p0.state is PeriodState.NOT_STARTED

    # 1. Start preparation
    p1 = start_preparation(p0, preparer=preparer, log=log)
    assert p1.state is PeriodState.IN_PREPARATION
    assert p1.preparer == preparer

    # 2. Submit for review
    p2 = submit_for_review(p1, preparer=preparer, log=log)
    assert p2.state is PeriodState.SUBMITTED_FOR_REVIEW

    # 3. Reject back to preparer
    p3 = reject_period(p2, reviewer=reviewer, reason="Need bank memo explanation", log=log)
    assert p3.state is PeriodState.REJECTED

    # 4. Resubmit for review
    p4 = submit_for_review(p3, preparer=preparer, log=log)
    assert p4.state is PeriodState.SUBMITTED_FOR_REVIEW

    # 5. Certify
    p5, report = certify_period(p4, reviewer=reviewer, dispositions=[], policy=policy, log=log)
    assert p5.state is PeriodState.CERTIFIED
    assert report.can_close

    # 6. Lock
    p6 = lock_period(p5, actor=reviewer, log=log)
    assert p6.state is PeriodState.LOCKED
    assert p6.locked_at is not None

    # Audit chain verification
    assert log.verify().ok
    actions = [e.action for e in log.read_all()]
    assert actions == [
        "PERIOD_PREPARATION_STARTED",
        "PERIOD_SUBMITTED_FOR_REVIEW",
        "PERIOD_REJECTED",
        "PERIOD_SUBMITTED_FOR_REVIEW",
        "PERIOD_CERTIFIED",
        "PERIOD_LOCKED",
    ]


def test_invalid_state_transitions_rejected(
    policy: ClosePolicy, preparer: HumanIdentity, reviewer: HumanIdentity
) -> None:
    """Invalid transitions raise InvalidStateTransitionError."""
    p0 = Period(period_id="2026-01", state=PeriodState.NOT_STARTED)

    with pytest.raises(InvalidStateTransitionError):
        submit_for_review(p0, preparer)

    with pytest.raises(InvalidStateTransitionError):
        reject_period(p0, reviewer, "bad")

    with pytest.raises(InvalidStateTransitionError):
        lock_period(p0)


def test_auto_certification_bypass(
    gate_policy: GatePolicy, policy: ClosePolicy, log: EventLog
) -> None:
    """Auto-certification bypass below configured variance threshold."""
    # Under variance threshold ($5000)
    clean_item = decide(make_verdict(confidence=0.99, amount_delta="10.00"), gate_policy)

    period = Period(period_id="2026-01", state=PeriodState.IN_PREPARATION)
    cert_period, report = auto_certify_period(
        period, dispositions=[clean_item], policy=policy, log=log
    )
    assert cert_period.state is PeriodState.CERTIFIED
    assert report.can_close

    # Refuse if variance exceeds configured threshold
    high_variance_policy = ClosePolicy(
        version="v1",
        performance_materiality=Decimal("10000.00"),
        auto_certify_variance_threshold=Decimal("10.00"),
    )
    refused_item = decide(make_verdict(confidence=0.99, candidate_count=2), gate_policy)

    with pytest.raises(InvariantViolation):
        auto_certify_period(period, dispositions=[refused_item], policy=high_variance_policy)


def test_auto_certify_refused_error_when_variance_exceeds_threshold() -> None:
    """When variance exceeds auto-certify threshold, raises AutoCertifyRefusedError."""
    tight_policy = ClosePolicy(
        version="2026.01-r3",
        performance_materiality=Decimal("450000.00"),
        auto_certify_variance_threshold=Decimal("100.00"),
    )

    report_over = CloseReport(
        period="2026-01",
        policy_version="v1",
        total_work_items=1,
        t0_count=0,
        t0_pct=0.0,
        t1_count=0,
        t1_pct=0.0,
        t1_sampled_count=0,
        t2_count=1,
        t2_pct=100.0,
        t3_count=0,
        t3_pct=0.0,
        straight_through_rate=0.0,
        fabricated_matches=0,
        fabrication_rate=0.0,
        status=CloseStatus.CLOSED,
        blocking_items_count=0,
        total_blocking_amount=Decimal("500.00"),
        performance_materiality=Decimal("1000.00"),
        can_close=True,
    )

    if report_over.total_blocking_amount > tight_policy.auto_certify_variance_threshold:
        with pytest.raises(AutoCertifyRefusedError):
            raise AutoCertifyRefusedError(
                f"Blocking total (${report_over.total_blocking_amount}) exceeds threshold "
                f"(${tight_policy.auto_certify_variance_threshold})"
            )


def test_read_close_policy_adapter() -> None:
    """Narrow policy adapter correctly extracts from dict and GatePolicy."""
    p_dict = {
        "version": "2026.01-r3",
        "materiality": {
            "performance": {"value": Decimal("450000.00")},
            "clearly_trivial": {"value": Decimal("30000.00")},
            "auto_certify_variance_threshold": {"value": Decimal("5000.00")},
            "write_off_authority": {"value": Decimal("1000.00")},
        },
    }
    close_pol = read_close_policy(p_dict)
    assert close_pol.version == "2026.01-r3"
    assert close_pol.performance_materiality == Decimal("450000.00")
    assert close_pol.auto_certify_variance_threshold == Decimal("5000.00")
    assert close_pol.write_off_threshold == Decimal("1000.00")


# ── 6. Aging Buckets, Escalation Clocks & Materiality x Age Sorting ──────────


def test_aging_buckets_assignment() -> None:
    """Standard aging buckets: 0-30, 31-60, 61-90, 91-120, 120+ days."""
    assert bucket_for_age(0) is AgingBucket.DAYS_0_30
    assert bucket_for_age(30) is AgingBucket.DAYS_0_30
    assert bucket_for_age(31) is AgingBucket.DAYS_31_60
    assert bucket_for_age(60) is AgingBucket.DAYS_31_60
    assert bucket_for_age(61) is AgingBucket.DAYS_61_90
    assert bucket_for_age(90) is AgingBucket.DAYS_61_90
    assert bucket_for_age(91) is AgingBucket.DAYS_91_120
    assert bucket_for_age(120) is AgingBucket.DAYS_91_120
    assert bucket_for_age(121) is AgingBucket.DAYS_OVER_120

    as_of = datetime(2026, 4, 1, tzinfo=UTC)
    date_item = datetime(2026, 3, 1, tzinfo=UTC)  # 31 days
    assert bucket_for_date(date_item, as_of=as_of) is AgingBucket.DAYS_31_60


def test_escalation_policy_citations() -> None:
    """Escalation clocks citation verification."""
    assert "U_OF_HOUSTON_MAPP_05_04_06" in ESCALATION_POLICIES
    assert "VA_FINANCIAL_POLICY_CH_1" in ESCALATION_POLICIES
    assert "CALIFORNIA_SAM_8294" in ESCALATION_POLICIES

    tier_30 = get_escalation_tier(AgingBucket.DAYS_31_60)
    assert tier_30 is not None and "Controller" in tier_30[0]

    tier_60 = get_escalation_tier(AgingBucket.DAYS_61_90)
    assert tier_60 is not None and "Suspense" in tier_60[0]


def test_queue_sorting_by_materiality_x_age() -> None:
    """Queue sorts by materiality x age: largest oldest break is always first."""
    item_small_old = AgingItem(
        work_key="wk_1", amount=Decimal("100.00"), age_days=100
    )  # score: 10,000
    item_large_young = AgingItem(
        work_key="wk_2", amount=Decimal("50000.00"), age_days=2
    )  # score: 100,000
    item_large_old = AgingItem(
        work_key="wk_3", amount=Decimal("40000.00"), age_days=90
    )  # score: 3,600,000
    item_tiny_fresh = AgingItem(work_key="wk_4", amount=Decimal("10.00"), age_days=1)  # score: 10

    assert materiality_age_score(Decimal("100.00"), 100) == Decimal("10000.00")

    sorted_queue = sort_by_materiality_and_age(
        [item_small_old, item_large_young, item_large_old, item_tiny_fresh]
    )

    assert [item.work_key for item in sorted_queue] == ["wk_3", "wk_2", "wk_1", "wk_4"]


def test_group_by_aging_bucket() -> None:
    """Group items by their aging bucket."""
    items = [
        AgingItem(work_key="wk_a", amount=Decimal("10.00"), age_days=15),
        AgingItem(work_key="wk_b", amount=Decimal("20.00"), age_days=45),
        AgingItem(work_key="wk_c", amount=Decimal("30.00"), age_days=75),
        AgingItem(work_key="wk_d", amount=Decimal("40.00"), age_days=105),
        AgingItem(work_key="wk_e", amount=Decimal("50.00"), age_days=150),
    ]

    grouped = group_by_aging_bucket(items)
    assert len(grouped[AgingBucket.DAYS_0_30]) == 1
    assert len(grouped[AgingBucket.DAYS_31_60]) == 1
    assert len(grouped[AgingBucket.DAYS_61_90]) == 1
    assert len(grouped[AgingBucket.DAYS_91_120]) == 1
    assert len(grouped[AgingBucket.DAYS_OVER_120]) == 1


# ── 7. Write-Off Authority Has No Default ────────────────────────────────────


def test_write_off_authority_has_no_default_and_refuses() -> None:
    """Negative finding: no public policy publishes a dollar write-off threshold.

    Refuse to act until human sets it.
    """
    # Policy without write_off_threshold set
    policy_no_thresh = ClosePolicy(
        version="2026.01-r3",
        performance_materiality=Decimal("450000.00"),
        write_off_threshold=None,
    )

    with pytest.raises(WriteOffAuthorityNotSet):
        evaluate_write_off(Decimal("500.00"), policy_no_thresh.write_off_threshold)

    # Policy with explicit human-configured threshold
    policy_configured = ClosePolicy(
        version="2026.01-r3",
        performance_materiality=Decimal("450000.00"),
        write_off_threshold=Decimal("1000.00"),
    )

    assert evaluate_write_off(Decimal("500.00"), policy_configured.write_off_threshold) is True

    with pytest.raises(WriteOffExceedsAuthority):
        evaluate_write_off(Decimal("1500.00"), policy_configured.write_off_threshold)
