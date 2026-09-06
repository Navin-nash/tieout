"""Tripwire: fails loudly if the ReconRiver `month-end-close` schema changes upstream.

Skips cleanly when data/raw/ hasn't been fetched (e.g. CI without network / before
scripts/fetch_dataset.py has run) -- this is a verification test on real data, not a
unit test with fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

RAW_DIR = Path("data/raw")
HOLDOUT_DIR = Path("data/holdout")

pytestmark = pytest.mark.skipif(
    not RAW_DIR.exists(),
    reason="data/raw/ not present -- run `python scripts/fetch_dataset.py` first",
)

EXPECTED_COLUMNS = {
    "internal_transactions.csv": [
        "internal_payment_id",
        "merchant_order_id",
        "occurred_at",
        "gross_amount",
        "currency",
        "payment_status",
        "payment_method",
        "synthetic_customer_reference",
    ],
    "processor_transactions.csv": [
        "processor_transaction_id",
        "merchant_order_id",
        "processor_event_type",
        "processor_event_time",
        "gross_amount",
        "fee_amount",
        "net_amount",
        "currency",
        "settlement_batch_id",
        "processor_status",
    ],
    "bank_settlements.csv": [
        "bank_entry_id",
        "settlement_batch_id",
        "booked_at",
        "credited_amount",
        "currency",
        "bank_reference",
        "description",
    ],
}

EXPECTED_HOLDOUT_COLUMNS = [
    "scenario_id",
    "result_scope",
    "work_key",
    "settlement_batch_id",
    "internal_payment_id",
    "processor_transaction_id",
    "bank_entry_id",
    "expected_outcome",
    "expected_reason_code",
    "expected_difference",
    "explanation",
]


@pytest.mark.parametrize("filename", list(EXPECTED_COLUMNS))
def test_raw_file_columns_exact(filename: str) -> None:
    df = pd.read_csv(RAW_DIR / filename, nrows=0)
    assert list(df.columns) == EXPECTED_COLUMNS[filename], (
        f"{filename} column set/order changed upstream -- re-verify docs/DATASET.md "
        f"before trusting downstream ingest"
    )


def test_holdout_file_columns_exact() -> None:
    df = pd.read_csv(HOLDOUT_DIR / "expected_reconciliation.csv", nrows=0)
    assert list(df.columns) == EXPECTED_HOLDOUT_COLUMNS


def test_raw_holdout_split_is_physical() -> None:
    """The agent-readable set (data/raw/) must never contain ground truth."""
    assert not (RAW_DIR / "expected_reconciliation.csv").exists(), (
        "expected_reconciliation.csv must live only in data/holdout/, never data/raw/ "
        "-- SPEC.md section 3 ground-truth isolation constraint"
    )
    assert (HOLDOUT_DIR / "expected_reconciliation.csv").exists()


def test_row_counts_match_manifest() -> None:
    manifest = json.loads((RAW_DIR / "scenario_manifest.json").read_text(encoding="utf-8"))
    claimed_counts = manifest["file_row_counts"]

    counts = {
        "internal_transactions.csv": len(pd.read_csv(RAW_DIR / "internal_transactions.csv")),
        "processor_transactions.csv": len(pd.read_csv(RAW_DIR / "processor_transactions.csv")),
        "bank_settlements.csv": len(pd.read_csv(RAW_DIR / "bank_settlements.csv")),
        "expected_reconciliation.csv": len(
            pd.read_csv(HOLDOUT_DIR / "expected_reconciliation.csv")
        ),
    }
    assert counts == claimed_counts
