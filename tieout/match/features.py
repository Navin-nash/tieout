"""Deterministic feature computation — SPEC section 3 & 5.3.

Derives FeatureVector deterministically. No LLM output enters this struct.
No float touches any amount field.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from tieout.ingest.manifest import FeePolicy
from tieout.ingest.money import compute_fee
from tieout.ingest.schema import WorkItem
from tieout.obs import trace_span, traced

FROZEN = ConfigDict(frozen=True, strict=True, arbitrary_types_allowed=True)

DEFAULT_FEE_PCT = Decimal("0.0290")
DEFAULT_FEE_FIXED = Decimal("0.30")


class RefMatch(StrEnum):
    EXACT = "EXACT"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


class ResultScope(StrEnum):
    ORDER = "ORDER"
    SETTLEMENT = "SETTLEMENT"


class FeatureVector(BaseModel):
    """Deterministic, auditable feature vector per WorkItem."""

    model_config = FROZEN

    scope: ResultScope
    amount_delta: Decimal = Decimal("0.00")
    date_delta_days: int = 0
    ref_match: RefMatch = RefMatch.NONE
    fee_explained_delta: bool = False
    currency_mismatch: bool = False
    candidate_count: int = 0
    batch_completeness: Decimal = Decimal("1.00")
    # Deterministic refund indicators
    is_refund: bool = False
    is_partial_refund: bool = False
    is_full_refund: bool = False


@traced("features")
def compute_features(
    work_item: WorkItem,
    *,
    fee_policy: FeePolicy | None = None,
) -> FeatureVector:
    """Compute deterministic FeatureVector for an order or settlement WorkItem."""
    with trace_span("features", work_key=work_item.work_key):
        pct = fee_policy.percentage_rate if fee_policy else DEFAULT_FEE_PCT
        fixed = fee_policy.fixed_charge if fee_policy else DEFAULT_FEE_FIXED

        # Determine scope
        is_settlement = bool(
            work_item.bank
            or (
                not work_item.ledger
                and work_item.processor
                and all(p.batch_key == work_item.work_key for p in work_item.processor)
            )
        )
        if is_settlement:
            return _compute_settlement_features(work_item)
        return _compute_order_features(work_item, pct=pct, fixed=fixed)


def _compute_order_features(
    work_item: WorkItem,
    *,
    pct: Decimal,
    fixed: Decimal,
) -> FeatureVector:
    ledgers = work_item.ledger
    procs = work_item.processor

    candidate_count = len(procs)
    if not ledgers:
        # MISSING_INTERNAL
        return FeatureVector(
            scope=ResultScope.ORDER,
            amount_delta=Decimal("0.00"),
            date_delta_days=0,
            ref_match=RefMatch.NONE,
            fee_explained_delta=False,
            currency_mismatch=False,
            candidate_count=candidate_count,
            batch_completeness=Decimal("0.00"),
        )

    ledger_entry = ledgers[0]
    if not procs:
        # MISSING_PROCESSOR
        return FeatureVector(
            scope=ResultScope.ORDER,
            amount_delta=ledger_entry.amount.amount,
            date_delta_days=0,
            ref_match=RefMatch.NONE,
            fee_explained_delta=False,
            currency_mismatch=False,
            candidate_count=0,
            batch_completeness=Decimal("0.00"),
        )

    # Check for multiple capture candidates vs refund events
    captures = [p for p in procs if p.event_type == "CAPTURE"]
    refunds = [p for p in procs if p.event_type == "REFUND"]

    # If multiple captures, this is an ambiguous candidate situation
    if len(captures) >= 2:
        curr_mismatch = any(c.gross.currency != ledger_entry.currency for c in captures)
        first_cap = captures[0]
        amt_delta = abs(ledger_entry.amount.amount - first_cap.gross.amount)
        date_delta = abs((first_cap.event_time.date() - ledger_entry.occurred_at.date()).days)
        ref_match = (
            RefMatch.EXACT if first_cap.order_key == ledger_entry.order_key else RefMatch.PARTIAL
        )
        return FeatureVector(
            scope=ResultScope.ORDER,
            amount_delta=amt_delta,
            date_delta_days=date_delta,
            ref_match=ref_match,
            fee_explained_delta=False,
            currency_mismatch=curr_mismatch,
            candidate_count=len(captures),
            batch_completeness=Decimal("1.00"),
        )

    # Single capture (or capture + refund)
    primary_proc = captures[0] if captures else procs[0]
    curr_mismatch = primary_proc.gross.currency != ledger_entry.currency
    amt_delta = abs(ledger_entry.amount.amount - primary_proc.gross.amount)
    date_delta = abs((primary_proc.event_time.date() - ledger_entry.occurred_at.date()).days)

    ref_match = RefMatch.NONE
    if primary_proc.order_key == ledger_entry.order_key:
        ref_match = RefMatch.EXACT
    elif primary_proc.order_key.startswith("SYNTH-ORDER") and ledger_entry.order_key.startswith(
        "SYNTH-ORDER"
    ):
        ref_match = RefMatch.PARTIAL

    # Fee check
    fee_mismatch = False
    if not curr_mismatch and amt_delta == Decimal("0.00"):
        expected_fee = compute_fee(ledger_entry.amount, pct, fixed)
        if primary_proc.fee.amount != expected_fee.amount:
            fee_mismatch = True

    # Refund analysis
    is_refund = len(refunds) > 0
    is_partial_refund = False
    is_full_refund = False
    if is_refund:
        ref_event = refunds[0]
        if abs(ref_event.gross.amount) == primary_proc.gross.amount:
            is_full_refund = True
        elif abs(ref_event.gross.amount) < primary_proc.gross.amount:
            is_partial_refund = True

    return FeatureVector(
        scope=ResultScope.ORDER,
        amount_delta=amt_delta,
        date_delta_days=date_delta,
        ref_match=ref_match,
        fee_explained_delta=fee_mismatch,
        currency_mismatch=curr_mismatch,
        candidate_count=1 if not is_refund else len(procs),
        batch_completeness=Decimal("1.00"),
        is_refund=is_refund,
        is_partial_refund=is_partial_refund,
        is_full_refund=is_full_refund,
    )


def _compute_settlement_features(work_item: WorkItem) -> FeatureVector:
    procs = work_item.processor
    banks = work_item.bank

    if not procs:
        # Bank entry with no processor batch
        b = banks[0]
        return FeatureVector(
            scope=ResultScope.SETTLEMENT,
            amount_delta=b.credited.amount,
            date_delta_days=0,
            ref_match=RefMatch.NONE,
            fee_explained_delta=False,
            currency_mismatch=False,
            candidate_count=0,
            batch_completeness=Decimal("0.00"),
        )

    if not banks:
        # MISSING_BANK_SETTLEMENT
        net_sum = sum((p.net.amount for p in procs), Decimal("0.00"))
        return FeatureVector(
            scope=ResultScope.SETTLEMENT,
            amount_delta=net_sum,
            date_delta_days=0,
            ref_match=RefMatch.NONE,
            fee_explained_delta=False,
            currency_mismatch=False,
            candidate_count=len(procs),
            batch_completeness=Decimal("0.00"),
        )

    bank_entry = banks[0]
    p_currencies = {p.net.currency for p in procs}
    curr_mismatch = (len(p_currencies) > 1) or (bank_entry.credited.currency not in p_currencies)

    net_sum = sum((p.net.amount for p in procs), Decimal("0.00"))
    amt_delta = abs(bank_entry.credited.amount - net_sum)

    # Date delta: days between latest processor event in batch and bank booked_at
    latest_proc_time = max(p.event_time for p in procs)
    date_delta_days = (bank_entry.booked_at.date() - latest_proc_time.date()).days

    ref_match = RefMatch.EXACT if bank_entry.batch_key == procs[0].batch_key else RefMatch.NONE

    # Batch completeness
    if bank_entry.credited.amount > Decimal("0.00"):
        completeness = (net_sum / bank_entry.credited.amount).quantize(Decimal("0.01"))
    else:
        completeness = Decimal("1.00") if amt_delta == Decimal("0.00") else Decimal("0.00")

    return FeatureVector(
        scope=ResultScope.SETTLEMENT,
        amount_delta=amt_delta,
        date_delta_days=date_delta_days,
        ref_match=ref_match,
        fee_explained_delta=False,
        currency_mismatch=curr_mismatch,
        candidate_count=len(procs),
        batch_completeness=completeness,
    )
