"""Tests for deterministic FeatureVector computation."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tieout.ingest.manifest import FeePolicy
from tieout.ingest.money import Money
from tieout.ingest.schema import BankEntry, LedgerEntry, ProcessorEvent, SourceRowRef, WorkItem
from tieout.match.features import FeatureVector, RefMatch, ResultScope, compute_features


def _make_work_item(
    order_key: str = "ORDER-1",
    ledger_amount: str = "100.00",
    proc_gross: str = "100.00",
    proc_fee: str = "3.20",
    proc_net: str = "96.80",
    ledger_currency: str = "USD",
    proc_currency: str = "USD",
    event_type: str = "CAPTURE",
    batch_key: str = "BATCH-1",
) -> WorkItem:
    ledger = LedgerEntry(
        id=f"leg_{order_key}",
        order_key=order_key,
        occurred_at=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
        amount=Money(Decimal(ledger_amount), ledger_currency),
        currency=ledger_currency,
        status="CAPTURED",
        method="card",
        source_row_ref=SourceRowRef(file="internal_transactions.csv", row_number=2),
    )
    proc = ProcessorEvent(
        id=f"proc_{order_key}",
        order_key=order_key,
        event_type=event_type,
        event_time=datetime(2026, 1, 15, 10, 5, tzinfo=UTC),
        gross=Money(Decimal(proc_gross), proc_currency),
        fee=Money(Decimal(proc_fee), proc_currency),
        net=Money(Decimal(proc_net), proc_currency),
        batch_key=batch_key,
        status="SETTLED",
        source_row_ref=SourceRowRef(file="processor_transactions.csv", row_number=2),
    )
    return WorkItem(work_key=order_key, ledger=[ledger], processor=[proc], bank=[])


def test_feature_vector_immutability():
    fv = FeatureVector(
        scope=ResultScope.ORDER,
        amount_delta=Decimal("0.00"),
        date_delta_days=0,
        ref_match=RefMatch.EXACT,
        fee_explained_delta=False,
        currency_mismatch=False,
        candidate_count=1,
        batch_completeness=Decimal("1.00"),
    )
    with pytest.raises(ValidationError):
        fv.amount_delta = Decimal("10.00")  # Frozen model raises on mutation


def test_feature_vector_no_float_allowed():
    # Attempting to assign float to Decimal fields raises TypeError / ValidationError
    with pytest.raises((ValidationError, TypeError)):
        FeatureVector(
            scope=ResultScope.ORDER,
            amount_delta=1.5,  # float not allowed
            date_delta_days=0,
            ref_match=RefMatch.EXACT,
            fee_explained_delta=False,
            currency_mismatch=False,
            candidate_count=1,
            batch_completeness=Decimal("1.00"),
        )


def test_features_exact_order_match():
    wi = _make_work_item(ledger_amount="100.00", proc_gross="100.00", proc_fee="3.20")
    fv = compute_features(wi)

    assert fv.scope == ResultScope.ORDER
    assert isinstance(fv.amount_delta, Decimal)
    assert fv.amount_delta == Decimal("0.00")
    assert fv.currency_mismatch is False
    assert fv.ref_match == RefMatch.EXACT
    assert fv.fee_explained_delta is False
    assert fv.candidate_count == 1


def test_features_currency_mismatch():
    wi = _make_work_item(ledger_currency="USD", proc_currency="EUR")
    fv = compute_features(wi)
    assert fv.currency_mismatch is True


def test_features_fee_mismatch_detection():
    # ReconRiver policy: 2.90% + 0.30 -> on 100.00, expected fee is 3.20
    fee_policy = FeePolicy(
        percentage_rate=Decimal("0.0290"),
        fixed_charge=Decimal("0.30"),
        rounding_mode="HALF_UP",
    )
    # Give a deviating actual fee (e.g. 4.50 instead of 3.20)
    wi = _make_work_item(proc_fee="4.50")
    fv = compute_features(wi, fee_policy=fee_policy)
    assert fv.fee_explained_delta is True


def test_features_settlement_batch_completeness():
    procs = [
        ProcessorEvent(
            id="p1",
            order_key="O1",
            event_type="CAPTURE",
            event_time=datetime(2026, 1, 10, tzinfo=UTC),
            gross=Money(Decimal("100.00"), "USD"),
            fee=Money(Decimal("3.20"), "USD"),
            net=Money(Decimal("96.80"), "USD"),
            batch_key="B1",
            status="SETTLED",
            source_row_ref=SourceRowRef(file="processor_transactions.csv", row_number=2),
        ),
        ProcessorEvent(
            id="p2",
            order_key="O2",
            event_type="CAPTURE",
            event_time=datetime(2026, 1, 11, tzinfo=UTC),
            gross=Money(Decimal("200.00"), "USD"),
            fee=Money(Decimal("6.10"), "USD"),
            net=Money(Decimal("193.90"), "USD"),
            batch_key="B1",
            status="SETTLED",
            source_row_ref=SourceRowRef(file="processor_transactions.csv", row_number=3),
        ),
    ]
    # Total net: 96.80 + 193.90 = 290.70
    bank = BankEntry(
        id="bank_1",
        batch_key="B1",
        booked_at=datetime(2026, 1, 13, tzinfo=UTC),
        credited=Money(Decimal("290.70"), "USD"),
        reference="REF1",
        description="Settlement",
        source_row_ref=SourceRowRef(file="bank_settlements.csv", row_number=2),
    )

    wi = WorkItem(work_key="B1", ledger=[], processor=procs, bank=[bank])
    fv = compute_features(wi)

    assert fv.scope == ResultScope.SETTLEMENT
    assert fv.amount_delta == Decimal("0.00")
    assert fv.batch_completeness == Decimal("1.00")
    assert fv.date_delta_days == 2  # Jan 13 - Jan 11 = 2 days
    assert fv.currency_mismatch is False
