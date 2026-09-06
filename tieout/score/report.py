"""The one JSON the CLI, the API and the dashboard all consume (SPEC section 12).

``build_report`` assembles it; ``render_text`` renders human-readable output *from that same
object*, so the text a judge reads at the terminal and the numbers a chart draws cannot
disagree. The shape is a contract -- ``docs/SCOREBOARD.md`` documents it field by field.

Two rules are enforced here rather than trusted:

1. **Fabrication and straight-through are emitted together.** They come out of one call to
   :func:`tieout.score.metrics.headline` and there is no branch that emits one alone.
2. **An unmeasured baseline is a null with a reason, never a point at the origin.** A chart
   series with ``absent_reason`` set carries ``x``/``y`` of ``null``; a renderer that plots
   it anyway is plotting nothing, which is correct.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from tieout.score.metrics import ClassScore, Metric

FROZEN = ConfigDict(frozen=True, extra="forbid")

REPORT_SCHEMA_VERSION = "tieout.score/1"

#: DESIGN.md section 9.1 assigns each baseline a marker shape and a colour token, reusing
#: the disposition scale rather than inventing a categorical palette. Identity is carried by
#: shape *and* colour *and* the legend label, never by colour alone (DESIGN.md section 11).
BASELINE_STYLE: dict[str, dict[str, str]] = {
    "A": {
        "label": "A - Naive LLM",
        "sublabel": "fabricates to close",
        "marker": "triangle",
        "color_token": "refuse",
        "color_light": "#7A1220",
        "color_dark": "#E8828C",
    },
    "B": {
        "label": "B - Deterministic only",
        "sublabel": "safe, unusable",
        "marker": "square",
        "color_token": "sampled",
        "color_light": "#3B5166",
        "color_dark": "#9CC1E8",
    },
    "C": {
        "label": "C - Tieout",
        "sublabel": "the full system",
        "marker": "circle",
        "color_token": "ink",
        "color_light": "#1A1613",
        "color_dark": "#EDE9E2",
    },
}

#: DESIGN.md section 9.1: y headroom above the worst observed baseline, x always the full
#: 0-100%, gridlines at 25% increments.
CHART_Y_MIN_CEILING = 0.08


class BaselinePoint(BaseModel):
    """One baseline on the two-axis chart. Either both coordinates, or neither plus a reason."""

    model_config = FROZEN

    id: str
    label: str
    sublabel: str
    marker: str
    color_token: str
    color_light: str
    color_dark: str
    straight_through_rate: float | None = None
    fabrication_rate: float | None = None
    absent_reason: str | None = None


class Chart(BaseModel):
    """The two-axis chart of SPEC section 11 -- fabrication rate against straight-through.

    Never one axis alone: SPEC section 11 says either alone is gameable, so the axis pair is
    the chart's identity. This is a scatter of at most three labelled points, not a time
    series and not a dual-axis chart.
    """

    model_config = FROZEN

    id: str = "fabrication-vs-straight-through"
    kind: str = "scatter"
    title: str = "Fabrication rate x straight-through rate"
    caption: str = (
        "Either axis alone is gameable: refuse everything and fabrication is zero; "
        "post everything and straight-through is 100%. Only the pair means anything."
    )
    x: dict[str, Any]
    y: dict[str, Any]
    grid: dict[str, Any]
    target_region: dict[str, Any]
    series: list[BaselinePoint]


class RunContext(BaseModel):
    """What was scored, under what inputs, so a number can be reproduced or invalidated."""

    model_config = FROZEN

    run_id: str
    scored_at: str
    tool_version: str
    policy_version: str
    policy_source: str
    scenario: str
    reproduce_with: str
    input_file_sha256: dict[str, str]
    manifest_verified: bool
    manifest_mismatches: list[dict[str, str]] = []
    ground_truth_isolated: bool = True


class JoinReport(BaseModel):
    """How well predictions and labels lined up. Reported before any metric derived from it."""

    model_config = FROZEN

    join_key: list[str]
    predicted_items: int
    ground_truth_rows: int
    joined: int
    predicted_without_label: int
    labelled_without_prediction: int
    unjoined_predicted_sample: list[str] = []
    unjoined_labelled_sample: list[str] = []


class ScoreReport(BaseModel):
    model_config = FROZEN

    schema_version: str = REPORT_SCHEMA_VERSION
    run: RunContext
    join: JoinReport
    metrics: dict[str, Metric]
    per_class: list[ClassScore]
    confusion: dict[str, dict[str, int]]
    chart: Chart
    notes: list[str] = []

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=indent, sort_keys=False)


def build_chart(
    *,
    tieout: dict[str, Metric],
    baselines: dict[str, dict[str, Metric] | str] | None = None,
) -> Chart:
    """Assemble the chart data.

    ``baselines`` maps ``"A"``/``"B"`` either to a metrics dict (measured) or to a string
    explaining why it is absent. ``tieout`` is baseline C, always measured by this scorer.
    """
    supplied: dict[str, dict[str, Metric] | str] = dict(baselines or {})
    supplied["C"] = tieout

    series: list[BaselinePoint] = []
    observed: list[float] = []
    for key in ("A", "B", "C"):
        style = BASELINE_STYLE[key]
        entry = supplied.get(key)
        if entry is None or isinstance(entry, str):
            series.append(
                BaselinePoint(
                    id=key,
                    absent_reason=(
                        entry
                        if isinstance(entry, str)
                        else "baseline not supplied to the scorer for this run"
                    ),
                    **style,
                )
            )
            continue
        fab = entry.get("fabrication_rate")
        stp = entry.get("straight_through_rate")
        if fab is None or stp is None or not fab.measured or not stp.measured:
            reason = next(
                (
                    m.absent_reason
                    for m in (fab, stp)
                    if m is not None and m.absent_reason is not None
                ),
                "fabrication rate and straight-through rate were not both measured",
            )
            series.append(BaselinePoint(id=key, absent_reason=reason, **style))
            continue
        assert fab.value is not None and stp.value is not None
        observed.append(fab.value)
        series.append(
            BaselinePoint(
                id=key,
                straight_through_rate=stp.value,
                fabrication_rate=fab.value,
                **style,
            )
        )

    y_max = max([CHART_Y_MIN_CEILING, *(v * 1.25 for v in observed)])
    return Chart(
        x={
            "key": "straight_through_rate",
            "label": "Straight-through rate",
            "format": "percent0",
            "domain": [0.0, 1.0],
            "ticks": [0.0, 0.25, 0.5, 0.75, 1.0],
        },
        y={
            "key": "fabrication_rate",
            "label": "Fabrication rate",
            "format": "percent1",
            "domain": [0.0, round(y_max, 4)],
            "ticks": [round(y_max * f, 4) for f in (0.0, 0.25, 0.5, 0.75, 1.0)],
        },
        grid={"increment": 0.25, "color_token": "border-hairline", "axis_label_style": "caption"},
        target_region={
            "label": "Zero fabrication, high straight-through",
            "x": [0.75, 1.0],
            "y": [0.0, 0.005],
            "stroke_token": "border-interactive",
            "dashed": True,
        },
        series=series,
    )


def build_report(
    *,
    run: RunContext,
    join: JoinReport,
    headline: dict[str, Metric],
    other_metrics: Sequence[Metric],
    per_class: list[ClassScore],
    macro_f1: Metric,
    confusion: dict[str, dict[str, int]],
    baselines: dict[str, dict[str, Metric] | str] | None = None,
    notes: Sequence[str] = (),
) -> ScoreReport:
    """Assemble the report. ``headline`` must carry both axes -- this refuses otherwise."""
    missing = {"fabrication_rate", "straight_through_rate"} - set(headline)
    if missing:
        raise ValueError(
            f"headline is missing {sorted(missing)} -- SPEC section 11 forbids reporting "
            "fabrication rate without straight-through rate, or the reverse"
        )
    metrics: dict[str, Metric] = dict(headline)
    metrics["macro_f1"] = macro_f1
    for metric in other_metrics:
        metrics[metric.name] = metric
    return ScoreReport(
        run=run,
        join=join,
        metrics=metrics,
        per_class=per_class,
        confusion=confusion,
        chart=build_chart(tieout=headline, baselines=baselines),
        notes=list(notes),
    )


# -- Text rendering, from the same object -----------------------------------------------


def _fmt(metric: Metric) -> str:
    if not metric.measured:
        return f"ABSENT -- {metric.absent_reason}"
    assert metric.value is not None
    if metric.unit == "ratio":
        return f"{metric.value * 100:.2f}%"
    if metric.unit == "usd":
        return f"${metric.value:,.4f}"
    if metric.unit == "seconds":
        return f"{metric.value:,.2f}s"
    return f"{metric.value:,.1f}"


def _row(label: str, metric: Metric) -> str:
    return f"  {label:<32} {_fmt(metric)}"


def render_text(report: ScoreReport) -> str:
    """Human-readable scoreboard, rendered from the report object and nothing else."""
    m = report.metrics
    out: list[str] = []
    out.append("=" * 78)
    out.append("TIEOUT SCOREBOARD -- out-of-process, against held-out labels")
    out.append("=" * 78)
    out.append(f"  run        {report.run.run_id}")
    out.append(f"  scored at  {report.run.scored_at}")
    out.append(f"  policy     {report.run.policy_version}  (source: {report.run.policy_source})")
    verified = "VERIFIED" if report.run.manifest_verified else "FAILED"
    out.append(f"  input SHA256 vs run manifest: {verified}")
    for mismatch in report.run.manifest_mismatches:
        out.append(f"    ! {mismatch['file']}: expected {mismatch['expected'][:16]}..., "
                   f"actual {mismatch['actual'][:16]}...")
    out.append("")
    out.append("-- join ----------------------------------------------------------------------")
    out.append(f"  join key {'+'.join(report.join.join_key)}")
    out.append(
        f"  {report.join.joined} joined / {report.join.predicted_items} predicted "
        f"/ {report.join.ground_truth_rows} labelled"
    )
    out.append(
        f"  {report.join.predicted_without_label} predicted without a label, "
        f"{report.join.labelled_without_prediction} labelled without a prediction"
    )
    out.append("")
    out.append("-- the two headline metrics (never one without the other) --------------------")
    out.append(_row("fabrication rate", m["fabrication_rate"]))
    out.append(_row("straight-through rate", m["straight_through_rate"]))
    out.append("")
    out.append("-- routing and error ---------------------------------------------------------")
    for key in (
        "classification_accuracy",
        "macro_f1",
        "escalation_precision",
        "refusal_precision",
        "row_weighted_error",
        "materiality_weighted_error",
    ):
        if key in m:
            out.append(_row(key.replace("_", " "), m[key]))
    out.append("")
    out.append("-- cost and latency, per 1,000 work items ------------------------------------")
    for key in ("wall_clock_seconds_per_1k", "tokens_per_1k", "usd_per_1k"):
        if key in m:
            out.append(_row(key.replace("_", " "), m[key]))
    out.append("")
    out.append("-- reliability ---------------------------------------------------------------")
    if "pass_k" in m:
        out.append(_row("pass^k", m["pass_k"]))
    out.append("")
    out.append("-- per-class precision / recall (11 classes) ---------------------------------")
    out.append(f"  {'class':<26}{'true':>7}{'pred':>7}{'prec':>9}{'recall':>9}{'F1':>9}")
    for score in report.per_class:
        if score.absent_reason and score.precision is None and score.recall is None:
            out.append(f"  {score.outcome_class:<26}{score.support_true:>7}"
                       f"{score.support_predicted:>7}   ABSENT -- {score.absent_reason}")
            continue
        prec = f"{score.precision:.3f}" if score.precision is not None else "n/a"
        rec = f"{score.recall:.3f}" if score.recall is not None else "n/a"
        f1 = f"{score.f1:.3f}" if score.f1 is not None else "n/a"
        out.append(
            f"  {score.outcome_class:<26}{score.support_true:>7}{score.support_predicted:>7}"
            f"{prec:>9}{rec:>9}{f1:>9}"
        )
    out.append("")
    out.append("-- the two-axis chart (SPEC section 11) --------------------------------------")
    for point in report.chart.series:
        if point.absent_reason:
            out.append(f"  {point.label:<26} NOT MEASURED -- {point.absent_reason}")
        else:
            assert point.straight_through_rate is not None
            assert point.fabrication_rate is not None
            out.append(
                f"  {point.label:<26} STP {point.straight_through_rate * 100:6.2f}%   "
                f"fabrication {point.fabrication_rate * 100:6.2f}%"
            )
    if report.notes:
        out.append("")
        out.append("-- notes ---------------------------------------------------------------------")
        for note in report.notes:
            out.append(f"  * {note}")
    out.append("")
    out.append(f"reproduce: {report.run.reproduce_with}")
    return "\n".join(out)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()
