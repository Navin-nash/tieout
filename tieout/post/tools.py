"""The constrained tool surface -- SPEC section 7.

    "AccountingBench models plug because they can. We didn't prompt ours not to -- we deleted
    the tool. There is no function in this system that posts an amount somebody didn't match.
    The plug isn't forbidden; it's unrepresentable."

:class:`ToolSurface` is the entire set of actions available to the agent. Seven methods, named
in ``ALLOWED_TOOLS``. Everything in ``ABSENT_TOOLS`` is absent -- not guarded, not permissioned,
not behind a flag. Absent. ``tests/test_invariants.py`` introspects both lists, so the day
someone helpfully adds ``create_adjusting_entry`` the suite goes red.

The one method that moves money, :meth:`ToolSurface.post_matched_entry`, takes a
:class:`~tieout.post.journal.MatchId` and no amount. See :mod:`tieout.post.journal` for why
that makes an unbalanced entry unrepresentable rather than merely detectable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from tieout.audit.events import EventLog
from tieout.audit.identity import Identity
from tieout.gate.decide import AGENT_IDENTITY
from tieout.gate.invariants import require_admissible_match
from tieout.post.journal import JournalEntry, MatchId, MatchStore, build_entry

#: SPEC section 7, "what the agent CAN do". This is the whole list.
ALLOWED_TOOLS: tuple[str, ...] = (
    "read_work_item",
    "compute_features",
    "propose_verdict",
    "escalate",
    "refuse",
    "post_matched_entry",
    "cite_prior_decision",
)

#: SPEC section 7, "what does not exist, and why". Transcribed so the reasons stay attached to
#: the names; asserted absent by ``tests/test_invariants.py``.
ABSENT_TOOLS: dict[str, str] = {
    "create_adjusting_entry": "the plug. Absent.",
    "force_balance": "absent.",
    "write_suspense": "absent.",
    "set_threshold": "policy is human-only.",
    "mark_period_closed": "no force param exists; closing is the close gate's, not the agent's.",
    "edit_source_row": "ingest is append-only.",
    "delete_event": "the log is hash-chained.",
    "read_expected_reconciliation": "outside the allowed-read set.",
}


class WorkItemSource(Protocol):
    """Read side of ingest. Read-only by construction: there is no ``put``."""

    def get(self, work_key: str) -> Any | None: ...


class FeatureSource(Protocol):
    """The deterministic feature computation of :mod:`tieout.match` (SPEC section 5 step 3).

    Adapter seam: the gate and the tool surface never compute a feature themselves.
    """

    def compute(self, work_key: str) -> Any: ...


class PriorDecisionSource(Protocol):
    """Read side of :mod:`tieout.memory`. Citing a precedent is a read, never a write."""

    def get(self, decision_id: str) -> Any | None: ...


class QueueSink(Protocol):
    """Where escalations and refusals go for human review."""

    def put(self, item: Any) -> None: ...


class UnknownWorkItem(KeyError):
    """A work key that does not resolve. The agent may not invent one."""


class UnknownPriorDecision(KeyError):
    """A decision id that does not resolve. A citation must point at something real."""


FROZEN = ConfigDict(frozen=True, extra="forbid")


class ProposedVerdict(BaseModel):
    """The structured output the agent may return (SPEC section 5 step 5).

    It cannot return an amount and it cannot return a new transaction -- there is no field for
    either. ``features`` is not a parameter of :meth:`ToolSurface.propose_verdict`: it is
    computed deterministically and attached here, so a proposal cannot come with its own
    arithmetic.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    work_key: str
    outcome_class: str
    reason_code: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    cited_row_refs: tuple[str, ...] = ()
    features: Any = None
    policy_version: str = ""
    adjudicator: str = "LLM"


class QueueItem(BaseModel):
    """A T2 escalation: the recommendation, the reason and the evidence, for a human."""

    model_config = FROZEN

    work_key: str
    recommendation: str
    evidence_refs: tuple[str, ...] = ()


class Refusal(BaseModel):
    """A T3 refusal. ``blocking`` is not a parameter -- a refusal blocks, that is what it is."""

    model_config = FROZEN

    work_key: str
    reason_code: str
    blocking_explanation: str
    blocking: bool = True


@dataclass(frozen=True)
class ToolSurface:
    """Everything the agent can do, and nothing else.

    The collaborators are injected as protocols so this module imports neither
    :mod:`tieout.match` nor :mod:`tieout.policy`; ``policy_version`` is carried as a string
    because the agent needs to *record* the policy in force and never to change it.
    """

    work_items: WorkItemSource
    features: FeatureSource
    matches: MatchStore
    policy_version: str
    log: EventLog | None = None
    actor: Identity | str = AGENT_IDENTITY
    queue: QueueSink | None = None
    memory: PriorDecisionSource | None = None
    adjudicator: str = "LLM"

    # -- reads ---------------------------------------------------------------

    def read_work_item(self, work_key: str) -> Any:
        item = self.work_items.get(work_key)
        if item is None:
            raise UnknownWorkItem(f"no work item {work_key!r}")
        return item

    def compute_features(self, work_key: str) -> Any:
        """Deterministic feature computation, delegated. No LLM in this struct."""
        return self.features.compute(work_key)

    def cite_prior_decision(self, decision_id: str) -> Any:
        """Cite a human's prior decision (SPEC section 9). A read, and only a read."""
        if self.memory is None:
            raise UnknownPriorDecision("no decision memory is wired to this tool surface")
        prior = self.memory.get(decision_id)
        if prior is None:
            raise UnknownPriorDecision(f"no prior decision {decision_id!r}")
        return prior

    # -- proposals -----------------------------------------------------------

    def propose_verdict(
        self,
        work_key: str,
        outcome_class: str,
        reason_code: str,
        confidence: float,
        rationale: str,
        cited_row_refs: tuple[str, ...] = (),
    ) -> ProposedVerdict:
        """Propose an outcome. The verdict still has to survive the gate, with no shortcut."""
        return ProposedVerdict(
            work_key=work_key,
            outcome_class=outcome_class,
            reason_code=reason_code,
            confidence=confidence,
            rationale=rationale,
            cited_row_refs=tuple(cited_row_refs),
            features=self.compute_features(work_key),
            policy_version=self.policy_version,
            adjudicator=self.adjudicator,
        )

    def escalate(
        self, work_key: str, recommendation: str, evidence_refs: tuple[str, ...] = ()
    ) -> QueueItem:
        item = QueueItem(
            work_key=work_key,
            recommendation=recommendation,
            evidence_refs=tuple(evidence_refs),
        )
        if self.queue is not None:
            self.queue.put(item)
        self._record(
            "ESCALATE",
            work_key,
            reason="ESCALATED_TO_HUMAN_QUEUE",
            evidence=item.evidence_refs[0] if item.evidence_refs else None,
            blocking=False,
        )
        return item

    def refuse(self, work_key: str, reason_code: str, blocking_explanation: str) -> Refusal:
        """Refuse an item. There is no ``blocking=False`` to pass: a refusal blocks."""
        refusal = Refusal(
            work_key=work_key,
            reason_code=reason_code,
            blocking_explanation=blocking_explanation,
        )
        if self.queue is not None:
            self.queue.put(refusal)
        self._record("REFUSE", work_key, reason=reason_code, blocking=True)
        return refusal

    # -- the only thing that moves money -------------------------------------

    def post_matched_entry(self, match_id: MatchId) -> JournalEntry:
        """Post the entry derived from a persisted, evidenced match.

        One parameter, and it is a :class:`MatchId`. There is no amount, no account, no work
        key and no override. I1 is enforced before anything is built: a ``MatchId`` that does
        not resolve to a persisted, evidenced match raises and nothing is written.
        """
        if not isinstance(match_id, MatchId):
            raise TypeError(
                f"post_matched_entry takes a MatchId, not {type(match_id).__name__}; an "
                "arbitrary identifier is not a match"
            )
        match = require_admissible_match(match_id, self.matches)
        entry = build_entry(match)
        self._record(
            "POST",
            match.work_key,
            reason="POSTED_FROM_MATCH",
            evidence=match.evidence_ref,
            blocking=False,
            features={
                "match_id": str(match.match_id),
                "debits": format(entry.debits.amount, "f"),
                "credits": format(entry.credits.amount, "f"),
                "currency": entry.currency,
                "pairs": len(entry.pairs),
            },
        )
        return entry

    # -- audit ---------------------------------------------------------------

    def _record(
        self,
        action: str,
        work_key: str,
        *,
        reason: str,
        evidence: str | None = None,
        blocking: bool = False,
        features: dict[str, Any] | None = None,
    ) -> None:
        """Every tool call that changes the world leaves a hash-chained event behind."""
        if self.log is None:
            return
        self.log.append(
            actor=self.actor,
            action=action,
            work_key=work_key,
            policy=self.policy_version,
            reason=reason,
            evidence=evidence,
            blocking=blocking,
            features=features or {},
        )
