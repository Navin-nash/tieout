"""The out-of-process scorer: run the pipeline, join to held-out labels, emit the report.

This module is the process boundary. It runs the same code the agent runs -- blocking,
features, the 11-class cascade, the refusal gate -- and *then*, in the same process but
strictly after every decision has been made and frozen, opens the held-out labels through
:mod:`tieout.score.holdout`. No decision function can see a label: the labels do not exist
in memory until every ``Disposition`` is built.

Before scoring anything it re-verifies the input files' SHA256s against a manifest built
from the same files (``tieout.ingest.manifest.verify``), per SPEC section 6. A score is a
claim about specific bytes; if the bytes moved between the run and the score, the claim is
void and this says so rather than quietly scoring the new bytes.

    uv run python -m tieout.score                     # text
    uv run python -m tieout.score --json score.json   # the report contract
    uv run python -m tieout.score --passk 5           # reliability over k runs
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from tieout import __version__
from tieout.gate.decide import decide
from tieout.gate.tiers import GatePolicy
from tieout.ingest.manifest import build_manifest, verify
from tieout.ingest.reconriver import load_bank_entries, load_ledger_entries, load_processor_events
from tieout.ingest.schema import WorkItem
from tieout.match.blocking import block_records
from tieout.match.classify import Adjudicator, Verdict, classify_all
from tieout.score import metrics as M
from tieout.score.holdout import JOIN_KEY_COLUMNS, load_ground_truth
from tieout.score.report import JoinReport, RunContext, ScoreReport, build_report, utc_now

#: SPEC section 4's ``policy.yaml``, verbatim. Used only until ``policy.yaml`` exists on
#: disk; every report records which of the two it used in ``run.policy_source``, because a
#: number scored under a different policy than the one in force is a different number.
SPEC_SECTION_4_POLICY = GatePolicy(
    version="2026.01-r3",
    clearly_trivial=Decimal("30000.00"),
    performance_materiality=Decimal("450000.00"),
    auto_min_confidence=0.95,
    auto_sampled_min_confidence=0.90,
    escalate_min_confidence=0.60,
    sample_rate=0.05,
)

RUN_SEED = "tieout-score"

#: Baselines A and B live in ``tieout/score/baselines.py``, owned by the ``baseline-a``
#: worker. Until that file lands they are absent-with-a-reason, not zeroes: an unrun
#: experiment plotted at the origin would be a fabricated result inside the fabrication
#: detector.
BASELINE_ABSENT_REASON = (
    "not run: baselines live in tieout/score/baselines.py (owned by the `baseline-a` "
    "worker) and that module has not landed. Plotting an unrun baseline would itself be a "
    "fabricated number."
)


def load_policy(root: Path) -> tuple[GatePolicy, str]:
    """``policy.yaml`` when it exists, otherwise the literal policy of SPEC section 4."""
    path = root / "policy.yaml"
    if not path.exists():
        return SPEC_SECTION_4_POLICY, "SPEC section 4 (policy.yaml not present on disk)"
    import yaml

    from tieout.gate.tiers import read_policy

    return read_policy(yaml.safe_load(path.read_text(encoding="utf-8"))), str(path)


def exposure_of(item: WorkItem) -> Decimal:
    """The absolute dollar magnitude of a work item -- the money that moves if it posts.

    Bank credit for a settlement, ledger gross for an order, processor gross where there is
    no ledger side. This is the weight in the materiality-weighted error, and it comes from
    ``data/raw`` only -- never from ``expected_difference`` in the labels, which would let
    ground truth leak into a weighting the system is graded on.
    """
    if item.bank:
        return abs(sum((b.credited.amount for b in item.bank), Decimal("0")))
    if item.ledger:
        return abs(sum(entry.amount.amount for entry in item.ledger))
    return abs(sum((p.gross.amount for p in item.processor), Decimal("0")))


def run_pipeline(root: Path) -> tuple[list[WorkItem], list[Verdict], list[Any]]:
    """Blocking -> features -> cascade -> refusal gate, over ``data/raw`` only."""
    ledger = load_ledger_entries(root=root)
    processor = load_processor_events(root=root)
    bank = load_bank_entries(root=root)

    work_items = block_records(ledger.rows, processor.rows, bank.rows)
    verdicts = classify_all(work_items)
    policy, _ = load_policy(root)
    dispositions = [decide(v, policy, run_seed=RUN_SEED) for v in verdicts]
    return work_items, verdicts, dispositions


def scored_items(
    work_items: Sequence[WorkItem],
    verdicts: Sequence[Verdict],
    dispositions: Sequence[Any],
    truth: dict[tuple[str, str], Any],
) -> list[M.ScoredItem]:
    """Join each decision to its held-out label on ``(result_scope, work_key)``."""
    by_key = {item.work_key: item for item in work_items}
    items: list[M.ScoredItem] = []
    for verdict, disposition in zip(verdicts, dispositions, strict=True):
        scope = verdict.features.scope.value
        label = truth.get((scope, verdict.work_key))
        work_item = by_key.get(verdict.work_key)
        items.append(
            M.ScoredItem(
                work_key=verdict.work_key,
                scope=scope,
                predicted_class=verdict.outcome_class.value,
                action=disposition.action.value,
                exposure=exposure_of(work_item) if work_item else Decimal("0"),
                truth_class=label.expected_outcome if label else None,
            )
        )
    return items


def decision_fingerprint(
    verdicts: Sequence[Verdict], dispositions: Sequence[Any]
) -> dict[str, tuple[str, str]]:
    """``work_key -> (outcome_class, action)`` -- the projection pass^k compares."""
    return {
        v.work_key: (v.outcome_class.value, d.action.value)
        for v, d in zip(verdicts, dispositions, strict=True)
    }


def score(root: Path | None = None, *, passk: int = 0) -> ScoreReport:
    """Run, verify, join, measure. Returns the report; prints nothing."""
    base = root or Path.cwd()
    started = time.perf_counter()

    manifest = build_manifest(root=base, policy_version="scoring-run")
    verification = verify(manifest, root=base)

    work_items, verdicts, dispositions = run_pipeline(base)
    wall_clock = time.perf_counter() - started

    # Labels are opened only now -- after every decision is frozen.
    truth = load_ground_truth(base)
    items = scored_items(work_items, verdicts, dispositions, truth)

    predicted_keys = {(i.scope, i.work_key) for i in items}
    unjoined_pred = [i.work_key for i in items if i.truth_class is None]
    unjoined_truth = [key[1] for key in truth if key not in predicted_keys]

    headline = M.headline(items)
    per_class, macro_f1 = M.per_class(items)
    weighted = M.weighted_error(items)

    llm_adjudicated = sum(1 for v in verdicts if v.adjudicator is not Adjudicator.DETERMINISTIC)
    if llm_adjudicated:
        tokens_in = tokens_out = None
        cost = None
        token_reason = (
            f"{llm_adjudicated} verdict(s) were LLM-adjudicated but this run captured no "
            "per-call token accounting from tieout.obs spans -- cost is unknown, not zero"
        )
    else:
        tokens_in = tokens_out = 0
        cost = Decimal("0")
        token_reason = None
    cost_latency = M.cost_and_latency(
        work_items=len(items),
        wall_clock_seconds=wall_clock,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        token_accounting_reason=token_reason,
    )

    if passk >= 2:
        runs = [decision_fingerprint(verdicts, dispositions)]
        for _ in range(passk - 1):
            _, rv, rd = run_pipeline(base)
            runs.append(decision_fingerprint(rv, rd))
        passk_metric = M.pass_k(runs)
    else:
        passk_metric = M.Metric.absent(
            "pass_k",
            "not requested: pass^k compares k repeated runs, re-run with --passk 5",
            k=passk,
        )

    notes = [
        "Ground truth was opened only after every disposition was frozen; no decision "
        "function in this process can reach data/holdout/.",
        "Baselines A and B are absent, not zero -- see chart.series[*].absent_reason.",
    ]
    if not verification.ok:
        notes.insert(
            0,
            "INPUT HASH MISMATCH: the files on disk are not the files this manifest was "
            "built from. Every number below is void.",
        )
    if unjoined_pred:
        notes.append(
            f"{len(unjoined_pred)} predicted work item(s) had no ground-truth row; posted "
            "ones count as fabrications, the rest are excluded from precision/recall."
        )

    policy, policy_source = load_policy(base)
    run = RunContext(
        run_id=str(uuid4()),
        scored_at=utc_now(),
        tool_version=f"tieout@{__version__}",
        policy_version=policy.version,
        policy_source=policy_source,
        scenario="month-end-close",
        reproduce_with="uv run python -m tieout.score --passk 5",
        input_file_sha256=manifest.file_hashes,
        manifest_verified=verification.ok,
        manifest_mismatches=[m.model_dump() for m in verification.mismatches],
    )
    join = JoinReport(
        join_key=list(JOIN_KEY_COLUMNS),
        predicted_items=len(items),
        ground_truth_rows=len(truth),
        joined=len(items) - len(unjoined_pred),
        predicted_without_label=len(unjoined_pred),
        labelled_without_prediction=len(unjoined_truth),
        unjoined_predicted_sample=sorted(unjoined_pred)[:10],
        unjoined_labelled_sample=sorted(unjoined_truth)[:10],
    )
    return build_report(
        run=run,
        join=join,
        headline=headline,
        other_metrics=[
            M.accuracy(items),
            M.escalation_precision(items),
            M.refusal_precision(items),
            weighted["row_weighted_error"],
            weighted["materiality_weighted_error"],
            cost_latency["wall_clock_seconds_per_1k"],
            cost_latency["tokens_per_1k"],
            cost_latency["usd_per_1k"],
            passk_metric,
        ],
        per_class=per_class,
        macro_f1=macro_f1,
        confusion=M.confusion(items),
        baselines={"A": BASELINE_ABSENT_REASON, "B": BASELINE_ABSENT_REASON},
        notes=notes,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tieout.score",
        description="Score a Tieout run against held-out labels, out of process.",
    )
    parser.add_argument("--json", type=Path, default=None, help="write the report JSON here")
    parser.add_argument(
        "--passk", type=int, default=0, metavar="K", help="repeat the run K times for pass^k"
    )
    parser.add_argument("--quiet", action="store_true", help="suppress the text scoreboard")
    args = parser.parse_args(argv)

    from tieout.score.report import render_text

    report = score(passk=args.passk)
    if not args.quiet:
        print(render_text(report))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(report.to_json(), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0 if report.run.manifest_verified else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
