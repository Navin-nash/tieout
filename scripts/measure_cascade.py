"""Measure the output distribution of the deterministic rule cascade over data/raw.

Runs blocking -> features -> classification over the full scenario.
Only reads data/raw/ (never accesses data/holdout/ or ground truth).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from tieout.ingest.reconriver import (
    load_bank_entries,
    load_ledger_entries,
    load_processor_events,
)
from tieout.match.blocking import block_records
from tieout.match.classify import OutcomeClass, classify_all
from tieout.match.features import ResultScope


def run_measurement(*, root: Path | None = None) -> dict[str, object]:
    base = root or Path.cwd()

    # Load raw data only
    ledger = load_ledger_entries(root=base)
    proc = load_processor_events(root=base)
    bank = load_bank_entries(root=base)

    work_items = block_records(ledger.rows, proc.rows, bank.rows)
    verdicts = classify_all(work_items)

    class_counts = Counter(v.outcome_class.value for v in verdicts)
    # Ensure all enum classes are present in output dictionary
    for outcome in OutcomeClass:
        if outcome.value not in class_counts:
            class_counts[outcome.value] = 0

    tier_counts = {
        "T0_AUTO_POST (conf >= 0.95)": 0,
        "T1_AUTO_SAMPLED (0.90 <= conf < 0.95)": 0,
        "T2_ESCALATE (0.60 <= conf < 0.90)": 0,
        "T3_REFUSE (conf < 0.60)": 0,
    }

    order_scope_count = 0
    settlement_scope_count = 0

    for v in verdicts:
        if v.features.scope == ResultScope.ORDER:
            order_scope_count += 1
        else:
            settlement_scope_count += 1

        if v.confidence >= 0.95:
            tier_counts["T0_AUTO_POST (conf >= 0.95)"] += 1
        elif v.confidence >= 0.90:
            tier_counts["T1_AUTO_SAMPLED (0.90 <= conf < 0.95)"] += 1
        elif v.confidence >= 0.60:
            tier_counts["T2_ESCALATE (0.60 <= conf < 0.90)"] += 1
        else:
            tier_counts["T3_REFUSE (conf < 0.60)"] += 1

    return {
        "raw_counts": {
            "internal_transactions": len(ledger.rows),
            "processor_transactions": len(proc.rows),
            "bank_settlements": len(bank.rows),
        },
        "total_work_items": len(work_items),
        "scope_breakdown": {
            "order_scope": order_scope_count,
            "settlement_scope": settlement_scope_count,
        },
        "class_distribution": dict(sorted(class_counts.items())),
        "confidence_tiers": tier_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run match pipeline cascade on raw data and output class distribution."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write JSON measurement results.",
    )
    args = parser.parse_args()

    results = run_measurement()

    print("=== Match Pipeline Deterministic Cascade Measurement ===")
    print(
        f"Input files: {results['raw_counts']['internal_transactions']} ledger, "
        f"{results['raw_counts']['processor_transactions']} processor, "
        f"{results['raw_counts']['bank_settlements']} bank entries."
    )
    print(f"Total WorkItems generated: {results['total_work_items']}")
    print(
        f"  - Order scope: {results['scope_breakdown']['order_scope']}\n"
        f"  - Settlement scope: {results['scope_breakdown']['settlement_scope']}"
    )

    print("\n--- Produced Outcome Class Distribution ---")
    for cls_name, count in sorted(results["class_distribution"].items()):
        print(f"  {cls_name:25}: {count:6d}")

    print("\n--- Produced Confidence Tier Split ---")
    for tier_name, count in results["confidence_tiers"].items():
        pct = (count / results["total_work_items"]) * 100
        print(f"  {tier_name:40}: {count:6d} ({pct:5.2f}%)")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nWrote measurement JSON to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
