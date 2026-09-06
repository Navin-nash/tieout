"""Tests for the 11-class rule cascade (SPEC section 14).

Asserts:
- One case per outcome class (all 11 classes).
- Ambiguity never picks (Invariant I3).
- Fee-explained gap becomes FEE_MISMATCH, not AMOUNT_MISMATCH.
- Many-to-one batch with 22 legs classifies correctly.
- Currency mismatch is detected using the real currency columns.
"""

from datetime import UTC, datetime
from decimal import Decimal

from tieout.ingest.money import Money
from tieout.ingest.schema import BankEntry, LedgerEntry, ProcessorEvent, SourceRowRef, WorkItem
from tieout.match.classify import OutcomeClass, classify_work_item


def _make_order_item(
    order_key: str = "ORDER-001",
    ledger_amount: str = "100.00",
    proc_gross: str = "100.00",
    proc_fee: str = "3.20",
    proc_net: str = "96.80",
    ledger_currency: str = "USD",
    proc_currency: str = "USD",
    event_type: str = "CAPTURE",
    has_ledger: bool = True,
    has_proc: bool = True,
    refund_gross: str | None = None,
    second_capture_gross: str | None = None,
) -> WorkItem:
    ledgers = []
    if has_ledger:
        ledgers.append(
            LedgerEntry(
                id=f"leg_{order_key}",
                order_key=order_key,
                occurred_at=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
                amount=Money(Decimal(ledger_amount), ledger_currency),
                currency=ledger_currency,
                status="CAPTURED",
                method="card",
                source_row_ref=SourceRowRef(file="internal_transactions.csv", row_number=2),
            )
        )

    procs = []
    if has_proc:
        procs.append(
            ProcessorEvent(
                id=f"proc_{order_key}_cap",
                order_key=order_key,
                event_type=event_type,
                event_time=datetime(2026, 1, 15, 10, 5, tzinfo=UTC),
                gross=Money(Decimal(proc_gross), proc_currency),
                fee=Money(Decimal(proc_fee), proc_currency),
                net=Money(Decimal(proc_net), proc_currency),
                batch_key="BATCH-001",
                status="SETTLED",
                source_row_ref=SourceRowRef(file="processor_transactions.csv", row_number=2),
            )
        )
        if second_capture_gross is not None:
            procs.append(
                ProcessorEvent(
                    id=f"proc_{order_key}_cap2",
                    order_key=order_key,
                    event_type="CAPTURE",
                    event_time=datetime(2026, 1, 15, 10, 6, tzinfo=UTC),
                    gross=Money(Decimal(second_capture_gross), proc_currency),
                    fee=Money(Decimal(proc_fee), proc_currency),
                    net=Money(Decimal(proc_net), proc_currency),
                    batch_key="BATCH-001",
                    status="SETTLED",
                    source_row_ref=SourceRowRef(file="processor_transactions.csv", row_number=3),
                )
            )
        if refund_gross is not None:
            procs.append(
                ProcessorEvent(
                    id=f"proc_{order_key}_ref",
                    order_key=order_key,
                    event_type="REFUND",
                    event_time=datetime(2026, 1, 16, 11, 0, tzinfo=UTC),
                    gross=Money(Decimal(refund_gross), proc_currency),
                    fee=Money(Decimal("0.00"), proc_currency),
                    net=Money(Decimal(refund_gross), proc_currency),
                    batch_key="BATCH-001",
                    status="SETTLED",
                    source_row_ref=SourceRowRef(file="processor_transactions.csv", row_number=4),
                )
            )

    return WorkItem(work_key=order_key, ledger=ledgers, processor=procs, bank=[])


def _make_settlement_item(
    batch_key: str = "BATCH-001",
    procs_count: int = 1,
    proc_net_per_leg: str = "96.80",
    bank_credited: str = "96.80",
    proc_currency: str = "USD",
    bank_currency: str = "USD",
    days_after_latest: int = 2,
    has_procs: bool = True,
    has_bank: bool = True,
) -> WorkItem:
    procs = []
    if has_procs:
        for i in range(procs_count):
            procs.append(
                ProcessorEvent(
                    id=f"p_{batch_key}_{i}",
                    order_key=f"O_{batch_key}_{i}",
                    event_type="CAPTURE",
                    event_time=datetime(2026, 1, 10, tzinfo=UTC),
                    gross=Money(Decimal("100.00"), proc_currency),
                    fee=Money(Decimal("3.20"), proc_currency),
                    net=Money(Decimal(proc_net_per_leg), proc_currency),
                    batch_key=batch_key,
                    status="SETTLED",
                    source_row_ref=SourceRowRef(
                        file="processor_transactions.csv", row_number=i + 2
                    ),
                )
            )

    banks = []
    if has_bank:
        banks.append(
            BankEntry(
                id=f"bank_{batch_key}",
                batch_key=batch_key,
                booked_at=datetime(2026, 1, 10 + days_after_latest, tzinfo=UTC),
                credited=Money(Decimal(bank_credited), bank_currency),
                reference="REF-001",
                description="Batch deposit",
                source_row_ref=SourceRowRef(file="bank_settlements.csv", row_number=2),
            )
        )

    return WorkItem(work_key=batch_key, ledger=[], processor=procs, bank=banks)


# --- 11 Classes Test Suite ---


def test_class_1_matched():
    wi = _make_order_item(ledger_amount="100.00", proc_gross="100.00", proc_fee="3.20")
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.MATCHED
    assert verdict.reason_code == "L2_EXACT_MATCH"
    assert verdict.confidence >= 0.95


def test_class_2_refund_matched():
    wi = _make_order_item(
        ledger_amount="100.00",
        proc_gross="100.00",
        refund_gross="-100.00",  # Full refund
    )
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.REFUND_MATCHED
    assert verdict.reason_code == "L2_FULL_REFUND_MATCHED"
    assert verdict.confidence >= 0.95


def test_class_3_partial_refund():
    wi = _make_order_item(
        ledger_amount="100.00",
        proc_gross="100.00",
        refund_gross="-50.00",  # Partial refund
    )
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.PARTIAL_REFUND
    assert verdict.reason_code == "L2_PARTIAL_REFUND_MATCHED"
    assert 0.90 <= verdict.confidence < 0.95


def test_class_4_late_settlement():
    # Settled 5 days after batch (exceeds 3 day policy window)
    wi = _make_settlement_item(days_after_latest=5, bank_credited="96.80", proc_net_per_leg="96.80")
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.LATE_SETTLEMENT
    assert verdict.reason_code == "L2_SETTLEMENT_WINDOW_EXCEEDED"
    assert 0.90 <= verdict.confidence < 0.95


def test_class_5_amount_mismatch():
    wi = _make_order_item(ledger_amount="100.00", proc_gross="105.00")
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.AMOUNT_MISMATCH
    assert verdict.reason_code == "L2_AMOUNT_MISMATCH_EXCEEDS_TOLERANCE"
    assert 0.60 <= verdict.confidence < 0.90


def test_class_6_fee_mismatch():
    # Gross matches (100.00 == 100.00), but fee is 4.50 instead of 3.20 (2.9% + 0.30)
    wi = _make_order_item(ledger_amount="100.00", proc_gross="100.00", proc_fee="4.50")
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.FEE_MISMATCH
    assert verdict.reason_code == "L2_FEE_CALCULATION_MISMATCH"
    assert 0.60 <= verdict.confidence < 0.90


def test_class_7_currency_mismatch():
    wi = _make_order_item(ledger_currency="USD", proc_currency="EUR")
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.CURRENCY_MISMATCH
    assert verdict.reason_code == "L2_CURRENCY_MISMATCH"
    assert 0.60 <= verdict.confidence < 0.90


def test_class_8_missing_processor():
    wi = _make_order_item(has_proc=False)
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.MISSING_PROCESSOR
    assert verdict.reason_code == "L2_MISSING_PROCESSOR_EVENT"
    assert verdict.confidence < 0.60


def test_class_9_missing_internal():
    wi = _make_order_item(has_ledger=False)
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.MISSING_INTERNAL
    assert verdict.reason_code == "L2_MISSING_INTERNAL_LEDGER"
    assert verdict.confidence < 0.60


def test_class_10_missing_bank_settlement():
    wi = _make_settlement_item(has_bank=False)
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.MISSING_BANK_SETTLEMENT
    assert verdict.reason_code == "L2_MISSING_BANK_SETTLEMENT"
    assert verdict.confidence < 0.60


def test_class_11_ambiguous_match_never_picks():
    # Invariant I3: Two candidates inside tolerance must emit AMBIGUOUS_MATCH, never a pick
    wi = _make_order_item(
        ledger_amount="100.00",
        proc_gross="100.00",
        second_capture_gross="100.00",  # 2 candidates!
    )
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.AMBIGUOUS_MATCH
    assert verdict.reason_code == "L2_TWO_CANDIDATES_WITHIN_TOLERANCE"
    assert verdict.confidence < 0.60  # Blocks close, forces REFUSE


# --- Named Edge Cases and Complex Shape Tests ---


def test_many_to_one_22_legs_classifies_matched():
    # 22 processor legs summing to bank credited amount
    total_net = str(Decimal("96.80") * 22)
    wi = _make_settlement_item(
        procs_count=22,
        proc_net_per_leg="96.80",
        bank_credited=total_net,
        days_after_latest=2,
    )
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.MATCHED
    assert verdict.reason_code == "L2_BATCH_SETTLEMENT_MATCHED"
    assert verdict.confidence >= 0.95


def test_fee_explained_gap_is_not_amount_mismatch():
    # A fee calculation difference must classify as FEE_MISMATCH, not AMOUNT_MISMATCH
    wi = _make_order_item(ledger_amount="559.43", proc_gross="559.43", proc_fee="16.89")
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.FEE_MISMATCH
    assert verdict.outcome_class != OutcomeClass.AMOUNT_MISMATCH


def test_settlement_currency_mismatch():
    wi = _make_settlement_item(proc_currency="USD", bank_currency="GBP")
    verdict = classify_work_item(wi)
    assert verdict.outcome_class == OutcomeClass.CURRENCY_MISMATCH
    assert verdict.reason_code == "L2_CURRENCY_MISMATCH"
