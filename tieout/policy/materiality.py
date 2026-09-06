"""SAB 108 dual-method quantification and SAB 99 qualitative overrides.

**SAB 108.** Every proposed adjustment is quantified two ways and is material if *either* is
material. SAB 108's own words: financial statements "would require adjustment when either
approach results in quantifying a misstatement that is material". Most tools pick one method
and inherit its blind spot -- rollover alone lets balance-sheet errors accumulate silently
across years, which is exactly the accumulation the iron curtain method catches.

**SAB 99.** Materiality is not a number. A misstatement below every threshold still requires
escalation when one of the qualitative factors applies, "regardless of amount". The six factors
in SPEC section 4 are implemented as named predicates here, and the ones that fired are returned
so the evidence pack can cite them by name rather than asserting a conclusion.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field, model_validator

from tieout.policy.schema import QUALITATIVE_OVERRIDES, Amount, FrozenModel, Materiality


class Misstatement(FrozenModel):
    """One proposed adjustment, quantified under both SAB 108 methods.

    Both amounts are supplied by the caller because they are different measurements of the same
    error, not derivable from one another:

    * `rollover_amount` -- the amount of the error originating in the *current-year income
      statement*. Also called the current-period or income-statement method.
    * `iron_curtain_amount` -- the effect of correcting the misstatement in the *year-end balance
      sheet*, irrespective of the year in which it originated.

    Signs are irrelevant to materiality, so magnitudes are compared.
    """

    work_key: str = Field(min_length=1)
    rollover_amount: Amount
    iron_curtain_amount: Amount
    description: str = ""


class QualitativeFacts(FrozenModel):
    """Inputs for the SAB 99 factors.

    Three factors are *computed* from figures supplied here; three are *declared*, because they
    depend on registers this system does not hold (a related-party register, a compensation
    plan, a legal determination). Declared factors default to False and must be asserted by the
    caller -- the honest position is that we evaluate what we can measure and carry the rest as
    an input, rather than pretending to detect them.
    """

    # --- computed ---------------------------------------------------------------------
    income_before: Amount | None = None
    """Reported pre-adjustment income for the period. With `Misstatement`, decides sign change."""

    covenant_headroom: Amount | None = None
    """Distance to the nearest debt-covenant threshold before the adjustment. Non-negative."""

    trend_prior: Amount | None = None
    trend_current_before: Amount | None = None
    """Prior and current pre-adjustment values of the metric a trend is read from."""

    # --- declared ---------------------------------------------------------------------
    related_party_counterparty: bool = False
    affects_management_compensation: bool = False
    conceals_unlawful_transaction: bool = False

    detail: tuple[str, ...] = ()
    """Free-text evidence refs the caller wants carried into the evidence pack."""

    @model_validator(mode="after")
    def _headroom_non_negative(self) -> QualitativeFacts:
        if self.covenant_headroom is not None and self.covenant_headroom < 0:
            raise ValueError(
                "covenant_headroom is a distance to a threshold and cannot be negative; a "
                "breach that has already happened is not a headroom measurement."
            )
        return self


class FiredFactor(FrozenModel):
    """A named SAB 99 factor that applies, with the reasoning that made it apply."""

    name: str
    explanation: str


# --- the six factors ----------------------------------------------------------------------
# Each returns an explanation when it fires and None when it does not. The `effect` passed in is
# the signed amount by which correcting the misstatement would move the current-period result --
# the rollover amount, since that is the current-year income-statement effect.


def _crosses_covenant_threshold(effect: Decimal, facts: QualitativeFacts) -> str | None:
    if facts.covenant_headroom is None:
        return None
    if abs(effect) >= facts.covenant_headroom:
        return (
            f"the adjustment of {abs(effect)} equals or exceeds the remaining covenant headroom "
            f"of {facts.covenant_headroom}, so correcting it moves the entity through a debt "
            "covenant threshold"
        )
    return None


def _changes_sign_income_to_loss(effect: Decimal, facts: QualitativeFacts) -> str | None:
    if facts.income_before is None:
        return None
    after = facts.income_before - abs(effect)
    if facts.income_before >= 0 and after < 0:
        return (
            f"income before adjustment is {facts.income_before}; correcting the misstatement "
            f"takes it to {after}, turning reported income into a loss"
        )
    return None


def _related_party_counterparty(effect: Decimal, facts: QualitativeFacts) -> str | None:
    if facts.related_party_counterparty:
        return "the counterparty is a related party, declared by the caller's party register"
    return None


def _masks_trend_reversal(effect: Decimal, facts: QualitativeFacts) -> str | None:
    if facts.trend_prior is None or facts.trend_current_before is None:
        return None
    reported_direction = facts.trend_current_before - facts.trend_prior
    corrected = facts.trend_current_before - abs(effect)
    true_direction = corrected - facts.trend_prior
    if reported_direction >= 0 > true_direction:
        return (
            f"the reported figure moves {reported_direction} against the prior period, but "
            f"after correction it moves {true_direction} -- the misstatement masks a reversal "
            "in the trend"
        )
    return None


def _affects_management_compensation(effect: Decimal, facts: QualitativeFacts) -> str | None:
    if facts.affects_management_compensation:
        return "the affected metric feeds management compensation, declared by the caller"
    return None


def _conceals_unlawful_transaction(effect: Decimal, facts: QualitativeFacts) -> str | None:
    if facts.conceals_unlawful_transaction:
        return "the misstatement conceals an unlawful transaction, declared by the caller"
    return None


_FACTORS = {
    "crosses_covenant_threshold": _crosses_covenant_threshold,
    "changes_sign_income_to_loss": _changes_sign_income_to_loss,
    "related_party_counterparty": _related_party_counterparty,
    "masks_trend_reversal": _masks_trend_reversal,
    "affects_management_compensation": _affects_management_compensation,
    "conceals_unlawful_transaction": _conceals_unlawful_transaction,
}
assert tuple(_FACTORS) == QUALITATIVE_OVERRIDES, "factor table drifted from the policy vocabulary"

COMPUTED_FACTORS: frozenset[str] = frozenset(
    {"crosses_covenant_threshold", "changes_sign_income_to_loss", "masks_trend_reversal"}
)
DECLARED_FACTORS: frozenset[str] = frozenset(QUALITATIVE_OVERRIDES) - COMPUTED_FACTORS


def evaluate_qualitative(
    misstatement: Misstatement,
    facts: QualitativeFacts,
    enabled: tuple[str, ...] = QUALITATIVE_OVERRIDES,
) -> tuple[FiredFactor, ...]:
    """Run the SAB 99 factors the policy has enabled and return the ones that fired."""
    unknown = [name for name in enabled if name not in _FACTORS]
    if unknown:
        raise ValueError(f"unknown qualitative factors: {unknown}")
    effect = misstatement.rollover_amount
    fired = []
    for name in enabled:
        explanation = _FACTORS[name](effect, facts)
        if explanation is not None:
            fired.append(FiredFactor(name=name, explanation=explanation))
    return tuple(fired)


# --- SAB 108 -------------------------------------------------------------------------------


class Assessment(FrozenModel):
    """The result of assessing one misstatement. Frozen, and it shows its work."""

    work_key: str
    rollover_amount: Amount
    iron_curtain_amount: Amount
    threshold: Amount
    rollover_material: bool
    iron_curtain_material: bool
    quantitatively_material: bool
    qualitative_factors: tuple[FiredFactor, ...]
    clearly_trivial: bool
    requires_adjustment: bool
    explanation: str

    @property
    def qualitative_factor_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.qualitative_factors)


def assess(
    misstatement: Misstatement,
    materiality: Materiality,
    facts: QualitativeFacts | None = None,
    enabled_factors: tuple[str, ...] = QUALITATIVE_OVERRIDES,
) -> Assessment:
    """Quantify under both SAB 108 methods, then apply the SAB 99 qualitative overrides.

    The comparison threshold is *overall* materiality: that is the level at which a misstatement
    requires adjustment to the financial statements. Performance materiality is a lower working
    level used when designing procedures, and clearly-trivial is the accumulation floor -- below
    it a difference is not carried forward at all, unless a qualitative factor fires, because
    SAB 99 factors apply regardless of amount.
    """
    facts = facts or QualitativeFacts()
    threshold = materiality.overall.value
    trivial_floor = materiality.clearly_trivial.value

    rollover = abs(misstatement.rollover_amount)
    iron_curtain = abs(misstatement.iron_curtain_amount)

    rollover_material = rollover >= threshold
    iron_curtain_material = iron_curtain >= threshold
    # SAB 108: material if EITHER method says so. This `or` is the whole point.
    quantitatively_material = rollover_material or iron_curtain_material

    fired = evaluate_qualitative(misstatement, facts, enabled_factors)
    clearly_trivial = max(rollover, iron_curtain) < trivial_floor and not fired
    requires_adjustment = quantitatively_material or bool(fired)

    if quantitatively_material:
        methods = [
            name
            for name, hit in (
                ("rollover", rollover_material),
                ("iron curtain", iron_curtain_material),
            )
            if hit
        ]
        reason = (
            f"material under {' and '.join(methods)} "
            f"(rollover {rollover}, iron curtain {iron_curtain}, "
            f"overall materiality {threshold} per {materiality.overall.basis}); "
            "SAB 108 requires adjustment when either method is material"
        )
    elif fired:
        reason = (
            f"below overall materiality of {threshold} under both SAB 108 methods "
            f"(rollover {rollover}, iron curtain {iron_curtain}), but SAB 99 qualitative "
            f"factors apply regardless of amount: {', '.join(f.name for f in fired)}"
        )
    elif clearly_trivial:
        reason = (
            f"clearly trivial: the larger of the two methods is {max(rollover, iron_curtain)}, "
            f"below the clearly-trivial floor of {trivial_floor}, and no qualitative factor fired"
        )
    else:
        reason = (
            f"not material: rollover {rollover} and iron curtain {iron_curtain} are both below "
            f"overall materiality of {threshold}, and no qualitative factor fired"
        )

    return Assessment(
        work_key=misstatement.work_key,
        rollover_amount=rollover,
        iron_curtain_amount=iron_curtain,
        threshold=threshold,
        rollover_material=rollover_material,
        iron_curtain_material=iron_curtain_material,
        quantitatively_material=quantitatively_material,
        qualitative_factors=fired,
        clearly_trivial=clearly_trivial,
        requires_adjustment=requires_adjustment,
        explanation=reason,
    )
