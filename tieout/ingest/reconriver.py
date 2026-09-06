"""ReconRiver CSV adapter — string cells to frozen models, quarantine on failure."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, TypeVar

from tieout.ingest.money import Money
from tieout.ingest.paths import open_allowed, raw_data_dir
from tieout.ingest.schema import BankEntry, LedgerEntry, ProcessorEvent, SourceRowRef

INTERNAL_COLUMNS = [
    "internal_payment_id",
    "merchant_order_id",
    "occurred_at",
    "gross_amount",
    "currency",
    "payment_status",
    "payment_method",
    "synthetic_customer_reference",
]

PROCESSOR_COLUMNS = [
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
]

BANK_COLUMNS = [
    "bank_entry_id",
    "settlement_batch_id",
    "booked_at",
    "credited_amount",
    "currency",
    "bank_reference",
    "description",
]


class SchemaMismatchError(ValueError):
    """Raised when CSV columns differ from docs/DATASET.md."""


@dataclass(frozen=True)
class QuarantinedRow:
    file: str
    row_number: int
    reason: str
    raw: dict[str, str]


T = TypeVar("T")


@dataclass
class IngestResult(Generic[T]):
    rows: list[T]
    quarantined: list[QuarantinedRow]


def _check_columns(header: list[str], expected: list[str], filename: str) -> None:
    if header == expected:
        return
    for col in expected:
        if col not in header:
            raise SchemaMismatchError(
                f"{filename}: missing required column '{col}' "
                f"(expected {expected}, got {header})"
            )
    for col in header:
        if col not in expected:
            raise SchemaMismatchError(
                f"{filename}: unexpected column '{col}' "
                f"(expected {expected}, got {header})"
            )
    raise SchemaMismatchError(
        f"{filename}: column order mismatch (expected {expected}, got {header})"
    )


def _parse_dt(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _read_csv_rows(
    filename: str, expected_columns: list[str], *, root: Path
) -> list[dict[str, str]]:
    path = raw_data_dir(root) / filename
    with open_allowed(path, root=root) as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise SchemaMismatchError(f"{filename}: empty or headerless file")
        _check_columns(list(reader.fieldnames), expected_columns, filename)
        return list(reader)


def load_ledger_entries(*, root: Path | None = None) -> IngestResult[LedgerEntry]:
    base = root or Path.cwd()
    filename = "internal_transactions.csv"
    good: list[LedgerEntry] = []
    quarantined: list[QuarantinedRow] = []

    for row_num, row in enumerate(
        _read_csv_rows(filename, INTERNAL_COLUMNS, root=base), start=2
    ):
        try:
            currency = row["currency"].strip()
            good.append(
                LedgerEntry(
                    id=row["internal_payment_id"].strip(),
                    order_key=row["merchant_order_id"].strip(),
                    occurred_at=_parse_dt(row["occurred_at"]),
                    amount=Money.from_csv(row["gross_amount"], currency),
                    currency=currency,
                    status=row["payment_status"].strip(),
                    method=row["payment_method"].strip(),
                    source_row_ref=SourceRowRef(file=filename, row_number=row_num),
                )
            )
        except (KeyError, ValueError, ArithmeticError) as exc:
            quarantined.append(
                QuarantinedRow(
                    file=filename,
                    row_number=row_num,
                    reason=str(exc),
                    raw=dict(row),
                )
            )

    return IngestResult(rows=good, quarantined=quarantined)


def load_processor_events(*, root: Path | None = None) -> IngestResult[ProcessorEvent]:
    base = root or Path.cwd()
    filename = "processor_transactions.csv"
    good: list[ProcessorEvent] = []
    quarantined: list[QuarantinedRow] = []

    for row_num, row in enumerate(
        _read_csv_rows(filename, PROCESSOR_COLUMNS, root=base), start=2
    ):
        try:
            currency = row["currency"].strip()
            good.append(
                ProcessorEvent(
                    id=row["processor_transaction_id"].strip(),
                    order_key=row["merchant_order_id"].strip(),
                    event_type=row["processor_event_type"].strip(),
                    event_time=_parse_dt(row["processor_event_time"]),
                    gross=Money.from_csv(row["gross_amount"], currency),
                    fee=Money.from_csv(row["fee_amount"], currency),
                    net=Money.from_csv(row["net_amount"], currency),
                    batch_key=row["settlement_batch_id"].strip(),
                    status=row["processor_status"].strip(),
                    source_row_ref=SourceRowRef(file=filename, row_number=row_num),
                )
            )
        except (KeyError, ValueError, ArithmeticError) as exc:
            quarantined.append(
                QuarantinedRow(
                    file=filename,
                    row_number=row_num,
                    reason=str(exc),
                    raw=dict(row),
                )
            )

    return IngestResult(rows=good, quarantined=quarantined)


def load_bank_entries(*, root: Path | None = None) -> IngestResult[BankEntry]:
    base = root or Path.cwd()
    filename = "bank_settlements.csv"
    good: list[BankEntry] = []
    quarantined: list[QuarantinedRow] = []

    for row_num, row in enumerate(
        _read_csv_rows(filename, BANK_COLUMNS, root=base), start=2
    ):
        try:
            currency = row["currency"].strip()
            good.append(
                BankEntry(
                    id=row["bank_entry_id"].strip(),
                    batch_key=row["settlement_batch_id"].strip(),
                    booked_at=_parse_dt(row["booked_at"]),
                    credited=Money.from_csv(row["credited_amount"], currency),
                    reference=row["bank_reference"].strip(),
                    description=row["description"].strip(),
                    source_row_ref=SourceRowRef(file=filename, row_number=row_num),
                )
            )
        except (KeyError, ValueError, ArithmeticError) as exc:
            quarantined.append(
                QuarantinedRow(
                    file=filename,
                    row_number=row_num,
                    reason=str(exc),
                    raw=dict(row),
                )
            )

    return IngestResult(rows=good, quarantined=quarantined)


def load_all(*, root: Path | None = None) -> dict[str, Any]:
    """Load all three agent-readable CSVs."""
    return {
        "ledger": load_ledger_entries(root=root),
        "processor": load_processor_events(root=root),
        "bank": load_bank_entries(root=root),
    }
