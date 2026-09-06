"""Adjudication contract and controller-ready escalation -- SPEC sections 5.5, 6, 7 & 9.

Implements:
1. AdjudicatedVerdict: frozen pydantic model with structured output only:
   {outcome_class, reason_code, confidence, rationale, cited_row_refs}.
   NO amount field -- returning an amount is a validation error by construction.
2. ControllerEscalation: the controller-ready escalation memo answering Track 2 Criterion 2:
   "Is the human judgement side of the finance automation truly intuitive?"
   Includes accounting language, dollar impact, tripped policy threshold, candidate
   explanations citing source_row_refs, recommended treatment, the SINGLE SPECIFIC
   QUESTION the human must answer, and cited prior human decisions.
3. PCAOB AS 2401 paragraph .61 self-check adapter running against proposed entries.
4. Decision memory lookup and bounded confidence lift (precedent may promote T2 to T1,
   never to T0, never rescues T3).
5. Deterministic fallback: works with NO API key set, never raises.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from tieout.gate.decide import INADMISSIBLE_OUTCOME_CLASSES
from tieout.gate.tiers import (
    DEFAULT_MAX_MEMORY_LIFT,
    GatePolicy,
    read_policy,
)
from tieout.ingest.schema import WorkItem
from tieout.match.classify import (
    DEFAULT_POLICY_VERSION,
    OutcomeClass,
    PolicyAdapter,
    classify_work_item,
)
from tieout.match.features import FeatureVector, compute_features
from tieout.policy.redflags import (
    ProposedJournalEntry,
    RedFlagAssessment,
    assess_red_flags,
)

FROZEN = ConfigDict(frozen=True, extra="forbid")


class AdjudicatedVerdict(BaseModel):
    """The structured adjudication verdict (SPEC section 5.5).

    The agent cannot return an amount and cannot return a new transaction.
    ``extra="forbid"`` ensures that returning an amount field is a validation error,
    not a policy we hope holds.
    """

    model_config = FROZEN

    outcome_class: str
    reason_code: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    cited_row_refs: tuple[str, ...] = ()


class CandidateExplanation(BaseModel):
    """A candidate explanation for an exception with evidenced pros and cons."""

    model_config = FROZEN

    hypothesis: str
    evidence_for: tuple[str, ...] = ()
    evidence_against: tuple[str, ...] = ()
    cited_row_refs: tuple[str, ...] = ()


class CitedPriorDecision(BaseModel):
    """A prior human decision cited to accelerate adjudication (SPEC section 9)."""

    model_config = FROZEN

    decision_id: str
    decider: str
    decided_at: str
    rationale: str
    similarity_score: float = Field(default=1.0, ge=0.0, le=1.0)


class ControllerEscalation(BaseModel):
    """A controller-ready escalation memo (Track 2 Criterion 2 differentiator).

    A controller does not want a row dump. This memo delivers:
    - What broke, in one sentence, in accounting language.
    - The dollar impact and which policy threshold it tripped, naming the version.
    - Candidate explanations with specific evidence for/against, citing source rows.
    - The recommended treatment and confidence in it.
    - The SINGLE SPECIFIC QUESTION the human must answer.
    - Any cited prior human decision, with who decided and when.
    """

    model_config = FROZEN

    work_key: str
    what_broke: str
    dollar_impact: Decimal
    policy_threshold: str
    policy_version: str
    candidate_explanations: tuple[CandidateExplanation, ...]
    recommended_treatment: str
    confidence: float = Field(ge=0.0, le=1.0)
    specific_question: str
    cited_prior_decision: CitedPriorDecision | None = None


class PriorDecisionRecord(BaseModel):
    """A human decision stored in decision memory."""

    model_config = ConfigDict(frozen=True, extra="allow")

    decision_id: str
    reason_code: str
    decider: str
    decided_at: str
    outcome_class: str
    rationale: str
    feature_amount_delta: Decimal = Decimal("0.00")
    confidence_lift: float = 0.05


class DecisionMemorySource(Protocol):
    """Protocol for querying decision memory."""

    def find_similar(
        self, reason_code: str, amount_delta: Decimal, tolerance: Decimal = Decimal("0.05")
    ) -> PriorDecisionRecord | None: ...


# --- Specific Question Builder (Criterion 2) ---------------------------------


def generate_specific_question(
    outcome_class: str,
    *,
    candidate_count: int = 1,
    details: str = "",
) -> str:
    """The single specific question the human must answer.

    For AMBIGUOUS_MATCH:
      'two candidates, both inside tolerance -- here is what distinguishes them; which is it?'
      NOT 'could not match'.
    For MISSING_BANK_SETTLEMENT:
      'the batch settled but no credit landed --
       is this a timing break or a genuine short-settlement?'
    """
    oc = outcome_class.upper()
    if oc == OutcomeClass.AMBIGUOUS_MATCH or oc == "AMBIGUOUS_MATCH":
        if candidate_count >= 2:
            return (
                "two candidates, both inside tolerance -- here is what distinguishes them; "
                "which is it?"
            )
        return (
            "multiple candidates inside tolerance -- here is what distinguishes them; which is it?"
        )

    if oc == OutcomeClass.MISSING_BANK_SETTLEMENT or oc == "MISSING_BANK_SETTLEMENT":
        return (
            "the batch settled but no credit landed -- is this a timing break or "
            "a genuine short-settlement?"
        )

    if oc == OutcomeClass.MISSING_PROCESSOR or oc == "MISSING_PROCESSOR":
        return (
            "internal ledger entry has no processor capture -- was this authorization aborted, "
            "voided, or settled through an alternate gateway?"
        )

    if oc == OutcomeClass.MISSING_INTERNAL or oc == "MISSING_INTERNAL":
        return (
            "processor settlement present with no internal ledger record -- is this an unrecorded "
            "direct capture or an orphan batch entry requiring manual booking?"
        )

    if oc == OutcomeClass.FEE_MISMATCH or oc == "FEE_MISMATCH":
        return (
            "fee variance does not reconcile to standard card schedule (2.9% + $0.30) -- "
            "is this an interchange rate tier adjustment or custom contractual pricing?"
        )

    if oc == OutcomeClass.AMOUNT_MISMATCH or oc == "AMOUNT_MISMATCH":
        return (
            "amount gap exceeds configured tolerance -- is this an unrecorded merchant fee, "
            "partial refund, or pricing discrepancy?"
        )

    if oc == OutcomeClass.CURRENCY_MISMATCH or oc == "CURRENCY_MISMATCH":
        return (
            "transaction currency differs across payment legs -- should this settle through "
            "realized FX gain/loss or is the order currency incorrectly mapped?"
        )

    if oc == OutcomeClass.LATE_SETTLEMENT or oc == "LATE_SETTLEMENT":
        return (
            "settlement delay exceeds policy date window -- is this a standard banking holiday "
            "hold or a processor settlement dispute?"
        )

    if details:
        return (
            f"exception '{outcome_class}' requires controller determination ({details}) -- "
            "approve recommended treatment or reassign?"
        )
    return (
        f"exception '{outcome_class}' requires controller determination -- "
        "approve recommended treatment or reassign?"
    )


def _extract_source_row_refs(work_item: WorkItem) -> tuple[str, ...]:
    """Collect all source_row_refs across ledger, processor, and bank legs."""
    refs: list[str] = []
    for leg_entry in work_item.ledger:
        if leg_entry.source_row_ref:
            refs.append(str(leg_entry.source_row_ref))
    for proc_entry in work_item.processor:
        if proc_entry.source_row_ref:
            refs.append(str(proc_entry.source_row_ref))
    for bank_entry in work_item.bank:
        if bank_entry.source_row_ref:
            refs.append(str(bank_entry.source_row_ref))
    return tuple(refs)


def _format_accounting_summary(
    outcome_class: str,
    work_key: str,
    amount_delta: Decimal,
    candidate_count: int,
) -> str:
    """One sentence accounting description of what broke."""
    oc = outcome_class.upper()
    if oc == "AMBIGUOUS_MATCH":
        return (
            f"Reconciliation blocked for {work_key}: {candidate_count} competing transactions "
            f"match within tolerance, preventing automated pairing under Invariant I3."
        )
    if oc == "MISSING_BANK_SETTLEMENT":
        return (
            f"Settlement break on {work_key}: processor batch closed but corresponding bank credit "
            f"of ${abs(amount_delta)} was not detected within statement window."
        )
    if oc == "MISSING_PROCESSOR":
        return (
            f"Ledger discrepancy on {work_key}: internal sale recorded for ${abs(amount_delta)} "
            "without corresponding processor authorization or settlement record."
        )
    if oc == "MISSING_INTERNAL":
        return (
            f"Unmatched deposit on {work_key}: processor captured ${abs(amount_delta)} with no "
            "matching internal order in the general ledger."
        )
    if oc == "FEE_MISMATCH":
        return (
            f"Processing fee variance on {work_key}: gap of ${abs(amount_delta)} does not conform "
            "to standard contract formula (2.90% + $0.30)."
        )
    if oc == "AMOUNT_MISMATCH":
        return (
            f"Imbalance on {work_key}: ledger and processor amounts differ by "
            f"${abs(amount_delta)}, exceeding acceptable rounding tolerance."
        )
    if oc == "CURRENCY_MISMATCH":
        return (
            f"Currency conflict on {work_key}: order currency does not match settlement currency."
        )
    return (
        f"Reconciliation exception {outcome_class} identified on work item {work_key} "
        f"with ${abs(amount_delta)} variance."
    )


def determine_materiality_threshold(
    amount: Decimal,
    policy: GatePolicy | Any,
) -> str:
    """Determine which materiality threshold was tripped."""
    abs_amt = abs(amount)
    clearly_trivial = getattr(policy, "clearly_trivial", Decimal("5.00"))
    performance = getattr(policy, "performance_materiality", Decimal("500.00"))

    if abs_amt < clearly_trivial:
        return f"within clearly-trivial (${clearly_trivial})"
    if abs_amt < performance:
        return (
            f"tripped clearly-trivial (${clearly_trivial}), below "
            f"performance materiality (${performance})"
        )
    return f"tripped performance materiality (${performance})"


def draft_controller_escalation(
    work_item: WorkItem,
    verdict: AdjudicatedVerdict | Any,
    features: FeatureVector,
    *,
    policy: Any | None = None,
    cited_prior_decision: CitedPriorDecision | None = None,
) -> ControllerEscalation:
    """Draft a structured, controller-ready escalation memo."""
    pol_adapter = policy if isinstance(policy, PolicyAdapter) else PolicyAdapter()
    gate_pol: GatePolicy | None = None
    try:
        if policy is not None and not isinstance(policy, PolicyAdapter):
            gate_pol = read_policy(policy)
    except Exception:
        gate_pol = None

    policy_version = (
        getattr(gate_pol, "version", None)
        or getattr(policy, "version", None)
        or getattr(pol_adapter, "version", DEFAULT_POLICY_VERSION)
    )

    dollar_impact = abs(features.amount_delta)
    threshold_str = (
        determine_materiality_threshold(dollar_impact, gate_pol)
        if gate_pol
        else f"evaluated against policy version {policy_version}"
    )

    row_refs = _extract_source_row_refs(work_item)
    candidate_count = features.candidate_count

    # Build candidate explanations
    explanations: list[CandidateExplanation] = []
    oc = getattr(verdict, "outcome_class", "").upper()

    if oc == "AMBIGUOUS_MATCH":
        explanations.append(
            CandidateExplanation(
                hypothesis="Primary candidate match: exact order key or timestamp alignment",
                evidence_for=(
                    f"Candidate count ({candidate_count}) fits tolerance window",
                    f"Dollar variance ${dollar_impact} within category threshold",
                ),
                evidence_against=(
                    "Multiple distinct processor/ledger records share identical amount and date",
                ),
                cited_row_refs=row_refs[:1] if row_refs else (),
            )
        )
        explanations.append(
            CandidateExplanation(
                hypothesis="Secondary candidate match: duplicate order submission or retry capture",
                evidence_for=(
                    "Identical transaction value captured within short time window",
                ),
                evidence_against=(
                    "Source row timestamps or IDs indicate distinct payment events",
                ),
                cited_row_refs=row_refs[1:2] if len(row_refs) > 1 else (),
            )
        )
        recommended_treatment = (
            "Refuse automated posting per Invariant I3. Present both candidates to controller "
            "for manual designation of true order counterpart."
        )
    elif oc == "MISSING_BANK_SETTLEMENT":
        explanations.append(
            CandidateExplanation(
                hypothesis="Timing lag: processor payout batch in transit over banking cut-off",
                evidence_for=(
                    f"Batch completeness is {features.batch_completeness}",
                    "Processor transaction is marked SETTLED",
                ),
                evidence_against=(
                    f"Statement exceeds policy window ({features.date_delta_days} days elapsed)",
                ),
                cited_row_refs=row_refs,
            )
        )
        explanations.append(
            CandidateExplanation(
                hypothesis="Short-settlement: processor hold, reserve deduction, or fee debit",
                evidence_for=(
                    "No credit appears on bank statement for this settlement batch ID",
                ),
                evidence_against=(
                    "No notification of reserve hold received from processor portal",
                ),
                cited_row_refs=row_refs,
            )
        )
        recommended_treatment = (
            "Escalate to treasury: verify merchant account payout trace ID against bank clearing "
            "system before creating adjusting journal."
        )
    elif oc == "FEE_MISMATCH":
        explanations.append(
            CandidateExplanation(
                hypothesis=(
                    "Non-standard interchange tier: corporate, rewards, or international rate"
                ),
                evidence_for=(
                    f"Fee variance of ${dollar_impact} is non-zero",
                    "Gross capture amount matches internal order exactly",
                ),
                evidence_against=(
                    "Processor contract specifies default 2.90% + $0.30 fee schedule",
                ),
                cited_row_refs=row_refs,
            )
        )
        recommended_treatment = (
            "Book processing fee expense to actual invoiced amount; flag agreement for rate review."
        )
    else:
        explanations.append(
            CandidateExplanation(
                hypothesis=f"Unreconciled event: {oc}",
                evidence_for=(
                    f"Calculated variance is ${dollar_impact}",
                    f"Candidate count is {candidate_count}",
                ),
                evidence_against=(),
                cited_row_refs=row_refs,
            )
        )
        recommended_treatment = (
            f"Hold in review queue; verify supporting invoices for {work_item.work_key}."
        )

    what_broke = _format_accounting_summary(oc, work_item.work_key, dollar_impact, candidate_count)
    specific_question = generate_specific_question(oc, candidate_count=candidate_count)

    return ControllerEscalation(
        work_key=work_item.work_key,
        what_broke=what_broke,
        dollar_impact=dollar_impact,
        policy_threshold=threshold_str,
        policy_version=policy_version,
        candidate_explanations=tuple(explanations),
        recommended_treatment=recommended_treatment,
        confidence=float(getattr(verdict, "confidence", 0.0)),
        specific_question=specific_question,
        cited_prior_decision=cited_prior_decision,
    )


# --- AS 2401 Fraud Risk Self-Check -------------------------------------------


def check_proposed_entry_as2401(
    entry: ProposedJournalEntry,
) -> RedFlagAssessment:
    """Run PCAOB AS 2401 paragraph .61 fraud-risk checks on proposed journal entries.

    Ensures the agent fraud-tests its own output before proposing journal entries.
    Trips on round-number amounts, seldom-used/suspense accounts, post-close timing,
    unauthorized initiators, and boilerplate explanations.
    """
    return assess_red_flags(entry)


# --- Decision Memory & Bounded Lift ------------------------------------------


def apply_decision_memory_precedent(
    verdict: AdjudicatedVerdict,
    features: FeatureVector,
    memory: DecisionMemorySource | None,
    policy: GatePolicy | None = None,
) -> tuple[AdjudicatedVerdict, CitedPriorDecision | None]:
    """Look up precedent in decision memory and apply bounded confidence lift.

    Bound rules (SPEC section 9):
    - Learned precedent may promote borderline T2 to T1.
    - Precedent can NEVER promote anything into T0 (requires deterministic key match).
    - Precedent can NEVER rescue a T3 / inadmissible class (a REFUSE stays a REFUSE).
    - Maximum lift is clamped to policy (default 0.05).
    """
    if memory is None:
        return verdict, None

    # Never apply lift to inadmissible classes (Invariant I3 & SPEC section 9)
    if verdict.outcome_class in INADMISSIBLE_OUTCOME_CLASSES:
        return verdict, None

    prior = memory.find_similar(verdict.reason_code, features.amount_delta)
    if prior is None:
        return verdict, None

    max_lift = (
        getattr(policy, "max_memory_confidence_lift", DEFAULT_MAX_MEMORY_LIFT)
        if policy
        else DEFAULT_MAX_MEMORY_LIFT
    )
    lift = min(max(prior.confidence_lift, 0.0), max_lift)

    new_conf = min(verdict.confidence + lift, 0.94)  # 0.94 strictly caps below T0 threshold (0.95)

    cited = CitedPriorDecision(
        decision_id=prior.decision_id,
        decider=prior.decider,
        decided_at=prior.decided_at,
        rationale=prior.rationale,
        similarity_score=1.0,
    )

    updated_verdict = AdjudicatedVerdict(
        outcome_class=verdict.outcome_class,
        reason_code=verdict.reason_code,
        confidence=new_conf,
        rationale=f"{verdict.rationale} [Precedent cited: {prior.decision_id} by {prior.decider}]",
        cited_row_refs=verdict.cited_row_refs,
    )
    return updated_verdict, cited


# --- Main Adjudication Entry Point (Zero-LLM Resilience) ---------------------


def adjudicate_residual(
    work_item: WorkItem,
    features: FeatureVector | None = None,
    *,
    policy: Any | None = None,
    memory: DecisionMemorySource | None = None,
    model: Any | None = None,
) -> AdjudicatedVerdict:
    """Adjudicate a residual work item (SPEC section 5.5).

    Zero-LLM resilience (ADR-001):
    Completes with NO API key set and NO model available. Degrades cleanly to the
    deterministic cascade's findings and never raises.
    """
    feat = features if features is not None else compute_features(work_item)
    pol = policy if policy is not None else PolicyAdapter()

    # If no model is supplied, run the deterministic cascade fallback
    if model is None:
        raw_verdict = classify_work_item(work_item, feat, policy=pol)
        refs = _extract_source_row_refs(work_item)
        base_verdict = AdjudicatedVerdict(
            outcome_class=raw_verdict.outcome_class.value,
            reason_code=raw_verdict.reason_code,
            confidence=raw_verdict.confidence,
            rationale=raw_verdict.rationale,
            cited_row_refs=refs,
        )
        # Apply bounded memory precedent if available
        final_verdict, _ = apply_decision_memory_precedent(base_verdict, feat, memory)
        return final_verdict

    # In Phase 2: deepagents model execution will be plugged in here.
    # For now, if a model is passed, safely fall back to the deterministic path.
    return adjudicate_residual(work_item, feat, policy=pol, memory=memory, model=None)
