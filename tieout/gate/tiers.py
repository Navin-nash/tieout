"""Confidence-tiered autonomy -- SPEC section 6.

Four tiers, and there is no fifth. The predicates below are the ones in SPEC section 6,
transcribed; the *numbers* in them are not here. Every threshold is read from the policy
layer, because a threshold the agent can read but not write is the guard against the first
row of SPEC section 6's reward-hacking table ("loosen thresholds to make items pass").

This module is also **the single adapter onto** :mod:`tieout.policy` (a parallel worker's
package). Nothing else in ``tieout/gate`` or ``tieout/post`` knows the shape of a Policy
object: :func:`read_policy` is structurally typed and walks either attributes or mapping
keys, so a rename over there is a one-line fix in ``POLICY_PATHS`` and nowhere else.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

#: SPEC section 9 bounds the precedent lift but puts no number on it. This default is
#: overridden by ``memory.max_confidence_lift`` in policy.yaml once the policy layer ships it.
DEFAULT_MAX_MEMORY_LIFT = 0.05


class Tier(StrEnum):
    """The four dispositions of SPEC section 6. Adding a fifth is a spec change."""

    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class Action(StrEnum):
    AUTO_POST = "AUTO_POST"
    AUTO_SAMPLED = "AUTO_SAMPLED"
    ESCALATE = "ESCALATE"
    REFUSE = "REFUSE"


ACTION_OF: dict[Tier, Action] = {
    Tier.T0: Action.AUTO_POST,
    Tier.T1: Action.AUTO_SAMPLED,
    Tier.T2: Action.ESCALATE,
    Tier.T3: Action.REFUSE,
}

#: Only T3 blocks the close (SPEC section 6: T2 "does not block the close").
BLOCKING_TIERS = frozenset({Tier.T3})

# -- Trigger codes ------------------------------------------------------------
# Recorded on the Disposition and written as the event ``reason``. Stable strings, because
# a scoreboard groups by them.

TRIGGER_CONFIDENCE_BELOW_ESCALATE = "L3_CONFIDENCE_BELOW_ESCALATE_MINIMUM"
TRIGGER_AT_OR_ABOVE_PERFORMANCE = "L2_AMOUNT_AT_OR_ABOVE_PERFORMANCE_MATERIALITY"
TRIGGER_QUALITATIVE_PREFIX = "L2_QUALITATIVE_OVERRIDE:"
TRIGGER_RED_FLAG_PREFIX = "L2_AS2401_RED_FLAG:"
TRIGGER_SAMPLED = "L1_SAMPLED_FOR_CONTROL_EVIDENCE"


class PolicyIncomplete(ValueError):
    """A policy that does not carry every threshold the gate needs.

    Never defaulted: a gate that invents a missing materiality threshold is the failure this
    project exists to prevent. Refuse to run instead.
    """


class GatePolicy(BaseModel):
    """The slice of the policy the gate reads. Frozen, and read-only to the agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    clearly_trivial: Decimal
    performance_materiality: Decimal
    auto_min_confidence: float
    auto_sampled_min_confidence: float
    escalate_min_confidence: float
    sample_rate: float
    max_memory_confidence_lift: float = DEFAULT_MAX_MEMORY_LIFT


#: Where each threshold lives in a policy object / parsed policy.yaml (SPEC section 4).
POLICY_PATHS: dict[str, tuple[str, ...]] = {
    "version": ("version",),
    "clearly_trivial": ("materiality", "clearly_trivial", "value"),
    "performance_materiality": ("materiality", "performance", "value"),
    "auto_min_confidence": ("confidence_tiers", "auto", "min_confidence"),
    "auto_sampled_min_confidence": ("confidence_tiers", "auto_sampled", "min_confidence"),
    "escalate_min_confidence": ("confidence_tiers", "escalate", "min_confidence"),
    "sample_rate": ("confidence_tiers", "auto_sampled", "sample_rate"),
}

OPTIONAL_POLICY_PATHS: dict[str, tuple[str, ...]] = {
    "max_memory_confidence_lift": ("memory", "max_confidence_lift"),
}

_MISSING = object()


def _dig(source: Any, path: tuple[str, ...]) -> Any:
    """Walk ``path`` through attributes or mapping keys. Returns ``_MISSING`` if absent."""
    node: Any = source
    for key in path:
        if isinstance(node, Mapping):
            if key not in node:
                return _MISSING
            node = node[key]
        elif hasattr(node, key):
            node = getattr(node, key)
        else:
            return _MISSING
    return node


def _as_decimal(value: Any) -> Decimal:
    """Thresholds are money. A float threshold is a defect, not a convenience."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise PolicyIncomplete(
            f"materiality threshold {value!r} is a float; money thresholds must be Decimal "
            "or a decimal string (SPEC section 3)"
        )
    return Decimal(str(value))


def read_policy(policy: Any) -> GatePolicy:
    """Adapt any policy representation to :class:`GatePolicy`.

    Accepts an already-built :class:`GatePolicy`, a :mod:`tieout.policy` object, or the
    mapping ``yaml.safe_load`` produces. Missing thresholds raise :class:`PolicyIncomplete`.
    """
    if isinstance(policy, GatePolicy):
        return policy
    values: dict[str, Any] = {}
    missing: list[str] = []
    for field, path in POLICY_PATHS.items():
        found = _dig(policy, path)
        if found is _MISSING:
            missing.append(".".join(path))
        else:
            values[field] = found
    if missing:
        raise PolicyIncomplete(
            "policy is missing thresholds the gate requires: " + ", ".join(sorted(missing))
        )
    for field, path in OPTIONAL_POLICY_PATHS.items():
        found = _dig(policy, path)
        if found is not _MISSING:
            values[field] = found
    values["version"] = str(values["version"])
    values["clearly_trivial"] = _as_decimal(values["clearly_trivial"])
    values["performance_materiality"] = _as_decimal(values["performance_materiality"])
    return GatePolicy(**values)


# -- Reproducible sampling ----------------------------------------------------


def is_sampled(work_key: str, run_seed: str, sample_rate: float) -> bool:
    """The deterministic T1 draw for control evidence.

    Seeded from the run, not from :mod:`random`: a sample nobody can reproduce is not control
    evidence, and a ``pass^k`` re-run and the scoreboard must agree on which items were
    sampled. ``hash()`` is salted per process and would not do.
    """
    if sample_rate <= 0:
        return False
    if sample_rate >= 1:
        return True
    digest = hashlib.sha256(f"{run_seed}:{work_key}".encode()).digest()[:8]
    return int.from_bytes(digest, "big") / 2**64 < sample_rate


# -- The tier predicate -------------------------------------------------------


def tier_for(
    *,
    confidence: float,
    amount_abs: Decimal,
    deterministic_key_match: bool,
    red_flags: tuple[str, ...] = (),
    qualitative_overrides: tuple[str, ...] = (),
    policy: GatePolicy,
) -> tuple[Tier, tuple[str, ...]]:
    """The SPEC section 6 predicates, in the only order that resolves their overlap.

    T2's predicate is a disjunction whose confidence clause subsumes T0 and T1, so the tiers
    are evaluated most-restrictive-first and the *forcing* clauses of T2 -- amount at or above
    performance materiality, a qualitative override, an AS 2401 red flag -- are checked before
    autonomy is granted. A high-confidence item carrying a red flag escalates; it does not
    auto-post.

    Note what this function does not take: an ``adjudicator``. The LLM's verdict is tiered by
    exactly this code (SPEC section 5.5, no privileged path), and there is no parameter here
    through which a caller could ask for a different answer.
    """
    triggers: list[str] = []

    if confidence < policy.escalate_min_confidence:
        return Tier.T3, (TRIGGER_CONFIDENCE_BELOW_ESCALATE,)

    if amount_abs >= policy.performance_materiality:
        triggers.append(TRIGGER_AT_OR_ABOVE_PERFORMANCE)
    triggers.extend(TRIGGER_QUALITATIVE_PREFIX + name for name in qualitative_overrides)
    triggers.extend(TRIGGER_RED_FLAG_PREFIX + name for name in red_flags)
    if triggers:
        return Tier.T2, tuple(triggers)

    if (
        confidence >= policy.auto_min_confidence
        and amount_abs < policy.clearly_trivial
        and deterministic_key_match
    ):
        return Tier.T0, ()

    if confidence >= policy.auto_sampled_min_confidence:
        # amount_abs < performance_materiality is already established above.
        return Tier.T1, ()

    return Tier.T2, ()
