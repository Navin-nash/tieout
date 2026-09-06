"""Frozen policy models. Every threshold carries provenance -- that is the feature.

SEC SAB 99 holds that exclusive reliance on a numerical threshold "has no basis in the
accounting literature or the law" and that a percentage is "only the beginning of an analysis
of materiality". A bare number is therefore not a valid policy input in this system: a
`Threshold` without `basis`, `set_by`, `set_at` and `rationale` fails validation.

Everything here is frozen (pydantic `frozen=True`). There is no setter, no `with_*` helper and
no mutating method anywhere in `tieout.policy` -- SPEC section 7 lists `set_threshold` as
deliberately absent, and SPEC section 14's `test_agent_cannot_mutate_policy` asserts it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

# --- money-ish scalars -------------------------------------------------------------------
#
# `tieout/ingest/money.py` (owned by the ingest-money worker) is the project's currency-tagged
# money type. It had not landed when this layer was written, and SPEC section 4's policy.yaml
# carries no currency on its thresholds, so a currency-tagged Money cannot be built from it
# without inventing a field. Policy amounts are therefore plain `Decimal` under the same
# arithmetic contract money.py guarantees: float rejected outright, 2dp, ROUND_HALF_UP.
# ponytail: adopt Money here once thresholds carry a currency; the contract already matches.

_CENTS = Decimal("0.01")


def _reject_float(value: object) -> object:
    if isinstance(value, float):
        raise ValueError(
            "float is not an acceptable money input -- binary floats cannot represent cents "
            "exactly. Supply a Decimal or a quoted string."
        )
    return value


def _to_cents(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _require_tz(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError(
            "set_at must be timezone-aware -- an unanchored timestamp is not provenance"
        )
    return value


Amount = Annotated[Decimal, BeforeValidator(_reject_float), AfterValidator(_to_cents)]
"""A money amount: never a float, always 2dp, always ROUND_HALF_UP."""

Rate = Annotated[Decimal, BeforeValidator(_reject_float), Field(ge=0)]
"""A ratio or percentage expressed as a fraction. Full precision, never a float."""

Attested = Annotated[datetime, AfterValidator(_require_tz)]
NonEmpty = Annotated[str, Field(min_length=1)]

# --- the canonical vocabularies ----------------------------------------------------------
# Named here so `materiality.py` and `redflags.py` take their names from one place, and a
# policy.yaml naming a factor nobody implements is rejected at load time rather than ignored.

QUALITATIVE_OVERRIDES: tuple[str, ...] = (
    "crosses_covenant_threshold",
    "changes_sign_income_to_loss",
    "related_party_counterparty",
    "masks_trend_reversal",
    "affects_management_compensation",
    "conceals_unlawful_transaction",
)

JE_RED_FLAGS: tuple[str, ...] = (
    "round_number_amount",
    "seldom_used_account",
    "post_close_timing",
    "unusual_initiator",
    "no_supporting_explanation",
)

ThresholdName = Literal["overall", "performance", "clearly_trivial"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class Threshold(FrozenModel):
    """A number plus the answer to "who decided this, when, and on what reasoning?".

    All five fields are mandatory. SAB 99 is the reason: a threshold that cannot state its own
    basis is a number pretending to be an analysis.
    """

    value: Amount
    basis: NonEmpty
    set_by: NonEmpty
    set_at: Attested
    rationale: NonEmpty


class Materiality(FrozenModel):
    """AS 2105 materiality set, with the structural checks enforced, not merely documented."""

    overall: Threshold
    performance: Threshold
    clearly_trivial: Threshold

    @model_validator(mode="after")
    def _as2105(self) -> Materiality:
        # AS 2105.06: overall materiality is established as a specified amount, not a percentage
        # alone. `Threshold.value` is a required Amount, so a percentage-only entry cannot be
        # expressed at all; this guards the degenerate zero/negative case.
        if self.overall.value <= 0:
            raise ValueError(
                "AS 2105: overall materiality must be a specified amount greater than zero; "
                f"got {self.overall.value}. A percentage alone is not a materiality level."
            )
        # AS 2105.09: performance materiality is set below overall to allow for the aggregation
        # of undetected misstatements. Strictly less -- equality defeats the purpose.
        if self.performance.value >= self.overall.value:
            raise ValueError(
                "AS 2105: performance materiality must be strictly less than overall "
                f"materiality; got performance={self.performance.value} >= "
                f"overall={self.overall.value}."
            )
        if not (0 < self.clearly_trivial.value < self.performance.value):
            raise ValueError(
                "clearly-trivial must be greater than zero and below performance materiality; "
                f"got clearly_trivial={self.clearly_trivial.value}, "
                f"performance={self.performance.value}."
            )
        return self

    def threshold(self, name: ThresholdName) -> Threshold:
        """Resolve a threshold by the name a confidence tier refers to."""
        return getattr(self, name)  # type: ignore[no-any-return]


class Tolerance(FrozenModel):
    """A matching tolerance for one transaction category. Deliberately not universal."""

    category: NonEmpty
    amount_abs: Amount | None = None
    amount_pct: Rate | None = None
    date_window_days: int = Field(ge=0)
    rationale: str | None = None

    @model_validator(mode="after")
    def _something_specified(self) -> Tolerance:
        if self.amount_abs is None and self.amount_pct is None:
            raise ValueError(
                f"tolerance '{self.category}' specifies neither amount_abs nor amount_pct. "
                "An unbounded amount tolerance is not a tolerance."
            )
        return self


class FeePolicy(FrozenModel):
    """Processor fee terms, resolved from the scenario manifest at load time, never hardcoded.

    SPEC section 19: the manifest is authoritative; the spec's own literals are not.
    """

    pct: Rate
    fixed: Amount
    rounding: Literal["HALF_UP"]
    source: NonEmpty
    """Where these numbers actually came from -- the manifest path and its generator version."""


class ConfidenceTier(FrozenModel):
    min_confidence: Rate = Field(le=1)
    max_amount: ThresholdName | None = None
    sample_rate: Rate | None = Field(default=None, le=1)


class ConfidenceTiers(FrozenModel):
    auto: ConfidenceTier
    auto_sampled: ConfidenceTier
    escalate: ConfidenceTier

    @model_validator(mode="after")
    def _monotonic(self) -> ConfidenceTiers:
        if not (
            self.auto.min_confidence
            >= self.auto_sampled.min_confidence
            >= self.escalate.min_confidence
        ):
            raise ValueError(
                "confidence tiers must be monotonically non-increasing "
                "(auto >= auto_sampled >= escalate); got "
                f"{self.auto.min_confidence}, {self.auto_sampled.min_confidence}, "
                f"{self.escalate.min_confidence}."
            )
        return self

    @property
    def refuse_below(self) -> Decimal:
        """Below the escalate floor there is no tier left -- SPEC section 6, T3 REFUSE."""
        return self.escalate.min_confidence


class Aging(FrozenModel):
    reconcile_within_working_days: int = Field(gt=0)
    suspense_resolve_within_days: int = Field(gt=0)
    escalate_to_controller_after_days: int = Field(gt=0)
    buckets: tuple[int, ...]

    @model_validator(mode="after")
    def _ascending(self) -> Aging:
        if not self.buckets or list(self.buckets) != sorted(set(self.buckets)):
            raise ValueError(f"aging buckets must be ascending and distinct; got {self.buckets}")
        return self


class Policy(FrozenModel):
    """One version of the entity's reconciliation policy. Immutable, attributed, dated."""

    version: NonEmpty
    effective_from: date
    entity: NonEmpty
    supersedes: str | None = None
    illustrative: bool = False
    """True when the materiality figures describe a synthetic entity (SPEC section 19)."""

    materiality: Materiality
    tolerances: tuple[Tolerance, ...]
    confidence_tiers: ConfidenceTiers
    qualitative_overrides: tuple[str, ...]
    je_red_flags: tuple[str, ...]
    aging: Aging

    fee_policy: FeePolicy | None = None
    """None when the scenario manifest was not available. Callers refuse, they do not assume."""

    write_off_authority: Threshold | None = None
    """Deliberately unset, with no default dollar figure.

    SPEC section 10 records the negative research finding: no public policy publishes a dollar
    write-off authority threshold -- they live in internal delegation-of-authority manuals.
    The field exists so a human can set one with provenance. Until then every code path that
    would act on it refuses. See `loader.require_write_off_authority`.
    """

    @model_validator(mode="after")
    def _known_vocabularies(self) -> Policy:
        for field, allowed in (
            ("qualitative_overrides", QUALITATIVE_OVERRIDES),
            ("je_red_flags", JE_RED_FLAGS),
        ):
            names: tuple[str, ...] = getattr(self, field)
            unknown = [n for n in names if n not in allowed]
            if unknown:
                raise ValueError(
                    f"{field} names factors this system does not implement: {unknown}. "
                    f"Known: {list(allowed)}."
                )
            if len(set(names)) != len(names):
                raise ValueError(f"{field} contains duplicates: {list(names)}")
        return self

    @model_validator(mode="after")
    def _distinct_tolerance_categories(self) -> Policy:
        cats = [t.category for t in self.tolerances]
        if len(set(cats)) != len(cats):
            raise ValueError(f"duplicate tolerance categories: {cats}")
        return self

    def tolerance_for(self, category: str) -> Tolerance | None:
        """No universal fallback: an unknown category has no tolerance, so the gate escalates."""
        return next((t for t in self.tolerances if t.category == category), None)
