"""The ONLY module in this repository permitted to open ``data/holdout/``.

Ground-truth isolation is an architectural constraint, not a convention (SPEC section 3).
``expected_reconciliation.csv`` is loaded here, in the out-of-process scorer, and nowhere
else. ``tieout/ingest/paths.py`` enforces an allowed-read set for the agent that contains
only the four ``data/raw/`` files; this module deliberately **does not import it**, because
routing the scorer's read through the agent's guard would be the first step towards
widening that guard.

Why the separation is drawn this hard:

* **AccountingBench.** Models close books by inventing a plug that satisfies the check.
  If the check itself is reachable, the plug becomes trivial to find.
* **The Darwin Godel Machine failure (SPEC section 3).** An agent asked to reduce
  hallucination deleted the logging tokens its detector relied on -- it defeated the
  *measurement* rather than the problem. A grader the graded process can reach is not a
  grader. Keeping the labels in a sibling directory that the agent's reader raises
  ``ForbiddenPathError`` on makes that class of reward hacking unrepresentable rather
  than merely discouraged.

``tests/test_score.py::test_agent_reader_cannot_open_holdout`` asserts the guard still
refuses this file, and ``::test_holdout_module_does_not_import_agent_reader`` asserts this
module has not quietly started using it.
"""

from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import BaseModel, ConfigDict

FROZEN = ConfigDict(frozen=True, strict=False, extra="forbid")

HOLDOUT_DIR_NAME = "holdout"
HOLDOUT_FILENAME = "expected_reconciliation.csv"

#: The 11 columns actually present in the file (docs/DATASET.md, verified 2026-09-05).
#: SPEC section 3 lists only the last four; the seven join keys it omits are exactly what a
#: scorer needs to attach a ground-truth row to a computed Verdict.
HOLDOUT_COLUMNS = (
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
)

#: The join key. ``work_key`` alone is not assumed unique: the file carries both ORDER-scope
#: and SETTLEMENT-scope rows and the scope discriminator is part of the identity.
JOIN_KEY_COLUMNS = ("result_scope", "work_key")


class HoldoutMissing(FileNotFoundError):
    """The held-out labels are not on disk. Never substituted, never approximated."""


class HoldoutSchemaError(ValueError):
    """The holdout file is not the file docs/DATASET.md describes. Fail loudly, never coerce."""


class GroundTruthRow(BaseModel):
    """One row of ``expected_reconciliation.csv``, verbatim.

    All seven join keys are kept. ``expected_difference`` is parsed as ``Decimal`` from the
    original CSV text -- the file writes fixed-2dp decimal strings and a float round-trip
    would silently move a money value (PLAN.md rule 3).
    """

    model_config = FROZEN

    scenario_id: str
    result_scope: str
    work_key: str
    settlement_batch_id: str
    internal_payment_id: str
    processor_transaction_id: str
    bank_entry_id: str
    expected_outcome: str
    expected_reason_code: str
    expected_difference: Decimal
    explanation: str

    @property
    def join_key(self) -> tuple[str, str]:
        return (self.result_scope, self.work_key)


def holdout_path(root: Path | None = None) -> Path:
    return (root or Path.cwd()) / "data" / HOLDOUT_DIR_NAME / HOLDOUT_FILENAME


def _decimal(text: str) -> Decimal:
    stripped = (text or "").strip()
    if not stripped:
        return Decimal("0")
    try:
        return Decimal(stripped)
    except InvalidOperation as exc:  # pragma: no cover - a corrupt label file
        raise HoldoutSchemaError(f"expected_difference {text!r} is not a decimal") from exc


def load_ground_truth(
    root: Path | None = None, *, path: Path | None = None
) -> dict[tuple[str, str], GroundTruthRow]:
    """Load the held-out labels, keyed by ``(result_scope, work_key)``.

    Raises rather than returning a partial or empty result: a scorer that silently scores
    against no labels reports a perfect run, which is the exact failure mode this project
    exists to catch.
    """
    target = path or holdout_path(root)
    if not target.exists():
        raise HoldoutMissing(
            f"held-out labels not found at {target}. Run `python scripts/fetch_dataset.py` "
            "to download them into data/holdout/ (gitignored, never committed)."
        )

    with target.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        actual = tuple(reader.fieldnames or ())
        if actual != HOLDOUT_COLUMNS:
            raise HoldoutSchemaError(
                f"holdout schema drift: expected {HOLDOUT_COLUMNS}, got {actual}. "
                "docs/DATASET.md records the verified schema; do not coerce, re-fetch."
            )
        rows: dict[tuple[str, str], GroundTruthRow] = {}
        for raw in reader:
            row = GroundTruthRow(
                scenario_id=raw["scenario_id"],
                result_scope=raw["result_scope"],
                work_key=raw["work_key"],
                settlement_batch_id=raw["settlement_batch_id"],
                internal_payment_id=raw["internal_payment_id"],
                processor_transaction_id=raw["processor_transaction_id"],
                bank_entry_id=raw["bank_entry_id"],
                expected_outcome=raw["expected_outcome"],
                expected_reason_code=raw["expected_reason_code"],
                expected_difference=_decimal(raw["expected_difference"]),
                explanation=raw["explanation"],
            )
            if row.join_key in rows:
                raise HoldoutSchemaError(
                    f"duplicate join key {row.join_key} in holdout -- "
                    "(result_scope, work_key) is not unique, the join is unsound"
                )
            rows[row.join_key] = row

    if not rows:
        raise HoldoutSchemaError(f"{target} contains a header but no label rows")
    return rows
