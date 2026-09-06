"""Tests for blocking and candidate WorkItem generation."""

from datetime import UTC, datetime
from decimal import Decimal

from tieout.ingest.money import Money
from tieout.ingest.schema import BankEntry, LedgerEntry, ProcessorEvent, SourceRowRef
from tieout.match.blocking import block_records, fallback_block_orphans


def _make_ledger(order_key: str, amount: str = "100.00", currency: str = "USD") -> LedgerEntry:
    return LedgerEntry(
        id=f"leg_{order_key}",
        order_key=order_key,
        occurred_at=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
        amount=Money(Decimal(amount), currency),
        currency=currency,
        status="CAPTURED",
        method="card",
        source_row_ref=SourceRowRef(file="internal_transactions.csv", row_number=2),
    )


def _make_proc(
    order_key: str,
    event_type: str = "CAPTURE",
    gross: str = "100.00",
    fee: str = "3.20",
    net: str = "96.80",
    currency: str = "USD",
    batch_key: str = "batch_001",
    proc_id: str | None = None,
) -> ProcessorEvent:
    return ProcessorEvent(
        id=proc_id or f"proc_{order_key}_{event_type}",
        order_key=order_key,
        event_type=event_type,
        event_time=datetime(2026, 1, 15, 10, 5, tzinfo=UTC),
        gross=Money(Decimal(gross), currency),
        fee=Money(Decimal(fee), currency),
        net=Money(Decimal(net), currency),
        batch_key=batch_key,
        status="SETTLED",
        source_row_ref=SourceRowRef(file="processor_transactions.csv", row_number=2),
    )


def _make_bank(
    batch_key: str,
    credited: str = "96.80",
    currency: str = "USD",
    booked_at: datetime | None = None,
) -> BankEntry:
    return BankEntry(
        id=f"bank_{batch_key}",
        batch_key=batch_key,
        booked_at=booked_at or datetime(2026, 1, 17, 12, 0, tzinfo=UTC),
        credited=Money(Decimal(credited), currency),
        reference="REF-001",
        description="Settlement credit",
        source_row_ref=SourceRowRef(file="bank_settlements.csv", row_number=2),
    )


def test_blocking_exact_one_to_one():
    ledger = [_make_ledger("ORDER-1")]
    proc = [_make_proc("ORDER-1", batch_key="BATCH-1")]
    bank = [_make_bank("BATCH-1", credited="96.80")]

    items = block_records(ledger, proc, bank)
    # Expect 1 order-level item and 1 batch-level item
    assert len(items) == 2
    order_item = next(i for i in items if i.work_key == "ORDER-1")
    assert len(order_item.ledger) == 1
    assert len(order_item.processor) == 1
    assert len(order_item.bank) == 0

    batch_item = next(i for i in items if i.work_key == "BATCH-1")
    assert len(batch_item.ledger) == 0
    assert len(batch_item.processor) == 1
    assert len(batch_item.bank) == 1


def test_blocking_ambiguous_two_candidates():
    ledger = [_make_ledger("ORDER-AMBIG")]
    proc1 = _make_proc("ORDER-AMBIG", proc_id="proc_1", batch_key="BATCH-1")
    proc2 = _make_proc("ORDER-AMBIG", proc_id="proc_2", batch_key="BATCH-1")
    bank = [_make_bank("BATCH-1", credited="193.60")]

    items = block_records(ledger, [proc1, proc2], bank)
    order_item = next(i for i in items if i.work_key == "ORDER-AMBIG")
    assert len(order_item.ledger) == 1
    assert len(order_item.processor) == 2


def test_blocking_many_to_one_22_legs():
    # Peak fan-out measured in dataset: 22 processor transactions behind 1 bank credit
    procs = []
    total_net = Decimal("0.00")
    for i in range(22):
        p = _make_proc(
            f"ORDER-{i:03d}",
            gross="100.00",
            fee="3.20",
            net="96.80",
            batch_key="BATCH-FANOUT",
        )
        procs.append(p)
        total_net += Decimal("96.80")

    bank = [_make_bank("BATCH-FANOUT", credited=str(total_net))]
    items = block_records([], procs, bank)

    batch_item = next(i for i in items if i.work_key == "BATCH-FANOUT")
    assert len(batch_item.processor) == 22
    assert len(batch_item.bank) == 1
    assert batch_item.bank[0].credited.amount == total_net


def test_blocking_missing_legs():
    ledger = [_make_ledger("ORDER-NOPROC")]
    proc = [_make_proc("ORDER-NOLEDGER", batch_key="BATCH-NOBANK")]

    items = block_records(ledger, proc, [])
    # 2 order items (1 missing proc, 1 missing ledger), 1 batch item (missing bank)
    assert len(items) == 3
    no_proc_item = next(i for i in items if i.work_key == "ORDER-NOPROC")
    assert len(no_proc_item.ledger) == 1
    assert len(no_proc_item.processor) == 0

    no_ledg_item = next(i for i in items if i.work_key == "ORDER-NOLEDGER")
    assert len(no_ledg_item.ledger) == 0
    assert len(no_ledg_item.processor) == 1

    no_bank_item = next(i for i in items if i.work_key == "BATCH-NOBANK")
    assert len(no_bank_item.processor) == 1
    assert len(no_bank_item.bank) == 0


def test_fallback_block_orphans():
    orphans = [
        _make_ledger("O1", amount="150.00", currency="USD"),
        _make_proc("O2", gross="175.00", currency="USD"),
        _make_bank("B1", credited="1500.00", currency="EUR"),
    ]
    buckets = fallback_block_orphans(orphans, amount_bucket_size=100)
    assert ("USD", 1) in buckets
    assert len(buckets[("USD", 1)]) == 2  # 150.00 and 175.00 both land in bucket 1
    assert ("EUR", 15) in buckets
    assert len(buckets[("EUR", 15)]) == 1
