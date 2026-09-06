"""Tests for adjudication contract, controller-ready escalation, and AS 2401 self-check.

Asserts:
1. AdjudicatedVerdict schema has NO amount field; passing an amount raises ValidationError.
2. ControllerEscalation carries all required fields (what broke, dollar impact as Decimal,
   tripped policy threshold with version, candidate explanations with pros/cons citing source rows,
   recommended treatment with confidence, and the single specific question).
3. AMBIGUOUS_MATCH produces the exact question:
   'two candidates, both inside tolerance -- here is what distinguishes them; which is it?'
   NOT 'could not match'.
4. MISSING_BANK_SETTLEMENT produces the exact question:
   'the batch settled but no credit landed -- is this a timing break or a genuine short-settlement?'
5. AS 2401 paragraph .61 check trips on round numbers, suspense accounts, post-close timing.
6. Decision memory bounded lift promotes borderline T2 to T1, but NEVER to T0, and NEVER rescues T3.
7. Zero-LLM fallback completes with no model/API key and never raises.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tieout.gate.decide import decide
from tieout.gate.tiers import Action, GatePolicy, Tier
from tieout.ingest.money import Money
from tieout.ingest.schema import LedgerEntry, ProcessorEvent, SourceRowRef, WorkItem
from tieout.match.adjudicate import (
    AdjudicatedVerdict,
    CandidateExplanation,
    PriorDecisionRecord,
    adjudicate_residual,
    apply_decision_memory_precedent,
    check_proposed_entry_as2401,
    draft_controller_escalation,
    generate_specific_question,
)
from tieout.match.features import FeatureVector, ResultScope, compute_features
from tieout.policy.redflags import ProposedJournalEntry


def _make_sample_work_item(
    order_key: str = "ORD-TEST-001",
    amount: str = "150.00",
    candidate_count: int = 2,
    outcome: str = "AMBIGUOUS_MATCH",
) -> WorkItem:
    """Create a sample work item with source row references."""
    ledgers = [
        LedgerEntry(
            id=f"leg_{order_key}",
            order_key=order_key,
            occurred_at=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
            amount=Money(Decimal(amount), "USD"),
            currency="USD",
            status="CAPTURED",
            method="card",
            source_row_ref=SourceRowRef(file="internal_transactions.csv", row_number=42),
        )
    ]
    procs = []
    for i in range(candidate_count):
        procs.append(
            ProcessorEvent(
                id=f"proc_{order_key}_{i}",
                order_key=order_key,
                event_type="CAPTURE",
                event_time=datetime(2026, 1, 15, 10, 5 + i, tzinfo=UTC),
                gross=Money(Decimal(amount), "USD"),
                fee=Money(Decimal("4.65"), "USD"),
                net=Money(Decimal("145.35"), "USD"),
                batch_key="BATCH-001",
                status="SETTLED",
                source_row_ref=SourceRowRef(file="processor_settlements.csv", row_number=100 + i),
            )
        )
    return WorkItem(work_key=order_key, ledger=ledgers, processor=procs, bank=[])


# --- 1. AdjudicatedVerdict Contract Tests -------------------------------------


def test_adjudicated_verdict_schema_valid():
    """AdjudicatedVerdict instantiates cleanly with allowed structured fields."""
    verdict = AdjudicatedVerdict(
        outcome_class="MATCHED",
        reason_code="L1_EXACT_MATCH",
        confidence=0.98,
        rationale="Exact join on order_key and amount matches",
        cited_row_refs=("internal_transactions.csv:42", "processor_settlements.csv:100"),
    )
    assert verdict.outcome_class == "MATCHED"
    assert verdict.reason_code == "L1_EXACT_MATCH"
    assert verdict.confidence == 0.98
    assert len(verdict.cited_row_refs) == 2


def test_adjudicated_verdict_rejects_amount():
    """AdjudicatedVerdict has NO amount field; returning one raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AdjudicatedVerdict(
            outcome_class="MATCHED",
            reason_code="L1_EXACT_MATCH",
            confidence=0.98,
            rationale="Attempting to supply an amount",
            amount=Decimal("150.00"),  # type: ignore[call-arg]
        )
    assert "extra_forbidden" in str(exc_info.value) or "amount" in str(exc_info.value)


def test_adjudicated_verdict_rejects_out_of_bounds_confidence():
    """Confidence must be between 0.0 and 1.0."""
    with pytest.raises(ValidationError):
        AdjudicatedVerdict(
            outcome_class="MATCHED",
            reason_code="L1_EXACT_MATCH",
            confidence=1.5,
            rationale="Too confident",
        )
    with pytest.raises(ValidationError):
        AdjudicatedVerdict(
            outcome_class="MATCHED",
            reason_code="L1_EXACT_MATCH",
            confidence=-0.1,
            rationale="Negative confidence",
        )


# --- 2. Controller-Ready Escalation Tests -------------------------------------


def test_ambiguous_match_controller_question():
    """For AMBIGUOUS_MATCH, the question must be the exact human-judgement question."""
    q = generate_specific_question("AMBIGUOUS_MATCH", candidate_count=2)
    expected = (
        "two candidates, both inside tolerance -- here is what distinguishes them; which is it?"
    )
    assert q == expected
    assert "could not match" not in q.lower()


def test_missing_bank_settlement_controller_question():
    """For MISSING_BANK_SETTLEMENT, the question must be the timing vs short-settlement question."""
    q = generate_specific_question("MISSING_BANK_SETTLEMENT")
    expected = (
        "the batch settled but no credit landed -- "
        "is this a timing break or a genuine short-settlement?"
    )
    assert q == expected


def test_draft_controller_escalation_structure():
    """ControllerEscalation contains all required fields with accounting domain depth."""
    item = _make_sample_work_item(candidate_count=2)
    features = compute_features(item)
    verdict = AdjudicatedVerdict(
        outcome_class="AMBIGUOUS_MATCH",
        reason_code="L2_TWO_CANDIDATES_WITHIN_TOLERANCE",
        confidence=0.40,
        rationale="Two competing processor captures found",
        cited_row_refs=("internal_transactions.csv:42",),
    )

    policy = GatePolicy(
        version="2026.01-r3",
        clearly_trivial=Decimal("5.00"),
        performance_materiality=Decimal("500.00"),
        auto_min_confidence=0.95,
        auto_sampled_min_confidence=0.90,
        escalate_min_confidence=0.60,
        sample_rate=0.05,
    )

    escalation = draft_controller_escalation(item, verdict, features, policy=policy)

    # 1. What broke in one sentence of accounting language
    assert "Reconciliation blocked for ORD-TEST-001" in escalation.what_broke
    assert "competing transactions" in escalation.what_broke
    assert "Invariant I3" in escalation.what_broke

    # 2. Dollar impact is Decimal
    assert isinstance(escalation.dollar_impact, Decimal)

    # 3. Tripped policy threshold naming the version
    assert "2026.01-r3" in escalation.policy_version
    assert "clearly-trivial" in escalation.policy_threshold

    # 4. Candidate explanations each with evidence for/against citing source rows
    assert len(escalation.candidate_explanations) >= 2
    for exp in escalation.candidate_explanations:
        assert isinstance(exp, CandidateExplanation)
        assert len(exp.evidence_for) > 0
        assert len(exp.evidence_against) > 0

    # 5. Recommended treatment and confidence
    assert "Refuse automated posting" in escalation.recommended_treatment
    assert escalation.confidence == 0.40

    # 6. Single specific question
    assert (
        escalation.specific_question
        == "two candidates, both inside tolerance -- here is what distinguishes them; which is it?"
    )


def test_controller_escalation_missing_bank_settlement():
    """Drafting escalation for missing bank settlement includes specific treasury guidance."""
    proc = ProcessorEvent(
        id="proc_payout_1",
        order_key="ORD-PAYOUT-1",
        event_type="CAPTURE",
        event_time=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        gross=Money(Decimal("1200.00"), "USD"),
        fee=Money(Decimal("35.10"), "USD"),
        net=Money(Decimal("1164.90"), "USD"),
        batch_key="BATCH-SETTLE-88",
        status="SETTLED",
        source_row_ref=SourceRowRef(file="processor_settlements.csv", row_number=88),
    )
    item = WorkItem(work_key="BATCH-SETTLE-88", ledger=[], processor=[proc], bank=[])
    features = FeatureVector(
        scope=ResultScope.SETTLEMENT,
        amount_delta=Decimal("1164.90"),
        candidate_count=0,
        batch_completeness=Decimal("1.00"),
        date_delta_days=5,
    )
    verdict = AdjudicatedVerdict(
        outcome_class="MISSING_BANK_SETTLEMENT",
        reason_code="L3_UNMATCHED_SETTLEMENT",
        confidence=0.30,
        rationale="No bank credit received for batch",
    )

    policy = GatePolicy(
        version="2026.01-r3",
        clearly_trivial=Decimal("5.00"),
        performance_materiality=Decimal("500.00"),
        auto_min_confidence=0.95,
        auto_sampled_min_confidence=0.90,
        escalate_min_confidence=0.60,
        sample_rate=0.05,
    )

    escalation = draft_controller_escalation(item, verdict, features, policy=policy)

    expected_q = (
        "the batch settled but no credit landed -- "
        "is this a timing break or a genuine short-settlement?"
    )
    assert escalation.specific_question == expected_q
    assert escalation.dollar_impact == Decimal("1164.90")
    assert "performance materiality" in escalation.policy_threshold
    assert "treasury" in escalation.recommended_treatment.lower()


# --- 3. PCAOB AS 2401 Fraud-Risk Self-Check Tests -----------------------------


def test_as2401_self_check_clean_entry():
    """Legitimate business entry with odd cents and normal account passes AS 2401 check."""
    entry = ProposedJournalEntry(
        entry_id="JE-001",
        amount=Decimal("143.27"),
        account="1100-cash",
        initiator="svc:tieout-agent@v0.1.0",
        explanation="Automated settlement match for card batch B-01",
        effective_date=date(2026, 1, 15),
    )
    assessment = check_proposed_entry_as2401(entry)
    assert not assessment.has_red_flags
    assert len(assessment.flags) == 0


def test_as2401_self_check_flags_round_number_and_suspense():
    """Forced balancing entry with round amount and suspense account trips AS 2401 red flags."""
    entry = ProposedJournalEntry(
        entry_id="JE-PLUG-001",
        amount=Decimal("1000.00"),  # Round number
        account="9999-suspense-plug",  # Suspense keyword
        initiator="unknown",  # Unusual initiator
        explanation="plug",  # Boilerplate description
        effective_date=date(2026, 1, 31),
        is_post_close=True,  # Post close
    )
    assessment = check_proposed_entry_as2401(entry)
    assert assessment.has_red_flags
    flag_names = assessment.flag_names
    assert "round_number_amount" in flag_names
    assert "seldom_used_account" in flag_names
    assert "post_close_timing" in flag_names
    assert "unusual_initiator" in flag_names
    assert "no_supporting_explanation" in flag_names


# --- 4. Decision Memory Bounded Lift Tests ------------------------------------


class MockMemorySource:
    def __init__(self, record: PriorDecisionRecord | None = None) -> None:
        self.record = record

    def find_similar(
        self, reason_code: str, amount_delta: Decimal, tolerance: Decimal = Decimal("0.05")
    ) -> PriorDecisionRecord | None:
        return self.record


def test_memory_bounded_lift_promotes_borderline_t2_to_t1():
    """Precedent lifts borderline T2 (e.g. 0.86) to T1 (e.g. 0.91), capped below T0."""
    verdict = AdjudicatedVerdict(
        outcome_class="FEE_MISMATCH",
        reason_code="L2_FEE_VARIANCE",
        confidence=0.86,
        rationale="Fee variance inside tolerance",
    )
    feat = FeatureVector(
        scope=ResultScope.ORDER,
        amount_delta=Decimal("0.12"),
        candidate_count=1,
    )
    mock_record = PriorDecisionRecord(
        decision_id="DEC-2026-0042",
        reason_code="L2_FEE_VARIANCE",
        decider="human:controller@acme",
        decided_at="2026-01-10T14:30:00Z",
        outcome_class="FEE_MISMATCH",
        rationale="Approved standard processor tier variance",
        confidence_lift=0.05,
    )
    memory = MockMemorySource(mock_record)
    updated, cited = apply_decision_memory_precedent(verdict, feat, memory)

    assert cited is not None
    assert cited.decision_id == "DEC-2026-0042"
    assert updated.confidence == 0.91
    assert "DEC-2026-0042" in updated.rationale


def test_memory_bound_never_promotes_to_t0():
    """Even with high lift, precedent NEVER promotes to T0 (conf is strictly clamped < 0.95)."""
    verdict = AdjudicatedVerdict(
        outcome_class="AMOUNT_MISMATCH",
        reason_code="L2_TOLERANCE_PASS",
        confidence=0.93,
        rationale="Near auto-post threshold",
    )
    feat = FeatureVector(scope=ResultScope.ORDER, candidate_count=1)
    mock_record = PriorDecisionRecord(
        decision_id="DEC-2026-0099",
        reason_code="L2_TOLERANCE_PASS",
        decider="human:controller@acme",
        decided_at="2026-01-12T10:00:00Z",
        outcome_class="AMOUNT_MISMATCH",
        rationale="Approve rounding delta",
        confidence_lift=0.10,
    )
    memory = MockMemorySource(mock_record)
    policy = GatePolicy(
        version="2026.01-r3",
        clearly_trivial=Decimal("5.00"),
        performance_materiality=Decimal("500.00"),
        auto_min_confidence=0.95,
        auto_sampled_min_confidence=0.90,
        escalate_min_confidence=0.60,
        sample_rate=0.05,
        max_memory_confidence_lift=0.05,
    )
    updated, _ = apply_decision_memory_precedent(verdict, feat, memory, policy=policy)
    # T0 requires >= 0.95 and deterministic key match; memory lift cannot exceed 0.94
    assert updated.confidence <= 0.94


def test_memory_bound_never_rescues_t3_refuse():
    """Precedent NEVER rescues an inadmissible class (AMBIGUOUS_MATCH stays refused)."""
    verdict = AdjudicatedVerdict(
        outcome_class="AMBIGUOUS_MATCH",
        reason_code="L2_TWO_CANDIDATES_WITHIN_TOLERANCE",
        confidence=0.88,
        rationale="Ambiguous matches cannot be lifted",
    )
    feat = FeatureVector(scope=ResultScope.ORDER, candidate_count=2)
    mock_record = PriorDecisionRecord(
        decision_id="DEC-2026-0001",
        reason_code="L2_TWO_CANDIDATES_WITHIN_TOLERANCE",
        decider="human:controller@acme",
        decided_at="2026-01-01T00:00:00Z",
        outcome_class="AMBIGUOUS_MATCH",
        rationale="Attempted rescue",
        confidence_lift=0.05,
    )
    memory = MockMemorySource(mock_record)
    updated, cited = apply_decision_memory_precedent(verdict, feat, memory)
    # Stays unchanged; precedent cannot create admissibility (SPEC section 9)
    assert cited is None
    assert updated.confidence == 0.88


# --- 5. Zero-LLM Resilience & Deterministic Fallback ---------------------------


def test_zero_llm_reconcile_completes_without_api_key():
    """Adjudication completes with zero LLM calls and no API key configured."""
    item = _make_sample_work_item(candidate_count=2)
    # Calling adjudicate_residual without model must never raise
    verdict = adjudicate_residual(item)
    assert isinstance(verdict, AdjudicatedVerdict)
    assert verdict.outcome_class == "AMBIGUOUS_MATCH"
    assert verdict.confidence >= 0.0
    assert len(verdict.cited_row_refs) > 0


def test_adjudicated_verdict_runs_through_refusal_gate():
    """An adjudicated verdict passes through gate.decide() without privileged path."""
    item = _make_sample_work_item(candidate_count=2)
    features = compute_features(item)
    adj_verdict = adjudicate_residual(item, features)

    policy = GatePolicy(
        version="2026.01-r3",
        clearly_trivial=Decimal("5.00"),
        performance_materiality=Decimal("500.00"),
        auto_min_confidence=0.95,
        auto_sampled_min_confidence=0.90,
        escalate_min_confidence=0.60,
        sample_rate=0.05,
    )

    # Gate input format
    gate_payload = {
        "work_key": item.work_key,
        "outcome_class": adj_verdict.outcome_class,
        "reason_code": adj_verdict.reason_code,
        "confidence": adj_verdict.confidence,
        "adjudicator": "LLM",
        "features": {
            "amount_delta": features.amount_delta,
            "candidate_count": features.candidate_count,
            "ref_match": features.ref_match.value,
            "batch_completeness": features.batch_completeness,
        },
    }

    disposition = decide(gate_payload, policy)
    # Ambiguous match forces T3 REFUSE by Invariant I3 regardless of adjudicator
    assert disposition.tier == Tier.T3
    assert disposition.action == Action.REFUSE
    assert disposition.blocking is True
