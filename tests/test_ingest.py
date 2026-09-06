"""Ingest guards, quarantine, schema tripwires, manifest verify."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest

from tieout.ingest.manifest import build_manifest, verify
from tieout.ingest.paths import ForbiddenPathError, open_allowed, resolve_allowed_path
from tieout.ingest.reconriver import (
    SchemaMismatchError,
    load_ledger_entries,
)

RAW_DIR = Path("data/raw")
HOLDOUT_FILE = Path("data/holdout/expected_reconciliation.csv")

pytestmark_dataset = pytest.mark.skipif(
    not RAW_DIR.exists(),
    reason="data/raw/ not present -- run `python scripts/fetch_dataset.py` first",
)


def test_agent_cannot_read_ground_truth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path
    raw = root / "data" / "raw"
    holdout = root / "data" / "holdout"
    raw.mkdir(parents=True)
    holdout.mkdir(parents=True)
    (raw / "scenario_manifest.json").write_text("{}", encoding="utf-8")
    (holdout / "expected_reconciliation.csv").write_text("x\n", encoding="utf-8")

    monkeypatch.chdir(root)

    with pytest.raises(ForbiddenPathError):
        open_allowed("data/holdout/expected_reconciliation.csv", root=root)

    with pytest.raises(ForbiddenPathError):
        open_allowed("../holdout/expected_reconciliation.csv", root=root)

    with pytest.raises(ForbiddenPathError):
        resolve_allowed_path("data/raw/../holdout/expected_reconciliation.csv", root=root)

    # Symlink escape: raw/sneaky.csv -> holdout/expected_reconciliation.csv
    link = raw / "internal_transactions.csv"
    target = holdout / "expected_reconciliation.csv"
    try:
        if os.name == "nt":
            os.symlink(str(target), str(link))
        else:
            link.symlink_to(target)
    except OSError:
        return  # direct-path checks above are sufficient when symlinks unavailable

    with pytest.raises(ForbiddenPathError):
        open_allowed(link, root=root)


@pytestmark_dataset
def test_real_dataset_has_zero_quarantine() -> None:
    result = load_ledger_entries()
    assert result.quarantined == []
    assert len(result.rows) == 10000


@pytestmark_dataset
def test_malformed_row_quarantined_not_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path
    raw = root / "data" / "raw"
    raw.mkdir(parents=True)
    header = (
        "internal_payment_id,merchant_order_id,occurred_at,gross_amount,currency,"
        "payment_status,payment_method,synthetic_customer_reference\n"
    )
    good = (
        "pay_1,ord_1,2026-01-01T00:00:00Z,10.00,USD,captured,card,cust_1\n"
    )
    bad = "pay_2,ord_2,2026-01-01T00:00:00Z,NOT_A_NUMBER,USD,captured,card,cust_2\n"
    (raw / "internal_transactions.csv").write_text(header + good + bad, encoding="utf-8")
    (raw / "scenario_manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(root)

    result = load_ledger_entries(root=root)
    assert len(result.rows) == 1
    assert len(result.quarantined) == 1
    assert result.quarantined[0].row_number == 3
    assert result.quarantined[0].reason


def test_renamed_column_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path
    raw = root / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "internal_transactions.csv").write_text(
        "internal_payment_id,merchant_order_id,occurred_at,amount,currency,"
        "payment_status,payment_method,synthetic_customer_reference\n",
        encoding="utf-8",
    )
    (raw / "scenario_manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(root)

    with pytest.raises(SchemaMismatchError, match="missing required column 'gross_amount'"):
        load_ledger_entries(root=root)


@pytestmark_dataset
def test_manifest_verify_detects_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = build_manifest()
    assert verify(manifest).ok

    ledger_path = RAW_DIR / "internal_transactions.csv"
    original = ledger_path.read_bytes()
    try:
        ledger_path.write_bytes(original + b"\n")
        result = verify(manifest)
        assert not result.ok
        assert any(m.file == "internal_transactions.csv" for m in result.mismatches)
    finally:
        ledger_path.write_bytes(original)


@pytestmark_dataset
def test_manifest_reads_fee_policy_from_scenario() -> None:
    manifest = build_manifest()
    assert manifest.fee_policy.percentage_rate == Decimal("0.029")
    assert manifest.fee_policy.fixed_charge == Decimal("0.30")
    assert manifest.fee_policy.rounding_mode == "HALF_UP"
    assert "calendar days" in manifest.settlement_window.lower()
