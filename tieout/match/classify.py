"""The 11-class deterministic rule cascade — SPEC section 3 & 5.4.

A cascade ordered most-specific first, emitting outcome class + reason code
+ confidence for all 11 classes. Ambiguity (>=2 candidates within tolerance)
NEVER picks — it emits AMBIGUOUS_MATCH and forces REFUSE.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from tieout.ingest.schema import WorkItem
from tieout.match.features import FeatureVector, ResultScope, compute_features
from tieout.obs import disposition_attrs, trace_span, traced

FROZEN = ConfigDict(frozen=True, strict=True, arbitrary_types_allowed=True)

DEFAULT_POLICY_VERSION = "2026.01-r3"


class OutcomeClass(StrEnum):
    """The 11 outcome classes from ReconRiver / SPEC section 3."""

    MATCHED = "MATCHED"
    REFUND_MATCHED = "REFUND_MATCHED"
    PARTIAL_REFUND = "PARTIAL_REFUND"
    LATE_SETTLEMENT = "LATE_SETTLEMENT"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    FEE_MISMATCH = "FEE_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    MISSING_PROCESSOR = "MISSING_PROCESSOR"
    MISSING_INTERNAL = "MISSING_INTERNAL"
    MISSING_BANK_SETTLEMENT = "MISSING_BANK_SETTLEMENT"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"


class Adjudicator(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"
    HUMAN = "HUMAN"


class CategoryTolerance(BaseModel):
    model_config = FROZEN

    category: str
    amount_abs: Decimal = Decimal("0.02")
    amount_pct: Decimal = Decimal("0.0005")
    date_window_days: int = 3
    rationale: str = ""


class PolicyAdapter:
    """Narrow adapter for policy tolerances per category (SPEC section 4)."""

    def __init__(
        self,
        version: str = DEFAULT_POLICY_VERSION,
        tolerances: dict[str, CategoryTolerance] | None = None,
    ) -> None:
        self.version = version
        self.tolerances = tolerances or {
            "card_settlement": CategoryTolerance(
                category="card_settlement",
                amount_abs=Decimal("0.02"),
                amount_pct=Decimal("0.0005"),
                date_window_days=3,
                rationale="Processor rounding + T+2 settlement",
            ),
            "wire": CategoryTolerance(
                category="wire",
                amount_abs=Decimal("0.00"),
                amount_pct=Decimal("0.00"),
                date_window_days=1,
                rationale="Wires must match to the cent",
            ),
            "fx_settlement": CategoryTolerance(
                category="fx_settlement",
                amount_abs=Decimal("0.00"),
                amount_pct=Decimal("0.005"),
                date_window_days=5,
                rationale="Rate timing between booking and credit",
            ),
        }

    def get_tolerance(self, category: str = "card_settlement") -> CategoryTolerance:
        return self.tolerances.get(
            category,
            CategoryTolerance(category=category, amount_abs=Decimal("0.02"), date_window_days=3),
        )


class Verdict(BaseModel):
    """The canonical output of the classification stage."""

    model_config = FROZEN

    work_key: str
    outcome_class: OutcomeClass
    reason_code: str
    confidence: float
    rationale: str
    features: FeatureVector
    policy_version: str
    adjudicator: Adjudicator = Adjudicator.DETERMINISTIC


@traced("classify")
def classify_work_item(
    work_item: WorkItem,
    features: FeatureVector | None = None,
    *,
    policy: Any | None = None,
    category: str = "card_settlement",
) -> Verdict:
    """Classify a WorkItem via the 11-class rule cascade (most-specific first)."""
    # 1. Resolve policy & tolerance
    if policy is None or not isinstance(policy, PolicyAdapter):
        pol = PolicyAdapter()
    else:
        pol = policy

    tolerance = pol.get_tolerance(category)
    feat = features if features is not None else compute_features(work_item)

    # 2. Most-specific first rule cascade
    verdict = _evaluate_cascade(work_item, feat, tolerance, pol.version)

    # 3. Observability tracing span
    with trace_span(
        "classify",
        **disposition_attrs(
            work_key=verdict.work_key,
            outcome_class=verdict.outcome_class.value,
            reason_code=verdict.reason_code,
            disposition=_typical_disposition(verdict.outcome_class),
            policy_version=verdict.policy_version,
            adjudicator=verdict.adjudicator.value,
        ),
    ):
        pass

    return verdict


def _evaluate_cascade(
    work_item: WorkItem,
    feat: FeatureVector,
    tolerance: CategoryTolerance,
    policy_version: str,
) -> Verdict:
    # Rule 1: AMBIGUOUS_MATCH — Invariant I3: Ambiguity NEVER picks
    if feat.scope == ResultScope.ORDER and feat.candidate_count >= 2 and not feat.is_refund:
        return Verdict(
            work_key=work_item.work_key,
            outcome_class=OutcomeClass.AMBIGUOUS_MATCH,
            reason_code="L2_TWO_CANDIDATES_WITHIN_TOLERANCE",
            confidence=0.00,
            rationale=(
                "Ambiguity detected: 2 or more candidate transactions match order key "
                "within tolerance. Ambiguity never resolves to a pick."
            ),
            features=feat,
            policy_version=policy_version,
            adjudicator=Adjudicator.DETERMINISTIC,
        )

    # Rule 2: MISSING_PROCESSOR
    if feat.scope == ResultScope.ORDER and not work_item.processor:
        return Verdict(
            work_key=work_item.work_key,
            outcome_class=OutcomeClass.MISSING_PROCESSOR,
            reason_code="L2_MISSING_PROCESSOR_EVENT",
            confidence=0.00,
            rationale="Internal ledger entry has no corresponding processor transaction.",
            features=feat,
            policy_version=policy_version,
            adjudicator=Adjudicator.DETERMINISTIC,
        )

    # Rule 3: MISSING_INTERNAL
    if feat.scope == ResultScope.ORDER and not work_item.ledger:
        return Verdict(
            work_key=work_item.work_key,
            outcome_class=OutcomeClass.MISSING_INTERNAL,
            reason_code="L2_MISSING_INTERNAL_LEDGER",
            confidence=0.00,
            rationale=(
                "Processor transaction recorded without a corresponding internal ledger entry."
            ),
            features=feat,
            policy_version=policy_version,
            adjudicator=Adjudicator.DETERMINISTIC,
        )

    # Rule 4: MISSING_BANK_SETTLEMENT
    if feat.scope == ResultScope.SETTLEMENT and not work_item.bank:
        return Verdict(
            work_key=work_item.work_key,
            outcome_class=OutcomeClass.MISSING_BANK_SETTLEMENT,
            reason_code="L2_MISSING_BANK_SETTLEMENT",
            confidence=0.00,
            rationale="Processor settlement batch has no corresponding bank deposit entry.",
            features=feat,
            policy_version=policy_version,
            adjudicator=Adjudicator.DETERMINISTIC,
        )

    # Rule 5: CURRENCY_MISMATCH
    if feat.currency_mismatch:
        return Verdict(
            work_key=work_item.work_key,
            outcome_class=OutcomeClass.CURRENCY_MISMATCH,
            reason_code="L2_CURRENCY_MISMATCH",
            confidence=0.80,
            rationale="Currency mismatch across matched transaction legs.",
            features=feat,
            policy_version=policy_version,
            adjudicator=Adjudicator.DETERMINISTIC,
        )

    # Rule 6: REFUND_MATCHED (Full refund)
    if feat.is_full_refund:
        return Verdict(
            work_key=work_item.work_key,
            outcome_class=OutcomeClass.REFUND_MATCHED,
            reason_code="L2_FULL_REFUND_MATCHED",
            confidence=0.98,
            rationale="Full refund matched exactly to original capture transaction.",
            features=feat,
            policy_version=policy_version,
            adjudicator=Adjudicator.DETERMINISTIC,
        )

    # Rule 7: PARTIAL_REFUND
    if feat.is_partial_refund:
        return Verdict(
            work_key=work_item.work_key,
            outcome_class=OutcomeClass.PARTIAL_REFUND,
            reason_code="L2_PARTIAL_REFUND_MATCHED",
            confidence=0.92,
            rationale="Partial refund transaction matched to original order.",
            features=feat,
            policy_version=policy_version,
            adjudicator=Adjudicator.DETERMINISTIC,
        )

    # Rule 8: FEE_MISMATCH (Fee explained delta)
    if feat.fee_explained_delta:
        return Verdict(
            work_key=work_item.work_key,
            outcome_class=OutcomeClass.FEE_MISMATCH,
            reason_code="L2_FEE_CALCULATION_MISMATCH",
            confidence=0.85,
            rationale="Gross amounts match but processor fee deviates from policy (2.90% + 0.30).",
            features=feat,
            policy_version=policy_version,
            adjudicator=Adjudicator.DETERMINISTIC,
        )

    # Rule 9: AMOUNT_MISMATCH
    if feat.amount_delta > tolerance.amount_abs:
        return Verdict(
            work_key=work_item.work_key,
            outcome_class=OutcomeClass.AMOUNT_MISMATCH,
            reason_code="L2_AMOUNT_MISMATCH_EXCEEDS_TOLERANCE",
            confidence=0.80,
            rationale=(
                f"Amount delta of {feat.amount_delta} exceeds tolerance threshold "
                f"of {tolerance.amount_abs}."
            ),
            features=feat,
            policy_version=policy_version,
            adjudicator=Adjudicator.DETERMINISTIC,
        )

    # Rule 10: LATE_SETTLEMENT
    if feat.scope == ResultScope.SETTLEMENT and feat.date_delta_days > tolerance.date_window_days:
        return Verdict(
            work_key=work_item.work_key,
            outcome_class=OutcomeClass.LATE_SETTLEMENT,
            reason_code="L2_SETTLEMENT_WINDOW_EXCEEDED",
            confidence=0.90,
            rationale=(
                f"Settlement arrived {feat.date_delta_days} days after latest batch transaction, "
                f"exceeding {tolerance.date_window_days} day window."
            ),
            features=feat,
            policy_version=policy_version,
            adjudicator=Adjudicator.DETERMINISTIC,
        )

    # Rule 11: MATCHED
    reason = "L2_EXACT_MATCH" if feat.scope == ResultScope.ORDER else "L2_BATCH_SETTLEMENT_MATCHED"
    return Verdict(
        work_key=work_item.work_key,
        outcome_class=OutcomeClass.MATCHED,
        reason_code=reason,
        confidence=1.00,
        rationale="Record successfully matched within policy tolerances and settlement window.",
        features=feat,
        policy_version=policy_version,
        adjudicator=Adjudicator.DETERMINISTIC,
    )


def _typical_disposition(outcome_class: OutcomeClass) -> str:
    """Map outcome class to typical Refusal Gate disposition for trace logging."""
    if outcome_class in (OutcomeClass.MATCHED, OutcomeClass.REFUND_MATCHED):
        return "AUTO_POST"
    if outcome_class in (OutcomeClass.PARTIAL_REFUND, OutcomeClass.LATE_SETTLEMENT):
        return "AUTO_SAMPLED"
    if outcome_class in (
        OutcomeClass.AMOUNT_MISMATCH,
        OutcomeClass.FEE_MISMATCH,
        OutcomeClass.CURRENCY_MISMATCH,
    ):
        return "ESCALATE"
    return "REFUSE"


def classify_all(
    work_items: list[WorkItem],
    *,
    policy: Any | None = None,
    category: str = "card_settlement",
) -> list[Verdict]:
    """Classify all WorkItems deterministically."""
    return [classify_work_item(wi, policy=policy, category=category) for wi in work_items]
