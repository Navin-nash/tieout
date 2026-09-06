"""The close gate state machine, the period lock and invariant I4 -- SPEC section 10.

The demo's money shot.

State machine:
    Not started
       -> In preparation       (preparer owns)
       -> Submitted for review  (reviewer owns)
       -> [Rejected -> back to preparer]
       -> Approved / certified
       -> Period locked         (immutable)

Invariant I4:
A period with any open REFUSE item cannot close.
No flag, env var or CLI option overrides this.
The close function has no `force`, no `override`, no `skip_gate`, no `ignore_refusals`.

Maker-checker:
The reviewer cannot be the preparer who initiated the reconciliation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tieout.audit.events import EventLog
from tieout.audit.identity import (
    Approval,
    HumanIdentity,
    Identity,
    utc_now,
)
from tieout.gate.decide import AGENT_IDENTITY
from tieout.gate.invariants import (
    assert_no_force_parameter,
    require_no_open_refusals,
)
from tieout.gate.tiers import Action, GatePolicy, Tier


class PeriodState(StrEnum):
    """The six states of the close state machine (SPEC section 10)."""

    NOT_STARTED = "NOT_STARTED"
    IN_PREPARATION = "IN_PREPARATION"
    SUBMITTED_FOR_REVIEW = "SUBMITTED_FOR_REVIEW"
    REJECTED = "REJECTED"
    CERTIFIED = "CERTIFIED"
    LOCKED = "LOCKED"


class CloseStatus(StrEnum):
    """Status emitted on the close report."""

    REFUSED = "REFUSED"
    CLOSED = "CLOSED"


class PeriodLockedError(RuntimeError):
    """Raised when an operation attempts to mutate or reclassify a locked period."""


class InvalidStateTransitionError(ValueError):
    """Raised when a state machine transition is invalid."""


class AutoCertifyRefusedError(ValueError):
    """Raised when auto-certification bypass is refused due to materiality or variance."""


# ── Narrow Policy Adapter ───────────────────────────────────────────────────


class ClosePolicy(BaseModel):
    """The slice of policy required by the close gate.

    Coupling is isolated in this adapter so policy renames are localized.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    performance_materiality: Decimal
    clearly_trivial: Decimal = Decimal("0.00")
    auto_certify_variance_threshold: Decimal = Decimal("0.00")
    write_off_threshold: Decimal | None = None


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, float):
        raise TypeError(
            f"materiality amount {value!r} is a float; money must be Decimal (SPEC section 3)"
        )
    if isinstance(value, Decimal):
        return abs(value)
    try:
        raw = getattr(value, "amount", value)
        return abs(Decimal(str(raw if raw is not None else value)))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"cannot convert {value!r} to Decimal") from exc


def read_close_policy(policy: Any) -> ClosePolicy:
    """Adapt any policy object, GatePolicy, or mapping into a ClosePolicy."""
    if isinstance(policy, ClosePolicy):
        return policy
    if isinstance(policy, GatePolicy):
        return ClosePolicy(
            version=policy.version,
            performance_materiality=policy.performance_materiality,
            clearly_trivial=policy.clearly_trivial,
            auto_certify_variance_threshold=policy.clearly_trivial,
            write_off_threshold=None,
        )
    if isinstance(policy, Mapping):
        version = str(policy.get("version", "unknown"))
        mat = policy.get("materiality", {})
        if isinstance(mat, Mapping):
            perf = mat.get("performance", {})
            perf_val = (
                perf.get("value") if isinstance(perf, Mapping) else getattr(perf, "value", perf)
            )
            triv = mat.get("clearly_trivial", {})
            triv_val = (
                triv.get("value") if isinstance(triv, Mapping) else getattr(triv, "value", triv)
            )
            auto_thresh = mat.get("auto_certify_variance_threshold", triv_val)
            auto_val = (
                auto_thresh.get("value")
                if isinstance(auto_thresh, Mapping)
                else getattr(auto_thresh, "value", auto_thresh)
            )
            write_off = (
                mat.get("write_off_authority", {}).get("value")
                if isinstance(mat.get("write_off_authority"), Mapping)
                else mat.get("write_off_threshold")
            )
        else:
            perf_val = getattr(policy, "performance_materiality", Decimal("0.00"))
            triv_val = getattr(policy, "clearly_trivial", Decimal("0.00"))
            auto_val = getattr(policy, "auto_certify_variance_threshold", triv_val)
            write_off = getattr(policy, "write_off_threshold", None)

        return ClosePolicy(
            version=version,
            performance_materiality=_as_decimal(
                perf_val if perf_val is not None else Decimal("0.00")
            ),
            clearly_trivial=_as_decimal(triv_val if triv_val is not None else Decimal("0.00")),
            auto_certify_variance_threshold=_as_decimal(
                auto_val if auto_val is not None else Decimal("0.00")
            ),
            write_off_threshold=_as_decimal(write_off) if write_off is not None else None,
        )

    version = str(getattr(policy, "version", "unknown"))
    perf_val = getattr(policy, "performance_materiality", Decimal("0.00"))
    triv_val = getattr(policy, "clearly_trivial", Decimal("0.00"))
    auto_val = getattr(policy, "auto_certify_variance_threshold", triv_val)
    write_off = getattr(policy, "write_off_threshold", None)
    return ClosePolicy(
        version=version,
        performance_materiality=_as_decimal(perf_val),
        clearly_trivial=_as_decimal(triv_val),
        auto_certify_variance_threshold=_as_decimal(auto_val),
        write_off_threshold=_as_decimal(write_off) if write_off is not None else None,
    )


# ── Structured Close Report ──────────────────────────────────────────────────


class BlockingClassSummary(BaseModel):
    """Summary of open blocking items grouped by outcome class."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome_class: str
    count: int = Field(ge=0)
    total_amount: Decimal


class CloseReport(BaseModel):
    """Structured report returned by the close gate (SPEC section 10 and 12).

    CLI, web dashboard and scoreboard consume identical structured JSON.
    Straight-through rate and fabrication rate are ALWAYS reported together.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    period: str
    policy_version: str
    total_work_items: int = Field(ge=0)
    t0_count: int = Field(ge=0)
    t0_pct: float = Field(ge=0.0, le=100.0)
    t1_count: int = Field(ge=0)
    t1_pct: float = Field(ge=0.0, le=100.0)
    t1_sampled_count: int = Field(ge=0)
    t2_count: int = Field(ge=0)
    t2_pct: float = Field(ge=0.0, le=100.0)
    t3_count: int = Field(ge=0)
    t3_pct: float = Field(ge=0.0, le=100.0)
    straight_through_rate: float = Field(ge=0.0, le=100.0)
    fabricated_matches: int = Field(ge=0)
    fabrication_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    status: CloseStatus
    blocking_items_count: int = Field(ge=0)
    blocking_classes: tuple[BlockingClassSummary, ...] = ()
    total_blocking_amount: Decimal = Decimal("0.00")
    performance_materiality: Decimal = Decimal("0.00")
    can_close: bool
    message: str = ""

    def render_text(self) -> str:
        """Render ASCII report matching SPEC section 10's terminal output shape."""
        t0_str = f"{self.t0_count:>6,}    {self.t0_pct:>4.1f}%"
        t1_samp = f"({self.t1_sampled_count} sampled)"
        t1_str = f"{self.t1_count:>3,}     {self.t1_pct:>3.1f}%   {t1_samp}"
        t2_str = f"{self.t2_count:>3,}     {self.t2_pct:>3.1f}%"
        t3_str = f"{self.t3_count:>2,}     {self.t3_pct:>3.1f}%"
        lines: list[str] = [
            f"  Reconciliation summary          policy {self.policy_version}",
            "  ─────────────────────────────────────────────────────────",
            f"  work items                              {self.total_work_items:>6,}",
            f"  auto-posted            T0               {t0_str}",
            f"  auto-posted, sampled   T1                  {t1_str}",
            f"  escalated              T2                  {t2_str}",
            f"  refused                T3                   {t3_str}",
            "  ─────────────────────────────────────────────────────────",
            f"  straight-through rate                    {self.straight_through_rate:>4.1f}%",
            f"  fabricated matches                           {self.fabricated_matches:>1}",
            "",
        ]

        if self.status is CloseStatus.REFUSED:
            lines.extend(
                [
                    "  ✕ CLOSE REFUSED",
                    "",
                    f"  {self.blocking_items_count} items are inadmissible and block this period:",
                    "",
                ]
            )
            for b in self.blocking_classes:
                lines.append(f"    {b.outcome_class:<27} {b.count:>2}   $ {b.total_amount:>11,.2f}")
            lines.extend(
                [
                    "                                     ─────────────",
                    f"    total blocking                   $ {self.total_blocking_amount:>11,.2f}",
                    "",
                ]
            )
            if self.total_blocking_amount > self.performance_materiality:
                perf_mat_str = f"${self.performance_materiality:,.2f}"
                lines.extend(
                    [
                        "  Blocking total exceeds performance materiality",
                        f"  ({perf_mat_str}). The period cannot be certified.",
                    ]
                )
            else:
                lines.extend(
                    [
                        (
                            f"  {self.blocking_items_count} open REFUSE item(s) exist "
                            f"(${self.total_blocking_amount:,.2f} total)."
                        ),
                        "  The period cannot be certified.",
                    ]
                )
            lines.extend(
                [
                    "",
                    "  Next: resolve via `tieout queue --blocking`",
                    "  No override exists. This is invariant I4.",
                ]
            )
        else:
            lines.extend(
                [
                    "  ✓ PERIOD CLOSED",
                    "",
                    "  0 items blocking.",
                    "  Reconciliation certified and period locked.",
                ]
            )

        return "\n".join(lines)


def build_close_report(
    period_id: str,
    dispositions: Iterable[Any],
    policy: Any,
    *,
    fabricated_matches: int = 0,
) -> CloseReport:
    """Build the structured CloseReport from a set of dispositions."""
    close_policy = read_close_policy(policy)
    disp_list = list(dispositions)

    total = len(disp_list)
    t0_count = 0
    t1_count = 0
    t1_sampled = 0
    t2_count = 0
    t3_count = 0

    blocking_by_class: dict[str, list[Decimal]] = defaultdict(list)

    for item in disp_list:
        tier = getattr(item, "tier", None)
        action = getattr(item, "action", None)
        blocking = getattr(item, "blocking", False)

        if tier is Tier.T0 or tier == "T0" or action is Action.AUTO_POST or action == "AUTO_POST":
            t0_count += 1
        elif (
            tier is Tier.T1
            or tier == "T1"
            or action is Action.AUTO_SAMPLED
            or action == "AUTO_SAMPLED"
        ):
            t1_count += 1
            if getattr(item, "sampled", False):
                t1_sampled += 1
        elif tier is Tier.T2 or tier == "T2" or action is Action.ESCALATE or action == "ESCALATE":
            t2_count += 1
        elif (
            tier is Tier.T3
            or tier == "T3"
            or action is Action.REFUSE
            or action == "REFUSE"
            or blocking
        ):
            t3_count += 1
        else:
            t2_count += 1

        if (
            blocking
            or tier is Tier.T3
            or tier == "T3"
            or action is Action.REFUSE
            or action == "REFUSE"
        ):
            outcome = "?"
            amount = Decimal("0.00")
            if hasattr(item, "verdict"):
                v = item.verdict
                outcome = getattr(v, "outcome_class", outcome)
                features = getattr(v, "features", None)
                if features is not None:
                    amount = _as_decimal(
                        getattr(
                            features,
                            "amount_abs",
                            getattr(features, "amount_delta", "0.00"),
                        )
                    )
            else:
                outcome = getattr(item, "outcome_class", outcome)
                amt_val = getattr(item, "amount", getattr(item, "amount_abs", "0.00"))
                amount = _as_decimal(amt_val)
            blocking_by_class[str(outcome)].append(amount)

    t0_pct = (t0_count / total * 100.0) if total > 0 else 0.0
    t1_pct = (t1_count / total * 100.0) if total > 0 else 0.0
    t2_pct = (t2_count / total * 100.0) if total > 0 else 0.0
    t3_pct = (t3_count / total * 100.0) if total > 0 else 0.0
    stp_rate = ((t0_count + t1_count) / total * 100.0) if total > 0 else 0.0

    posted_count = t0_count + t1_count
    fab_rate = (fabricated_matches / posted_count * 100.0) if posted_count > 0 else 0.0

    blocking_classes = tuple(
        BlockingClassSummary(
            outcome_class=cls_name,
            count=len(amounts),
            total_amount=sum(amounts, start=Decimal("0.00")),
        )
        for cls_name, amounts in sorted(
            blocking_by_class.items(),
            key=lambda it: sum(it[1], start=Decimal("0.00")),
            reverse=True,
        )
    )

    total_blocking_amt = sum((b.total_amount for b in blocking_classes), start=Decimal("0.00"))
    has_refusals = t3_count > 0 or len(blocking_classes) > 0
    status = CloseStatus.REFUSED if has_refusals else CloseStatus.CLOSED
    can_close = not has_refusals

    msg = (
        f"{t3_count} items are inadmissible and block this period. "
        "Invariant I4: No override exists."
        if has_refusals
        else "Reconciliation certified and period locked."
    )

    return CloseReport(
        period=period_id,
        policy_version=close_policy.version,
        total_work_items=total,
        t0_count=t0_count,
        t0_pct=round(t0_pct, 1),
        t1_count=t1_count,
        t1_pct=round(t1_pct, 1),
        t1_sampled_count=t1_sampled,
        t2_count=t2_count,
        t2_pct=round(t2_pct, 1),
        t3_count=t3_count,
        t3_pct=round(t3_pct, 1),
        straight_through_rate=round(stp_rate, 1),
        fabricated_matches=fabricated_matches,
        fabrication_rate=round(fab_rate, 2),
        status=status,
        blocking_items_count=t3_count,
        blocking_classes=blocking_classes,
        total_blocking_amount=total_blocking_amt,
        performance_materiality=close_policy.performance_materiality,
        can_close=can_close,
        message=msg,
    )


# ── Period State Machine Model ───────────────────────────────────────────────


class Period(BaseModel):
    """A financial close period with frozen state and audit tracking."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    period_id: str
    state: PeriodState = PeriodState.NOT_STARTED
    preparer: Identity | None = None
    reviewer: HumanIdentity | None = None
    policy_version: str | None = None
    report: CloseReport | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    locked_at: datetime | None = None

    def assert_not_locked(self, operation: str = "operation") -> None:
        """Assert that the period is not locked."""
        if self.state is PeriodState.LOCKED:
            raise PeriodLockedError(
                f"period '{self.period_id}' is LOCKED and immutable; "
                f"{operation} is forbidden (SPEC section 10)"
            )


def assert_period_not_locked(period: Period, operation: str = "operation") -> None:
    """Assert a period is not locked before mutating or transitioning."""
    period.assert_not_locked(operation)


# ── Lifecycle Transitions ───────────────────────────────────────────────────


def start_preparation(
    period: Period,
    preparer: Identity,
    *,
    at: datetime | None = None,
    log: EventLog | None = None,
) -> Period:
    """Transition from NOT_STARTED or REJECTED to IN_PREPARATION."""
    assert_no_force_parameter(start_preparation)
    assert_period_not_locked(period, "start_preparation")
    if period.state not in (PeriodState.NOT_STARTED, PeriodState.REJECTED):
        raise InvalidStateTransitionError(
            f"Cannot start preparation from state {period.state.value}"
        )

    now = at or utc_now()
    updated = period.model_copy(
        update={
            "state": PeriodState.IN_PREPARATION,
            "preparer": preparer,
            "updated_at": now,
        }
    )

    if log is not None:
        log.append(
            actor=preparer,
            action="PERIOD_PREPARATION_STARTED",
            work_key=f"period:{period.period_id}",
            policy=period.policy_version or "default",
            at=now,
            reason="Preparation started by preparer",
            features={"period_id": period.period_id, "state": PeriodState.IN_PREPARATION.value},
        )
    return updated


def submit_for_review(
    period: Period,
    preparer: Identity,
    *,
    at: datetime | None = None,
    log: EventLog | None = None,
) -> Period:
    """Transition from IN_PREPARATION or REJECTED to SUBMITTED_FOR_REVIEW."""
    assert_no_force_parameter(submit_for_review)
    assert_period_not_locked(period, "submit_for_review")
    if period.state not in (PeriodState.IN_PREPARATION, PeriodState.REJECTED):
        raise InvalidStateTransitionError(
            f"Cannot submit for review from state {period.state.value}"
        )

    now = at or utc_now()
    updated = period.model_copy(
        update={
            "state": PeriodState.SUBMITTED_FOR_REVIEW,
            "preparer": preparer,
            "updated_at": now,
        }
    )

    if log is not None:
        log.append(
            actor=preparer,
            action="PERIOD_SUBMITTED_FOR_REVIEW",
            work_key=f"period:{period.period_id}",
            policy=period.policy_version or "default",
            at=now,
            reason="Submitted for human reviewer certification",
            features={
                "period_id": period.period_id,
                "state": PeriodState.SUBMITTED_FOR_REVIEW.value,
            },
        )
    return updated


def reject_period(
    period: Period,
    reviewer: HumanIdentity,
    reason: str,
    *,
    at: datetime | None = None,
    log: EventLog | None = None,
) -> Period:
    """Transition from SUBMITTED_FOR_REVIEW to REJECTED."""
    assert_no_force_parameter(reject_period)
    assert_period_not_locked(period, "reject_period")
    if not isinstance(reviewer, HumanIdentity):
        raise TypeError(f"reviewer must be a HumanIdentity, got {type(reviewer).__name__}")
    if period.state is not PeriodState.SUBMITTED_FOR_REVIEW:
        raise InvalidStateTransitionError(f"Cannot reject period from state {period.state.value}")

    now = at or utc_now()
    updated = period.model_copy(
        update={
            "state": PeriodState.REJECTED,
            "reviewer": reviewer,
            "updated_at": now,
        }
    )

    if log is not None:
        log.append(
            actor=reviewer,
            action="PERIOD_REJECTED",
            work_key=f"period:{period.period_id}",
            policy=period.policy_version or "default",
            at=now,
            reason=f"Rejected by reviewer: {reason}",
            features={"period_id": period.period_id, "state": PeriodState.REJECTED.value},
        )
    return updated


def certify_period(
    period: Period,
    reviewer: HumanIdentity,
    dispositions: Iterable[Any],
    policy: Any,
    *,
    at: datetime | None = None,
    log: EventLog | None = None,
    fabricated_matches: int = 0,
) -> tuple[Period, CloseReport]:
    """Certify a period submitted for review.

    Maker-checker rule enforced: reviewer cannot be the preparer.
    Invariant I4 enforced: raises InvariantViolation if any open REFUSE exists.
    """
    assert_no_force_parameter(certify_period)
    assert_period_not_locked(period, "certify_period")
    if not isinstance(reviewer, HumanIdentity):
        raise TypeError(
            f"certify_period reviewer must be a HumanIdentity, got {type(reviewer).__name__}"
        )
    if period.state not in (PeriodState.SUBMITTED_FOR_REVIEW, PeriodState.IN_PREPARATION):
        raise InvalidStateTransitionError(f"Cannot certify period from state {period.state.value}")

    now = at or utc_now()

    # Maker-checker / Four-eyes enforcement
    if period.preparer is not None:
        Approval(
            initiator=period.preparer,
            approver=reviewer,
            at=now,
            note="period certification",
        )

    # Invariant I4 enforcement
    require_no_open_refusals(dispositions)

    close_policy = read_close_policy(policy)
    report = build_close_report(
        period.period_id,
        dispositions,
        close_policy,
        fabricated_matches=fabricated_matches,
    )

    updated = period.model_copy(
        update={
            "state": PeriodState.CERTIFIED,
            "reviewer": reviewer,
            "policy_version": close_policy.version,
            "report": report,
            "updated_at": now,
        }
    )

    if log is not None:
        log.append(
            actor=reviewer,
            action="PERIOD_CERTIFIED",
            work_key=f"period:{period.period_id}",
            policy=close_policy.version,
            at=now,
            reason="Period approved and certified under maker-checker review",
            features={
                "period_id": period.period_id,
                "straight_through_rate": str(report.straight_through_rate),
                "fabricated_matches": report.fabricated_matches,
                "total_work_items": report.total_work_items,
            },
        )

    return updated, report


def auto_certify_period(
    period: Period,
    dispositions: Iterable[Any],
    policy: Any,
    *,
    actor: Identity = AGENT_IDENTITY,
    at: datetime | None = None,
    log: EventLog | None = None,
    fabricated_matches: int = 0,
) -> tuple[Period, CloseReport]:
    """Auto-certification bypass below configured variance threshold (SPEC section 10).

    Management's own materiality decision as configuration, not a regulator-mandated number.
    Invariant I4 still holds: any open REFUSE item prevents auto-certification.
    """
    assert_no_force_parameter(auto_certify_period)
    assert_period_not_locked(period, "auto_certify_period")
    if period.state not in (PeriodState.IN_PREPARATION, PeriodState.NOT_STARTED):
        raise InvalidStateTransitionError(f"Cannot auto-certify from state {period.state.value}")

    now = at or utc_now()
    close_policy = read_close_policy(policy)

    # I4 check
    require_no_open_refusals(dispositions)

    report = build_close_report(
        period.period_id,
        dispositions,
        close_policy,
        fabricated_matches=fabricated_matches,
    )

    # Check variance threshold
    if report.total_blocking_amount > close_policy.auto_certify_variance_threshold:
        raise AutoCertifyRefusedError(
            f"Blocking/variance total (${report.total_blocking_amount:,.2f}) exceeds configured "
            f"auto-certification threshold (${close_policy.auto_certify_variance_threshold:,.2f}). "
            "Human review is required."
        )

    updated = period.model_copy(
        update={
            "state": PeriodState.CERTIFIED,
            "policy_version": close_policy.version,
            "report": report,
            "updated_at": now,
        }
    )

    if log is not None:
        log.append(
            actor=actor,
            action="PERIOD_AUTO_CERTIFIED",
            work_key=f"period:{period.period_id}",
            policy=close_policy.version,
            at=now,
            reason="Auto-certified below configured materiality variance threshold",
            features={
                "period_id": period.period_id,
                "straight_through_rate": str(report.straight_through_rate),
                "variance_threshold": format(close_policy.auto_certify_variance_threshold, "f"),
            },
        )

    return updated, report


def lock_period(
    period: Period,
    *,
    actor: Identity = AGENT_IDENTITY,
    at: datetime | None = None,
    log: EventLog | None = None,
) -> Period:
    """Lock a certified period, making it strictly immutable."""
    assert_no_force_parameter(lock_period)
    assert_period_not_locked(period, "lock_period")
    if period.state is not PeriodState.CERTIFIED:
        raise InvalidStateTransitionError(
            f"Cannot lock period in state {period.state.value}; must be CERTIFIED first"
        )

    now = at or utc_now()
    locked = period.model_copy(
        update={
            "state": PeriodState.LOCKED,
            "locked_at": now,
            "updated_at": now,
        }
    )

    if log is not None:
        log.append(
            actor=actor,
            action="PERIOD_LOCKED",
            work_key=f"period:{period.period_id}",
            policy=period.policy_version or "default",
            at=now,
            reason="Period sealed and locked; books immutable",
            features={"period_id": period.period_id, "state": PeriodState.LOCKED.value},
        )

    return locked


# ── The Close Gate Entrypoint ────────────────────────────────────────────────


def close_gate(
    period_id: str,
    dispositions: Iterable[Any],
    policy: Any,
    *,
    reviewer: HumanIdentity | None = None,
    preparer: Identity | None = None,
    log: EventLog | None = None,
    at: datetime | None = None,
    fabricated_matches: int = 0,
) -> tuple[Period, CloseReport]:
    """The Close Gate entrypoint.

    Asserts no force/override parameter exists.
    Evaluates dispositions and produces the structured report.
    If open refusals exist: emits CLOSE_REFUSED audit event, reports refusal, and refuses lock (I4).
    If no refusals exist: certifies and locks the period.
    """
    assert_no_force_parameter(close_gate)

    now = at or utc_now()
    close_policy = read_close_policy(policy)
    report = build_close_report(
        period_id,
        dispositions,
        close_policy,
        fabricated_matches=fabricated_matches,
    )

    initial_period = Period(
        period_id=period_id,
        state=PeriodState.IN_PREPARATION,
        preparer=preparer,
        policy_version=close_policy.version,
        report=report,
        created_at=now,
        updated_at=now,
    )

    if not report.can_close:
        # Emit hash-chained audit event for refusal
        if log is not None:
            log.append(
                actor=reviewer or preparer or AGENT_IDENTITY,
                action="CLOSE_REFUSED",
                work_key=f"period:{period_id}",
                policy=close_policy.version,
                at=now,
                reason=f"I4: {report.blocking_items_count} open REFUSE item(s) block close",
                blocking=True,
                features={
                    "period_id": period_id,
                    "blocking_count": report.blocking_items_count,
                    "total_blocking_amount": format(report.total_blocking_amount, "f"),
                    "straight_through_rate": str(report.straight_through_rate),
                    "fabricated_matches": report.fabricated_matches,
                },
            )
        return initial_period, report

    # Happy path: no refusals. Progress through certification and lock.
    if reviewer is not None and preparer is not None:
        cert_period, _ = certify_period(
            initial_period,
            reviewer=reviewer,
            dispositions=dispositions,
            policy=close_policy,
            at=now,
            log=log,
            fabricated_matches=fabricated_matches,
        )
    else:
        cert_period, _ = auto_certify_period(
            initial_period,
            dispositions=dispositions,
            policy=close_policy,
            actor=preparer or AGENT_IDENTITY,
            at=now,
            log=log,
            fabricated_matches=fabricated_matches,
        )

    locked = lock_period(cert_period, actor=reviewer or preparer or AGENT_IDENTITY, at=now, log=log)
    return locked, report
