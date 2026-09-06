"""Candidate WorkItem generation — SPEC section 5.2.

Generates candidate WorkItems cheaply: exact join on merchant_order_id,
then settlement_batch_id for the bank leg, with fallback grouping
for orphans.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from tieout.ingest.schema import BankEntry, LedgerEntry, ProcessorEvent, WorkItem
from tieout.obs import trace_span, traced


@traced("blocking")
def block_records(
    ledger_entries: list[LedgerEntry],
    processor_events: list[ProcessorEvent],
    bank_entries: list[BankEntry],
) -> list[WorkItem]:
    """Generate candidate WorkItems across order and settlement scopes."""
    work_items: list[WorkItem] = []

    # 1. Order-level grouping (Ledger <-> Processor on order_key)
    proc_by_order: dict[str, list[ProcessorEvent]] = defaultdict(list)
    for proc_event in processor_events:
        proc_by_order[proc_event.order_key].append(proc_event)

    ledger_by_order: dict[str, list[LedgerEntry]] = defaultdict(list)
    for ledger_entry in ledger_entries:
        ledger_by_order[ledger_entry.order_key].append(ledger_entry)

    # All known order keys
    all_order_keys = set(ledger_by_order.keys()) | set(proc_by_order.keys())

    # Sort for deterministic processing order
    for order_key in sorted(all_order_keys):
        l_list = ledger_by_order.get(order_key, [])
        p_list = proc_by_order.get(order_key, [])
        work_items.append(
            WorkItem(
                work_key=order_key,
                ledger=l_list,
                processor=p_list,
                bank=[],
            )
        )

    # 2. Settlement-level grouping (Processor <-> Bank on batch_key)
    proc_by_batch: dict[str, list[ProcessorEvent]] = defaultdict(list)
    for proc_event in processor_events:
        proc_by_batch[proc_event.batch_key].append(proc_event)

    bank_by_batch: dict[str, list[BankEntry]] = defaultdict(list)
    for bank_entry in bank_entries:
        bank_by_batch[bank_entry.batch_key].append(bank_entry)

    all_batch_keys = set(proc_by_batch.keys()) | set(bank_by_batch.keys())

    for batch_key in sorted(all_batch_keys):
        p_list = proc_by_batch.get(batch_key, [])
        b_list = bank_by_batch.get(batch_key, [])
        work_items.append(
            WorkItem(
                work_key=batch_key,
                ledger=[],
                processor=p_list,
                bank=b_list,
            )
        )

    with trace_span("blocking", candidate_group_count=len(work_items)):
        pass

    return work_items


def fallback_block_orphans(
    orphans: list[Any],
    *,
    amount_bucket_size: int = 100,
) -> dict[tuple[str, int], list[Any]]:
    """Group orphaned records by (currency, amount_bucket) as candidate blocks."""
    buckets: dict[tuple[str, int], list[Any]] = defaultdict(list)
    for item in orphans:
        # Extract amount and currency depending on item type
        if isinstance(item, LedgerEntry):
            curr = item.currency
            amt = int(item.amount.amount // amount_bucket_size)
        elif isinstance(item, ProcessorEvent):
            curr = item.gross.currency
            amt = int(item.gross.amount // amount_bucket_size)
        elif isinstance(item, BankEntry):
            curr = item.credited.currency
            amt = int(item.credited.amount // amount_bucket_size)
        else:
            continue
        buckets[(curr, amt)].append(item)
    return dict(buckets)
