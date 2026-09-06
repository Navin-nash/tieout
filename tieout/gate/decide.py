"""THE REFUSAL GATE -- SPEC section 6.

One entry point, :func:`decide`. It takes a ``Verdict`` and the policy in force and returns a
:class:`Disposition` carrying the tier, the action, whether it blocks the close, and which
triggers fired. **Four dispositions, and there is no fifth.**

Two orderings in here are load-bearing and neither is an accident:

1. **Admissibility and ambiguity are checked before tiering.** SPEC section 6 makes I3 a gate
   *precondition*. A high-confidence ambiguous item must not be able to reach T0 by scoring
   well, so the preconditions return before :func:`~tieout.gate.tiers.tier_for` is ever
   reached.
2. **The precedent lift is applied after the base tier is known**, and only when the base
   tier is already admissible. SPEC section 9: precedent can accelerate a decision, never
   create admissibility. A REFUSE stays a REFUSE.

This module is also **the single adapter onto** :mod:`tieout.match` (a parallel worker's
package). :func:`read_verdict` is structurally typed -- it reads a ``Verdict`` and its
``FeatureVector`` by name, per SPEC section 3 -- so a rename over there is a one-line fix in
``VERDICT_FIELDS`` / ``FEATURE_FIELDS`` and nowhere else. No feature is computed here and no
tolerance is applied here; both belong to the match and policy layers.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict

from tieout import __version__
from tieout.audit.events import EventLog
from tieout.audit.identity import Identity, ServiceIdentity
from tieout.gate.tiers import (
    ACTION_OF,
    BLOCKING_TIERS,
    TRIGGER_SAMPLED,
    Action,
    GatePolicy,
    Tier,
    is_sampled,
    read_policy,
    tier_for,
)

#: The default initiating identity: a distinct service principal per deployed version, never
#: a shared account (SPEC section 8, requirement 1).
AGENT_IDENTITY = ServiceIdentity(name="tieout-agent", version=f"v{__version__}")

#: SPEC section 3's outcome-class table: these four are inadmissible by construction, whatever
#: confidence the classifier attached. They are the 80 rows the project exists for.
INADMISSIBLE_OUTCOME_CLASSES = frozenset(
    {
        "MISSING_PROCESSOR",
        "MISSING_INTERNAL",
        "MISSING_BANK_SETTLEMENT",
        "AMBIGUOUS_MATCH",
    }
)

#: A deterministic key match, in FeatureVector terms (SPEC section 3: EXACT | PARTIAL | NONE).
DETERMINISTIC_REF_MATCH = "EXACT"

TRIGGER_NO_ADMISSIBLE_MATCH = "L3_NO_ADMISSIBLE_MATCH"
TRIGGER_TWO_CANDIDATES = "L2_TWO_CANDIDATES_WITHIN_TOLERANCE"
TRIGGER_INADMISSIBLE_CLASS = "L3_INADMISSIBLE_OUTCOME_CLASS:"
TRIGGER_BATCH_INCOMPLETE = "L3_UNEXPLAINED_BATCH_INCOMPLETENESS"
TRIGGER_MEMORY_LIFT = "L1_PRECEDENT_LIFT_APPLIED"


class VerdictUnreadable(ValueError):
    """A verdict missing a field the gate needs. Never defaulted -- an absent confidence is
    not a confidence of zero, it is a broken pipeline, and the gate says so."""


# -- The match-layer adapter --------------------------------------------------

#: Field names on ``tieout.match``'s Verdict (SPEC section 3).
VERDICT_FIELDS = ("work_key", "outcome_class", "reason_code", "confidence", "features")
#: Field names on its FeatureVector (SPEC section 3).
FEATURE_FIELDS = ("amount_delta", "candidate_count", "ref_match", "batch_completeness")

_MISSING = object()


def _field(source: Any, name: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, _MISSING)
    return getattr(source, name, _MISSING)


def _require(source: Any, name: str, what: str) -> Any:
    value = _field(source, name)
    if value is _MISSING:
        raise VerdictUnreadable(f"{what} has no {name!r}; the gate cannot decide without it")
    return value


def _amount(value: Any) -> Decimal:
    """Absolute magnitude of a money-ish value, as Decimal. A float here is a defect."""
    raw = getattr(value, "amount", value)
    if isinstance(raw, float):
        raise VerdictUnreadable(
            f"amount_delta arrived as a float ({raw!r}); money is Decimal (SPEC section 3)"
        )
    try:
        return abs(raw if isinstance(raw, Decimal) else Decimal(str(raw)))
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise VerdictUnreadable(f"amount_delta {value!r} is not a decimal amount") from exc


def _enum_text(value: Any) -> str:
    """Render an enum member or plain string as its upper-case name."""
    if isinstance(value, str):
        return value.upper()
    name = getattr(value, "name", None)
    return str(name if name is not None else value).upper()


class GateFeatures(BaseModel):
    """The four FeatureVector fields the gate reads. Nothing here is computed by the gate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amount_abs: Decimal
    candidate_count: int
    ref_match: str
    batch_completeness: Decimal

    @property
    def deterministic_key_match(self) -> bool:
        return self.ref_match == DETERMINISTIC_REF_MATCH

    def as_event_features(self, confidence: float) -> dict[str, Any]:
        """The event ``features`` block, SPEC section 8 shape: decimal strings, never floats.

        The audit log's canonicaliser rejects floats outright, which is why ``confidence`` is
        rendered here rather than handed over raw.
        """
        return {
            "amount_delta": format(self.amount_abs, "f"),
            "candidate_count": self.candidate_count,
            "ref_match": self.ref_match,
            "batch_completeness": format(self.batch_completeness, "f"),
            "confidence": format(Decimal(str(confidence)), "f"),
        }


class GateVerdict(BaseModel):
    """A ``tieout.match`` Verdict, normalised. The gate reads nothing else off a verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    work_key: str
    outcome_class: str
    reason_code: str
    confidence: float
    adjudicator: str
    policy_version: str | None = None
    features: GateFeatures


def read_verdict(verdict: Any) -> GateVerdict:
    """Adapt a ``tieout.match`` Verdict (or an equivalent mapping) for the gate."""
    if isinstance(verdict, GateVerdict):
        return verdict
    raw_features = _require(verdict, "features", "verdict")
    features = GateFeatures(
        amount_abs=_amount(_require(raw_features, "amount_delta", "feature vector")),
        candidate_count=int(_require(raw_features, "candidate_count", "feature vector")),
        ref_match=_enum_text(_require(raw_features, "ref_match", "feature vector")),
        batch_completeness=Decimal(
            str(_require(raw_features, "batch_completeness", "feature vector"))
        ),
    )
    adjudicator = _field(verdict, "adjudicator")
    policy_version = _field(verdict, "policy_version")
    return GateVerdict(
        work_key=str(_require(verdict, "work_key", "verdict")),
        outcome_class=_enum_text(_require(verdict, "outcome_class", "verdict")),
        reason_code=str(_require(verdict, "reason_code", "verdict")),
        confidence=float(_require(verdict, "confidence", "verdict")),
        adjudicator=(
            "DETERMINISTIC" if adjudicator is _MISSING else _enum_text(adjudicator)
        ),
        policy_version=None if policy_version is _MISSING else str(policy_version),
        features=features,
    )


# -- The disposition ----------------------------------------------------------


class Disposition(BaseModel):
    """SPEC section 3: ``verdict, tier, action, blocking, triggers``.

    ``sampled`` and ``event_id`` are additions: the review queue needs to know which T1 items
    were drawn for control evidence, and every caller needs the audit event it can cite.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    verdict: GateVerdict
    tier: Tier
    action: Action
    blocking: bool
    triggers: tuple[str, ...] = ()
    sampled: bool = False
    event_id: str | None = None

    @property
    def reason(self) -> str:
        """The reason code written to the audit log: what fired, else the classifier's code."""
        return self.triggers[0] if self.triggers else self.verdict.reason_code

    @property
    def posts(self) -> bool:
        return self.action in (Action.AUTO_POST, Action.AUTO_SAMPLED)


def _preconditions(
    verdict: GateVerdict, *, batch_incompleteness_explained: bool
) -> tuple[str, ...]:
    """Inadmissibility and ambiguity -- checked before tiering, per SPEC section 6.

    Every clause here is read straight off the feature vector or the outcome class. The gate
    computes no feature and applies no tolerance: "within tolerance" was decided by the match
    layer when it counted the candidates.
    """
    triggers: list[str] = []
    features = verdict.features
    if features.candidate_count >= 2:
        # I3. Ambiguity never resolves to a pick, at any confidence.
        triggers.append(TRIGGER_TWO_CANDIDATES)
    if features.candidate_count <= 0:
        triggers.append(TRIGGER_NO_ADMISSIBLE_MATCH)
    if verdict.outcome_class in INADMISSIBLE_OUTCOME_CLASSES:
        triggers.append(TRIGGER_INADMISSIBLE_CLASS + verdict.outcome_class)
    if features.batch_completeness < 1 and not batch_incompleteness_explained:
        triggers.append(TRIGGER_BATCH_INCOMPLETE)
    return tuple(triggers)


def decide(
    verdict: Any,
    policy: Any,
    *,
    red_flags: tuple[str, ...] = (),
    qualitative_overrides: tuple[str, ...] = (),
    batch_incompleteness_explained: bool = False,
    memory_confidence_lift: float = 0.0,
    run_seed: str = "",
    log: EventLog | None = None,
    actor: Identity | str = AGENT_IDENTITY,
    evidence_ref: str | None = None,
    at: datetime | None = None,
) -> Disposition:
    """Gate one verdict. The only way an item is disposed of in this system.

    ``red_flags`` (AS 2401 para .61) and ``qualitative_overrides`` (SAB 99) are *supplied* by
    the policy layer, not computed here -- the gate consumes findings, it does not make
    materiality judgements. ``batch_incompleteness_explained`` defaults to ``False``: unexplained
    incompleteness refuses, and the caller must positively assert an explanation exists.

    ``memory_confidence_lift`` is the bounded precedent lift of SPEC section 9. It is clamped
    to the policy's maximum, it is only consulted once the item is already admissible, and it
    can never produce a T0 (see :func:`_apply_precedent_lift`).

    Nothing in this function branches on ``verdict.adjudicator``. An LLM-adjudicated verdict
    and a deterministic one traverse identical code (SPEC section 5.5).
    """
    gate_policy: GatePolicy = read_policy(policy)
    view = read_verdict(verdict)

    triggers = _preconditions(view, batch_incompleteness_explained=batch_incompleteness_explained)
    if triggers:
        return _seal(view, Tier.T3, triggers, gate_policy, log, actor, evidence_ref, at)

    tier, triggers = tier_for(
        confidence=view.confidence,
        amount_abs=view.features.amount_abs,
        deterministic_key_match=view.features.deterministic_key_match,
        red_flags=red_flags,
        qualitative_overrides=qualitative_overrides,
        policy=gate_policy,
    )
    if tier is not Tier.T3 and memory_confidence_lift:
        tier, triggers = _apply_precedent_lift(
            view,
            base_tier=tier,
            base_triggers=triggers,
            lift=memory_confidence_lift,
            red_flags=red_flags,
            qualitative_overrides=qualitative_overrides,
            policy=gate_policy,
        )

    sampled = tier is Tier.T1 and is_sampled(view.work_key, run_seed, gate_policy.sample_rate)
    if sampled:
        triggers = (*triggers, TRIGGER_SAMPLED)
    return _seal(view, tier, triggers, gate_policy, log, actor, evidence_ref, at, sampled=sampled)


def _apply_precedent_lift(
    view: GateVerdict,
    *,
    base_tier: Tier,
    base_triggers: tuple[str, ...],
    lift: float,
    red_flags: tuple[str, ...],
    qualitative_overrides: tuple[str, ...],
    policy: GatePolicy,
) -> tuple[Tier, tuple[str, ...]]:
    """SPEC section 9's bounded lift, with its two bounds enforced here rather than trusted.

    The caller is :mod:`tieout.memory`, another worker's module. The bound is a gate concern,
    so it is applied at the gate: whatever lift arrives is clamped to the policy maximum, and
    a lift can only ever move an item *up one step into T1*. It cannot produce a T0 -- that
    tier additionally requires a deterministic key match, and precedent is not a key match --
    and it never runs at all on a T3, which returned before this function was called.
    """
    if base_tier is Tier.T0:
        return base_tier, base_triggers
    bounded = min(max(lift, 0.0), policy.max_memory_confidence_lift)
    lifted_tier, lifted_triggers = tier_for(
        confidence=view.confidence + bounded,
        amount_abs=view.features.amount_abs,
        deterministic_key_match=view.features.deterministic_key_match,
        red_flags=red_flags,
        qualitative_overrides=qualitative_overrides,
        policy=policy,
    )
    if lifted_tier is Tier.T0:
        # Precedent accelerates; it does not confer full autonomy.
        return Tier.T1, (*base_triggers, TRIGGER_MEMORY_LIFT)
    if lifted_tier is base_tier:
        return base_tier, base_triggers
    return lifted_tier, (*lifted_triggers, TRIGGER_MEMORY_LIFT)


def _seal(
    view: GateVerdict,
    tier: Tier,
    triggers: tuple[str, ...],
    policy: GatePolicy,
    log: EventLog | None,
    actor: Identity | str,
    evidence_ref: str | None,
    at: datetime | None,
    *,
    sampled: bool = False,
) -> Disposition:
    """Build the Disposition and write its audit event. Every decision leaves a record."""
    disposition = Disposition(
        verdict=view,
        tier=tier,
        action=ACTION_OF[tier],
        blocking=tier in BLOCKING_TIERS,
        triggers=triggers,
        sampled=sampled,
    )
    if log is None:
        return disposition
    event = log.append(
        actor=actor,
        action=disposition.action.value,
        work_key=view.work_key,
        policy=view.policy_version or policy.version,
        at=at,
        outcome=view.outcome_class,
        reason=disposition.reason,
        features=view.features.as_event_features(view.confidence),
        evidence=evidence_ref,
        blocking=disposition.blocking,
    )
    return disposition.model_copy(update={"event_id": event.event_id})
