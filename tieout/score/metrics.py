"""The seven metrics of SPEC section 11, as pure functions over joined records.

Nothing here reads a file, runs a pipeline or knows what a baseline is. Every function takes
:class:`ScoredItem` records -- one per work item, carrying the system's decision and the
held-out label -- and returns a :class:`Metric`.

**A metric is a value or an explicit absence with a reason. There is no third state.**
:class:`Metric` refuses to be constructed with neither, and refuses to be constructed with
both. A scorer for a system whose thesis is "software fabricates a number to satisfy a
check" must not be able to fabricate a number to satisfy a check, so the honesty rule is a
model validator rather than a docstring.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from tieout.gate.decide import INADMISSIBLE_OUTCOME_CLASSES
from tieout.match.classify import OutcomeClass

FROZEN = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

#: The 11 outcome classes, in the order SPEC section 3 tabulates them.
OUTCOME_CLASSES: tuple[str, ...] = tuple(c.value for c in OutcomeClass)

#: Ground-truth classes for which **no admissible counterpart exists in the data**. Posting
#: an item whose true class is one of these is not a misclassification -- it is a match
#: asserted where the data contains none. That is the AccountingBench failure, and it is
#: what ``fabrication_rate`` counts. Imported from the gate so the scorer and the thing it
#: scores cannot drift apart on the definition.
NO_COUNTERPART_CLASSES: frozenset[str] = frozenset(INADMISSIBLE_OUTCOME_CLASSES)

#: Actions that put a number in the books without a human looking at it.
POSTING_ACTIONS = frozenset({"AUTO_POST", "AUTO_SAMPLED"})


class Metric(BaseModel):
    """A measured value, or an explicit absence carrying the reason it is absent."""

    model_config = FROZEN

    name: str
    value: float | None = None
    unit: str = "ratio"
    absent_reason: str | None = None
    detail: dict[str, Any] = {}

    @model_validator(mode="after")
    def _exactly_one_state(self) -> Metric:
        if (self.value is None) == (self.absent_reason is None):
            raise ValueError(
                f"metric {self.name!r} must be either measured or absent-with-a-reason, "
                "never both and never neither -- a placeholder is not a measurement"
            )
        return self

    @property
    def measured(self) -> bool:
        return self.value is not None

    @classmethod
    def of(cls, name: str, value: float, *, unit: str = "ratio", **detail: Any) -> Metric:
        return cls(name=name, value=value, unit=unit, detail=detail)

    @classmethod
    def absent(cls, name: str, reason: str, *, unit: str = "ratio", **detail: Any) -> Metric:
        return cls(name=name, unit=unit, absent_reason=reason, detail=detail)


class ScoredItem(BaseModel):
    """One work item: what the system decided, and what the held-out label says it was.

    ``truth_class is None`` means no ground-truth row joined to this work key. That is not
    treated as a pass -- for a posted item it is the strongest form of fabrication, an
    entry against a work item the labels do not contain at all.
    """

    model_config = FROZEN

    work_key: str
    scope: str
    predicted_class: str
    action: str
    exposure: Decimal = Decimal("0")
    truth_class: str | None = None

    @property
    def posts(self) -> bool:
        return self.action in POSTING_ACTIONS

    @property
    def correct(self) -> bool:
        return self.truth_class is not None and self.predicted_class == self.truth_class

    @property
    def fabricated(self) -> bool:
        """Posted, with no ground-truth counterpart to post against."""
        if not self.posts:
            return False
        return self.truth_class is None or self.truth_class in NO_COUNTERPART_CLASSES


# -- 1 & 2. Fabrication and straight-through -- never one without the other ------------


def headline(items: Sequence[ScoredItem]) -> dict[str, Metric]:
    """Fabrication rate and straight-through rate, together.

    SPEC section 11 is explicit that either alone is gameable: "refuse everything" scores a
    perfect fabrication rate. They are returned from one function, and
    :func:`tieout.score.report.build_report` has no path that emits one without the other,
    so the pairing is structural rather than a convention a caller can forget.
    """
    total = len(items)
    if total == 0:
        reason = "no work items were scored -- the run produced no dispositions"
        return {
            "fabrication_rate": Metric.absent("fabrication_rate", reason),
            "straight_through_rate": Metric.absent("straight_through_rate", reason),
        }

    posted = [i for i in items if i.posts]
    fabricated = [i for i in posted if i.fabricated]
    unlabelled = [i for i in fabricated if i.truth_class is None]
    fabricated_dollars = sum((abs(i.exposure) for i in fabricated), Decimal("0"))

    if not posted:
        fab = Metric.absent(
            "fabrication_rate",
            "nothing was posted, so the ratio has no denominator -- a system that posts "
            "nothing cannot fabricate, which is exactly why straight-through rate is "
            "reported beside it",
            posted=0,
            total_work_items=total,
        )
    else:
        fab = Metric.of(
            "fabrication_rate",
            len(fabricated) / len(posted),
            posted=len(posted),
            fabricated=len(fabricated),
            fabricated_no_ground_truth_row=len(unlabelled),
            fabricated_no_admissible_counterpart=len(fabricated) - len(unlabelled),
            fabricated_dollars=str(fabricated_dollars),
            by_true_class=dict(
                Counter(i.truth_class or "<no ground-truth row>" for i in fabricated)
            ),
        )

    stp = Metric.of(
        "straight_through_rate",
        len(posted) / total,
        posted=len(posted),
        total_work_items=total,
        by_action=dict(Counter(i.action for i in items)),
    )
    return {"fabrication_rate": fab, "straight_through_rate": stp}


# -- 3. Per-class precision / recall ----------------------------------------------------


class ClassScore(BaseModel):
    model_config = FROZEN

    outcome_class: str
    support_true: int
    support_predicted: int
    true_positives: int
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    absent_reason: str | None = None


def per_class(items: Sequence[ScoredItem]) -> tuple[list[ClassScore], Metric]:
    """Precision / recall / F1 for all 11 classes, plus macro-F1.

    SPEC section 11 records that error-*type* classification is far harder than
    localisation (22.2% macro-F1 in the agent literature). Rare classes with tiny support
    are reported as measured, however bad; a class the run never predicted and the labels
    never contain reports its precision and recall absent-with-a-reason rather than 0.0,
    because 0.0 would be a claim about a class that was never at issue.
    """
    joined = [i for i in items if i.truth_class is not None]
    scores: list[ClassScore] = []
    f1s: list[float] = []

    for cls in OUTCOME_CLASSES:
        tp = sum(1 for i in joined if i.predicted_class == cls and i.truth_class == cls)
        pred = sum(1 for i in joined if i.predicted_class == cls)
        true = sum(1 for i in joined if i.truth_class == cls)
        if pred == 0 and true == 0:
            scores.append(
                ClassScore(
                    outcome_class=cls,
                    support_true=0,
                    support_predicted=0,
                    true_positives=0,
                    absent_reason="class absent from both predictions and labels in this run",
                )
            )
            continue
        precision = tp / pred if pred else None
        recall = tp / true if true else None
        if precision is not None and recall is not None and (precision + recall) > 0:
            f1 = 2 * precision * recall / (precision + recall)
        elif precision is not None and recall is not None:
            f1 = 0.0
        else:
            f1 = None
        if f1 is not None:
            f1s.append(f1)
        scores.append(
            ClassScore(
                outcome_class=cls,
                support_true=true,
                support_predicted=pred,
                true_positives=tp,
                precision=precision,
                recall=recall,
                f1=f1,
                absent_reason=(
                    None
                    if precision is not None and recall is not None
                    else (
                        "no predictions of this class in the run"
                        if precision is None
                        else "no labelled instances of this class in the run"
                    )
                ),
            )
        )

    if not f1s:
        macro = Metric.absent(
            "macro_f1", "no class had both predictions and labels -- macro-F1 is undefined"
        )
    else:
        macro = Metric.of("macro_f1", sum(f1s) / len(f1s), classes_averaged=len(f1s))
    return scores, macro


def accuracy(items: Sequence[ScoredItem]) -> Metric:
    """Plain per-item classification accuracy over joined rows."""
    joined = [i for i in items if i.truth_class is not None]
    if not joined:
        return Metric.absent(
            "classification_accuracy", "no predicted work item joined to a ground-truth row"
        )
    correct = sum(1 for i in joined if i.correct)
    return Metric.of(
        "classification_accuracy",
        correct / len(joined),
        joined=len(joined),
        correct=correct,
        unjoined=len(items) - len(joined),
    )


# -- 4. Escalation precision ------------------------------------------------------------


def _routing_precision(items: Sequence[ScoredItem], action: str, name: str) -> Metric:
    routed = [i for i in items if i.action == action]
    if not routed:
        return Metric.absent(
            name, f"the run routed no item to {action}; the ratio has no denominator"
        )
    labelled = [i for i in routed if i.truth_class is not None]
    if not labelled:
        return Metric.absent(
            name, f"no {action} item joined to a ground-truth row; correctness is unknowable"
        )
    genuine = [i for i in labelled if i.truth_class != OutcomeClass.MATCHED.value]
    return Metric.of(
        name,
        len(genuine) / len(labelled),
        routed=len(routed),
        joined=len(labelled),
        genuinely_needed_a_human=len(genuine),
        wasted_on_true_matches=len(labelled) - len(genuine),
        by_true_class=dict(Counter(i.truth_class for i in labelled if i.truth_class)),
    )


def escalation_precision(items: Sequence[ScoredItem]) -> Metric:
    """Of items escalated, the share genuinely needing a human (not ``MATCHED`` in truth).

    Catches over-escalation -- SPEC section 11's *"we like being slow"* failure.
    """
    return _routing_precision(items, "ESCALATE", "escalation_precision")


def refusal_precision(items: Sequence[ScoredItem]) -> Metric:
    """The same measure applied to REFUSE.

    Not one of the seven, and reported anyway: a refusal gate whose refusals are mostly
    true matches is an over-refusing gate, and a scoreboard that reports only escalation
    precision would hide that. SPEC section 11 explicitly refuses to let "refuse
    everything" look good.
    """
    return _routing_precision(items, "REFUSE", "refusal_precision")


# -- 5. Materiality-weighted error, beside row-weighted ---------------------------------


def weighted_error(items: Sequence[ScoredItem]) -> dict[str, Metric]:
    """Row-weighted and dollar-weighted misclassification, always as a pair.

    ``exposure`` is the absolute dollar magnitude of the work item -- the money that would
    move if the item were posted. A $0.02 miss and a $50,000 miss are one row each and are
    not one dollar each, and a row-weighted number alone hides the only errors that matter.
    """
    joined = [i for i in items if i.truth_class is not None]
    if not joined:
        reason = "no predicted work item joined to a ground-truth row"
        return {
            "row_weighted_error": Metric.absent("row_weighted_error", reason),
            "materiality_weighted_error": Metric.absent("materiality_weighted_error", reason),
        }

    wrong = [i for i in joined if not i.correct]
    row = Metric.of(
        "row_weighted_error",
        len(wrong) / len(joined),
        wrong=len(wrong),
        joined=len(joined),
    )

    total_dollars = sum((abs(i.exposure) for i in joined), Decimal("0"))
    if total_dollars == 0:
        dollars = Metric.absent(
            "materiality_weighted_error",
            "total exposure across joined items is $0 -- the dollar-weighted ratio has no "
            "denominator (no amounts were attached to the scored items)",
            unit="ratio",
            wrong_dollars="0",
        )
    else:
        wrong_dollars = sum((abs(i.exposure) for i in wrong), Decimal("0"))
        dollars = Metric.of(
            "materiality_weighted_error",
            float(wrong_dollars / total_dollars),
            wrong_dollars=str(wrong_dollars),
            total_dollars=str(total_dollars),
            largest_single_error=str(max((abs(i.exposure) for i in wrong), default=Decimal("0"))),
        )
    return {"row_weighted_error": row, "materiality_weighted_error": dollars}


# -- 6. Cost and latency per 1,000 work items -------------------------------------------


def cost_and_latency(
    *,
    work_items: int,
    wall_clock_seconds: float | None,
    tokens_in: int | None,
    tokens_out: int | None,
    cost_usd: Decimal | None,
    token_accounting_reason: str | None = None,
) -> dict[str, Metric]:
    """Wall-clock, tokens and USD, normalised per 1,000 work items.

    ``tokens_*`` and ``cost_usd`` of ``None`` mean *not accounted for*, and are emitted
    absent-with-a-reason. A run that made zero LLM calls should pass ``0``, not ``None`` --
    but only when the caller has actually established that, which
    :mod:`tieout.score.run` does by checking every verdict's ``adjudicator``.
    """
    if work_items <= 0:
        reason = "no work items -- a per-1,000 rate has no denominator"
        return {
            key: Metric.absent(key, reason, unit=unit)
            for key, unit in (
                ("wall_clock_seconds_per_1k", "seconds"),
                ("tokens_per_1k", "tokens"),
                ("usd_per_1k", "usd"),
            )
        }
    scale = 1000 / work_items

    if wall_clock_seconds is None:
        wall = Metric.absent(
            "wall_clock_seconds_per_1k", "the run did not record wall-clock time", unit="seconds"
        )
    else:
        wall = Metric.of(
            "wall_clock_seconds_per_1k",
            wall_clock_seconds * scale,
            unit="seconds",
            wall_clock_seconds_total=wall_clock_seconds,
            work_items=work_items,
        )

    missing = token_accounting_reason or "the run carried no token accounting"
    if tokens_in is None or tokens_out is None:
        tokens = Metric.absent("tokens_per_1k", missing, unit="tokens")
    else:
        tokens = Metric.of(
            "tokens_per_1k",
            (tokens_in + tokens_out) * scale,
            unit="tokens",
            tokens_in_total=tokens_in,
            tokens_out_total=tokens_out,
        )
    if cost_usd is None:
        usd = Metric.absent("usd_per_1k", missing, unit="usd")
    else:
        usd = Metric.of(
            "usd_per_1k",
            float(cost_usd) * scale,
            unit="usd",
            usd_total=str(cost_usd),
        )
    return {
        "wall_clock_seconds_per_1k": wall,
        "tokens_per_1k": tokens,
        "usd_per_1k": usd,
    }


# -- 7. pass^k reliability ---------------------------------------------------------------


def pass_k(runs: Sequence[Mapping[str, Any]]) -> Metric:
    """Share of work items on which all ``k`` runs agreed, exactly (tau-bench pass^k).

    Each run is a mapping ``work_key -> decision``, where the decision is any hashable
    projection of the answer -- :mod:`tieout.score.run` uses ``(outcome_class, action)``.
    A work key missing from some run counts as disagreement: an item the system sometimes
    does not produce at all is not a stable decision.
    """
    k = len(runs)
    if k < 2:
        return Metric.absent(
            "pass_k",
            f"pass^k needs at least 2 runs to compare, got {k} -- run with --passk 5",
            k=k,
        )
    keys: set[str] = set()
    for run in runs:
        keys |= set(run.keys())
    if not keys:
        return Metric.absent("pass_k", "the repeated runs produced no work items", k=k)

    unstable = [key for key in keys if len({run.get(key, _ABSENT) for run in runs}) > 1]
    return Metric.of(
        "pass_k",
        (len(keys) - len(unstable)) / len(keys),
        k=k,
        work_items=len(keys),
        unstable_items=len(unstable),
        unstable_sample=sorted(unstable)[:10],
    )


class _Absent:
    """Sentinel for "this run did not produce that work key" -- distinct from any decision."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<no decision>"


_ABSENT = _Absent()


def confusion(items: Iterable[ScoredItem]) -> dict[str, dict[str, int]]:
    """``truth_class -> predicted_class -> count``, over joined rows only."""
    table: dict[str, dict[str, int]] = {}
    for item in items:
        if item.truth_class is None:
            continue
        table.setdefault(item.truth_class, {})
        table[item.truth_class][item.predicted_class] = (
            table[item.truth_class].get(item.predicted_class, 0) + 1
        )
    return table
