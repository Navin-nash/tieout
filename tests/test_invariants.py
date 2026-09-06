"""Invariants I1-I4 and the absences -- SPEC sections 6, 7, 9 and 14.

The most important file in this repo. Every test here fails loudly if the thesis breaks, and
several of them fail if someone *adds* something: a ``force`` parameter, a fifth disposition,
``create_adjusting_entry``. That is deliberate. The absence is the feature, so the absence is
what is asserted.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tieout.audit.events import EventLog
from tieout.gate import decide as decide_module
from tieout.gate import tiers as tiers_module
from tieout.gate.decide import (
    TRIGGER_BATCH_INCOMPLETE,
    TRIGGER_NO_ADMISSIBLE_MATCH,
    TRIGGER_TWO_CANDIDATES,
    Disposition,
    decide,
    read_verdict,
)
from tieout.gate.invariants import (
    InvariantViolation,
    assert_absent,
    assert_no_force_parameter,
    require_no_open_refusals,
    require_unambiguous,
)
from tieout.gate.tiers import (
    Action,
    GatePolicy,
    PolicyIncomplete,
    Tier,
    is_sampled,
    read_policy,
)
from tieout.ingest.money import Money
from tieout.ingest.schema import BankEntry, LedgerEntry, ProcessorEvent, SourceRowRef
from tieout.post import journal as journal_module
from tieout.post import tools as tools_module
from tieout.post.journal import (
    InMemoryMatchStore,
    MatchId,
    PersistedMatch,
    build_entry,
)
from tieout.post.tools import ALLOWED_TOOLS, ToolSurface

#: SPEC section 7's absence list, transcribed here rather than imported. A test that reads the
#: list from the module it is policing can be defeated by editing the list.
FORBIDDEN_NAMES = (
    "create_adjusting_entry",
    "force_balance",
    "write_suspense",
    "set_threshold",
    "mark_period_closed",
    "edit_source_row",
    "delete_event",
    "read_expected_reconciliation",
)

#: SPEC section 3's eleven outcome classes.
OUTCOME_CLASSES = (
    "MATCHED",
    "REFUND_MATCHED",
    "PARTIAL_REFUND",
    "LATE_SETTLEMENT",
    "AMOUNT_MISMATCH",
    "FEE_MISMATCH",
    "CURRENCY_MISMATCH",
    "MISSING_PROCESSOR",
    "MISSING_INTERNAL",
    "MISSING_BANK_SETTLEMENT",
    "AMBIGUOUS_MATCH",
)

AT = datetime(2026, 1, 31, 12, 0, tzinfo=UTC)


# -- fixtures ------------------------------------------------------------------


@pytest.fixture
def policy() -> GatePolicy:
    """SPEC section 4's numbers, read as a policy rather than written into the gate."""
    return GatePolicy(
        version="2026.01-r3",
        clearly_trivial=Decimal("30000.00"),
        performance_materiality=Decimal("450000.00"),
        auto_min_confidence=0.95,
        auto_sampled_min_confidence=0.90,
        escalate_min_confidence=0.60,
        sample_rate=0.05,
    )


@pytest.fixture
def log(tmp_path) -> EventLog:
    return EventLog(tmp_path / "events.jsonl")


def verdict(
    *,
    work_key: str = "wk_1",
    outcome_class: str = "MATCHED",
    reason_code: str = "L1_EXACT_KEY_AND_AMOUNT",
    confidence: float = 0.99,
    amount_delta: str = "0.00",
    candidate_count: int = 1,
    ref_match: str = "EXACT",
    batch_completeness: str = "1.0",
    adjudicator: str = "DETERMINISTIC",
) -> dict:
    """A Verdict in SPEC section 3's shape, as a plain mapping.

    Deliberately not one of the gate's own models: the gate reads the match layer's Verdict
    through a structural adapter, and this fixture is the proof that the adapter works on a
    foreign shape.
    """
    return {
        "work_key": work_key,
        "outcome_class": outcome_class,
        "reason_code": reason_code,
        "confidence": confidence,
        "rationale": "deterministic cascade",
        "policy_version": "2026.01-r3",
        "adjudicator": adjudicator,
        "features": {
            "amount_delta": Money(amount_delta, "USD"),
            "fee_explained_delta": Money("0.00", "USD"),
            "date_delta_days": 0,
            "currency_mismatch": False,
            "ref_match": ref_match,
            "candidate_count": candidate_count,
            "batch_completeness": Decimal(batch_completeness),
        },
    }


def _ref(row: int) -> SourceRowRef:
    return SourceRowRef(file="processor_transactions.csv", row_number=row)


def _processor(order: str, gross: str, fee: str, net: str, currency: str = "USD") -> ProcessorEvent:
    return ProcessorEvent(
        id=f"pe_{order}",
        order_key=order,
        event_type="SETTLEMENT",
        event_time=AT,
        gross=Money(gross, currency),
        fee=Money(fee, currency),
        net=Money(net, currency),
        batch_key="batch_1",
        status="SETTLED",
        source_row_ref=_ref(2),
    )


def _ledger(order: str, amount: str, currency: str = "USD") -> LedgerEntry:
    return LedgerEntry(
        id=f"le_{order}",
        order_key=order,
        occurred_at=AT,
        amount=Money(amount, currency),
        currency=currency,
        status="CAPTURED",
        method="card",
        source_row_ref=SourceRowRef(file="internal_transactions.csv", row_number=3),
    )


def _bank() -> BankEntry:
    return BankEntry(
        id="be_1",
        batch_key="batch_1",
        booked_at=AT,
        credited=Money("970.00", "USD"),
        reference="ref",
        description="deposit",
        source_row_ref=SourceRowRef(file="bank_settlements.csv", row_number=4),
    )


#: One row shape per outcome class, including the awkward ones: refunds are negative, partial
#: refunds do not divide evenly, the currency-mismatch case is not USD, and three classes have
#: a missing leg entirely.
MATCH_SHAPES: dict[str, PersistedMatch] = {
    "MATCHED": PersistedMatch(
        match_id=MatchId("m_matched"),
        work_key="wk_matched",
        evidence_ref="ev_sha256:aaa",
        ledger=(_ledger("o1", "1000.00"),),
        processor=(_processor("o1", "1000.00", "29.30", "970.70"),),
        bank=(_bank(),),
    ),
    "REFUND_MATCHED": PersistedMatch(
        match_id=MatchId("m_refund"),
        work_key="wk_refund",
        evidence_ref="ev_sha256:bbb",
        ledger=(_ledger("o2", "-1000.00"),),
        processor=(_processor("o2", "-1000.00", "-29.30", "-970.70"),),
    ),
    "PARTIAL_REFUND": PersistedMatch(
        match_id=MatchId("m_partial"),
        work_key="wk_partial",
        evidence_ref="ev_sha256:ccc",
        processor=(_processor("o3", "-333.33", "-9.97", "-323.36"),),
    ),
    "LATE_SETTLEMENT": PersistedMatch(
        match_id=MatchId("m_late"),
        work_key="wk_late",
        evidence_ref="ev_sha256:ddd",
        processor=(_processor("o4", "77.77", "2.56", "75.21"),),
    ),
    "AMOUNT_MISMATCH": PersistedMatch(
        match_id=MatchId("m_amount"),
        work_key="wk_amount",
        evidence_ref="ev_sha256:eee",
        ledger=(_ledger("o5", "500.01"),),
        processor=(_processor("o5", "500.00", "14.80", "485.20"),),
    ),
    "FEE_MISMATCH": PersistedMatch(
        match_id=MatchId("m_fee"),
        work_key="wk_fee",
        evidence_ref="ev_sha256:fff",
        processor=(_processor("o6", "250.00", "9.99", "240.01"),),
    ),
    "CURRENCY_MISMATCH": PersistedMatch(
        match_id=MatchId("m_ccy"),
        work_key="wk_ccy",
        evidence_ref="ev_sha256:ggg",
        processor=(_processor("o7", "100.00", "3.20", "96.80", currency="EUR"),),
    ),
    "MISSING_PROCESSOR": PersistedMatch(
        match_id=MatchId("m_missing_proc"),
        work_key="wk_missing_proc",
        evidence_ref="ev_sha256:hhh",
        ledger=(_ledger("o8", "42.42"),),
    ),
    "MISSING_INTERNAL": PersistedMatch(
        match_id=MatchId("m_missing_int"),
        work_key="wk_missing_int",
        evidence_ref="ev_sha256:iii",
        processor=(_processor("o9", "12.34", "0.66", "11.68"),),
    ),
    "MISSING_BANK_SETTLEMENT": PersistedMatch(
        match_id=MatchId("m_missing_bank"),
        work_key="wk_missing_bank",
        evidence_ref="ev_sha256:jjj",
        ledger=(_ledger("o10", "888.88"),),
        processor=(_processor("o10", "888.88", "26.08", "862.80"),),
    ),
    "AMBIGUOUS_MATCH": PersistedMatch(
        match_id=MatchId("m_ambiguous"),
        work_key="wk_ambiguous",
        evidence_ref="ev_sha256:kkk",
        ledger=(_ledger("o11a", "100.00"), _ledger("o11b", "100.00")),
    ),
}


class _Features:
    def compute(self, work_key: str) -> dict:
        return verdict(work_key=work_key)["features"]


class _WorkItems:
    def get(self, work_key: str) -> dict | None:
        return {"work_key": work_key} if work_key.startswith("wk_") else None


def surface(log: EventLog | None = None) -> ToolSurface:
    store = InMemoryMatchStore()
    for match in MATCH_SHAPES.values():
        store.put(match)
    return ToolSurface(
        work_items=_WorkItems(),
        features=_Features(),
        matches=store,
        policy_version="2026.01-r3",
        log=log,
    )


# -- I1 ------------------------------------------------------------------------


def test_no_post_without_match(log: EventLog) -> None:
    """I1: nothing posts unless the match id resolves to a persisted, evidenced match."""
    tools = surface(log)

    # An unresolvable id: well-formed, and worthless.
    with pytest.raises(InvariantViolation) as unresolved:
        tools.post_matched_entry(MatchId("m_does_not_exist"))
    assert unresolved.value.invariant == "I1"

    # A bare string is not a match id. The type is the first line of defence.
    with pytest.raises(TypeError):
        tools.post_matched_entry("m_matched")  # type: ignore[arg-type]

    # An unevidenced match cannot even be persisted: evidence_ref is required.
    with pytest.raises(ValidationError):
        PersistedMatch(
            match_id=MatchId("m_bare"),
            work_key="wk_bare",
            evidence_ref="",
            ledger=(_ledger("o0", "1.00"),),
        )

    # Nothing was written. A rejected post leaves no trace of a posting.
    assert [event.action for event in log.read_all()] == []

    # And the happy path still works, so the test is not passing by being broken.
    entry = tools.post_matched_entry(MatchId("m_matched"))
    assert entry.balances
    assert [event.action for event in log.read_all()] == ["POST"]


def test_post_matched_entry_takes_a_match_id_and_no_amount() -> None:
    """I1/I2 read off the signature: one parameter, and it is not money."""
    params = inspect.signature(ToolSurface.post_matched_entry).parameters
    assert list(params) == ["self", "match_id"]
    assert params["match_id"].annotation == "MatchId"

    builder = inspect.signature(build_entry).parameters
    assert list(builder) == ["match"]
    assert not {"amount", "account", "difference", "plug"} & set(builder)


# -- I2 ------------------------------------------------------------------------


@pytest.mark.parametrize("outcome_class", OUTCOME_CLASSES)
def test_journal_always_balances(outcome_class: str) -> None:
    """I2: over every outcome class, entries balance to the cent, with amounts derived."""
    entry = build_entry(MATCH_SHAPES[outcome_class])
    assert entry.balances
    assert entry.debits == entry.credits
    assert entry.debits.amount == entry.credits.amount
    assert entry.debits.amount.as_tuple().exponent == -2  # to the cent
    assert entry.pairs, "an entry with no derived lines is not an entry"
    lines = entry.lines()
    assert len(lines) == 2 * len(entry.pairs)
    assert sum(side == "DR" for side, _, _ in lines) == sum(side == "CR" for side, _, _ in lines)
    # Derived, never supplied: every amount on the entry came off a matched source row.
    source_amounts = {
        row.amount.amount for row in MATCH_SHAPES[outcome_class].ledger
    } | {
        amount
        for event in MATCH_SHAPES[outcome_class].processor
        for amount in (event.net.amount, event.fee.amount)
    }
    assert {pair.amount.amount for pair in entry.pairs} <= source_amounts


def test_an_unbalanced_entry_cannot_be_constructed() -> None:
    """I2 stated as a property of the type, not of a validation step.

    A journal is a tuple of balanced pairs. There is no API that emits a single unpaired line,
    so there is no expression in this system that denotes an unbalanced entry.
    """
    pair_fields = set(journal_module.BalancedPair.model_fields)
    assert pair_fields == {"debit_account", "credit_account", "amount", "memo"}
    # One amount, spent on both sides. No second amount field to disagree with the first.
    assert sum(name.endswith("amount") for name in pair_fields) == 1
    entry_fields = set(journal_module.JournalEntry.model_fields)
    assert not {"amount", "difference", "suspense", "plug"} & entry_fields


# -- I3 ------------------------------------------------------------------------


def test_ambiguity_never_picks(policy: GatePolicy, log: EventLog) -> None:
    """I3: two candidates inside tolerance refuse, at any confidence, and nothing posts."""
    disposition = decide(
        verdict(work_key="wk_ambiguous", confidence=0.99, candidate_count=2),
        policy,
        log=log,
    )
    assert disposition.action is Action.REFUSE
    assert disposition.tier is Tier.T3
    assert disposition.blocking
    assert TRIGGER_TWO_CANDIDATES in disposition.triggers

    actions = [event.action for event in log.read_all()]
    assert actions == ["REFUSE"]
    assert "POST" not in actions, "an ambiguous item produced a posting event"
    assert log.verify().ok

    # The precondition is checked before tiering, so scoring well cannot buy a way out.
    with pytest.raises(InvariantViolation) as violation:
        require_unambiguous(2)
    assert violation.value.invariant == "I3"


def test_ambiguity_is_checked_before_tiering(policy: GatePolicy) -> None:
    """The same features that would otherwise reach T0 still refuse when ambiguous."""
    clean = decide(verdict(confidence=0.99, candidate_count=1), policy)
    assert clean.action is Action.AUTO_POST
    ambiguous = decide(verdict(confidence=0.99, candidate_count=2), policy)
    assert ambiguous.action is Action.REFUSE


def test_inadmissible_items_refuse(policy: GatePolicy) -> None:
    """No admissible match, and unexplained batch incompleteness, both refuse."""
    none_found = decide(verdict(confidence=0.99, candidate_count=0), policy)
    assert none_found.action is Action.REFUSE
    assert TRIGGER_NO_ADMISSIBLE_MATCH in none_found.triggers

    incomplete = decide(verdict(confidence=0.99, batch_completeness="0.75"), policy)
    assert incomplete.action is Action.REFUSE
    assert TRIGGER_BATCH_INCOMPLETE in incomplete.triggers

    explained = decide(
        verdict(confidence=0.99, batch_completeness="0.75"),
        policy,
        batch_incompleteness_explained=True,
    )
    assert explained.action is not Action.REFUSE


# -- I4 ------------------------------------------------------------------------


def test_cannot_close_with_refusals(policy: GatePolicy) -> None:
    """I4: an open REFUSE blocks the close, and no signature offers a way around it."""
    refused = decide(verdict(confidence=0.99, candidate_count=2), policy)
    escalated = decide(verdict(confidence=0.99, amount_delta="500000.00"), policy)
    assert refused.blocking and not escalated.blocking

    with pytest.raises(InvariantViolation) as violation:
        require_no_open_refusals([escalated, refused])
    assert violation.value.invariant == "I4"
    require_no_open_refusals([escalated])  # no refusals, no exception

    # Introspection, not a call: the point is that the API offers nothing to reach for.
    assert_no_force_parameter(require_no_open_refusals)
    assert not hasattr(ToolSurface, "mark_period_closed")

    # And the introspection itself works -- a function that did offer one is caught.
    def close_period(period: str, force: bool = False) -> None: ...

    with pytest.raises(InvariantViolation):
        assert_no_force_parameter(close_period)

    # When the close gate lands, every close/lock function it exposes is checked here too.
    if importlib.util.find_spec("tieout.close.period") is not None:
        module = importlib.import_module("tieout.close.period")
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if "close" in name or "lock" in name or "certif" in name:
                assert_no_force_parameter(func)


# -- Decision memory (SPEC section 9) -----------------------------------------


@pytest.mark.parametrize("lift", [0.0, 0.05, 0.4, 1.0, 99.0])
def test_memory_cannot_rescue_refusal(policy: GatePolicy, lift: float) -> None:
    """No quantity of prior human approvals promotes a T3 out of REFUSE.

    Precedent may accelerate a decision; it may never create admissibility. Otherwise the
    memory becomes a laundering path for the fabrication this system exists to prevent.
    """
    below_confidence = decide(verdict(confidence=0.55), policy, memory_confidence_lift=lift)
    assert below_confidence.action is Action.REFUSE

    ambiguous = decide(
        verdict(confidence=0.99, candidate_count=2), policy, memory_confidence_lift=lift
    )
    assert ambiguous.action is Action.REFUSE

    inadmissible = decide(
        verdict(confidence=0.99, outcome_class="MISSING_PROCESSOR"),
        policy,
        memory_confidence_lift=lift,
    )
    assert inadmissible.action is Action.REFUSE


def test_memory_lift_is_bounded_and_never_reaches_t0(policy: GatePolicy) -> None:
    """The lift can promote a borderline T2 into T1. It can do nothing more than that."""
    borderline = verdict(confidence=0.89, amount_delta="100.00")
    assert decide(borderline, policy).tier is Tier.T2
    assert decide(borderline, policy, memory_confidence_lift=0.05).tier is Tier.T1

    # An absurd lift is clamped to the policy bound, so it cannot leap two tiers.
    assert decide(borderline, policy, memory_confidence_lift=10.0).tier is Tier.T1

    # Even a lift that would clear the auto threshold on paper stops at T1: T0 additionally
    # requires a deterministic key match, and precedent is not a key match.
    almost_auto = verdict(confidence=0.94, amount_delta="10.00")
    assert decide(almost_auto, policy, memory_confidence_lift=0.05).tier is Tier.T1


# -- The LLM has no privileged path (SPEC section 5.5) -------------------------


@pytest.mark.parametrize("confidence", [0.10, 0.59, 0.60, 0.90, 0.95, 0.99])
@pytest.mark.parametrize("amount_delta", ["0.00", "29999.99", "30000.00", "450000.00"])
def test_llm_has_no_privileged_path(
    policy: GatePolicy, confidence: float, amount_delta: str
) -> None:
    """An LLM-adjudicated verdict is gated identically to a deterministic one."""
    dispositions = [
        decide(
            verdict(confidence=confidence, amount_delta=amount_delta, adjudicator=adjudicator),
            policy,
        )
        for adjudicator in ("DETERMINISTIC", "LLM", "HUMAN")
    ]
    signatures = {(d.tier, d.action, d.blocking, d.triggers) for d in dispositions}
    assert len(signatures) == 1, f"adjudicator changed the disposition: {signatures}"


def test_no_code_path_branches_on_the_adjudicator() -> None:
    """Structural, not behavioural: there is no branch to find, in either gate module."""
    for module in (tiers_module, decide_module):
        source = inspect.getsource(module)
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(("if ", "elif ")) and "adjudicator" in stripped:
                pytest.fail(f"{module.__name__} branches on the adjudicator: {stripped}")
    # tier_for cannot even see it.
    assert "adjudicator" not in inspect.signature(tiers_module.tier_for).parameters


# -- The absences (SPEC section 7) --------------------------------------------


@pytest.mark.parametrize("name", FORBIDDEN_NAMES)
def test_absent_functions_do_not_exist(name: str) -> None:
    """The plug and its friends are absent, not guarded. This is the whole thesis."""
    for namespace in (tools_module, journal_module, decide_module, tiers_module, ToolSurface):
        assert not hasattr(namespace, name), (
            f"{getattr(namespace, '__name__', namespace)} exposes {name!r}; SPEC section 7 says "
            "this function does not exist in this system"
        )


def test_assert_absent_catches_a_reintroduced_plug() -> None:
    """The guard itself works -- otherwise the tests above pass vacuously forever."""

    class Regressed:
        def create_adjusting_entry(self, account: str, amount: str) -> None: ...

    assert_absent(ToolSurface, FORBIDDEN_NAMES)
    with pytest.raises(InvariantViolation):
        assert_absent(Regressed, FORBIDDEN_NAMES)


def test_tool_surface_is_exactly_the_spec_list() -> None:
    """Seven tools. Not six, not eight."""
    public = {
        name
        for name, _ in inspect.getmembers(ToolSurface, inspect.isfunction)
        if not name.startswith("_")
    }
    assert public == set(ALLOWED_TOOLS)


def test_the_agent_cannot_mint_a_match() -> None:
    """The posting path reads matches and never writes one: ``put`` is not on the protocol."""
    protocol_methods = {
        name for name in vars(journal_module.MatchStore) if not name.startswith("_")
    }
    assert protocol_methods == {"get"}
    assert not hasattr(ToolSurface, "put_match")


# -- Tiering, thresholds and sampling -----------------------------------------


def test_thresholds_come_from_the_policy_not_the_gate() -> None:
    """No 0.95 / 0.90 / 0.60 in the gate. The adapter reads policy.yaml's shape."""
    parsed = {
        "version": "2026.01-r3",
        "materiality": {
            "overall": {"value": Decimal("750000.00")},
            "performance": {"value": Decimal("450000.00")},
            "clearly_trivial": {"value": Decimal("30000.00")},
        },
        "confidence_tiers": {
            "auto": {"min_confidence": 0.95},
            "auto_sampled": {"min_confidence": 0.90, "sample_rate": 0.05},
            "escalate": {"min_confidence": 0.60},
        },
    }
    gate_policy = read_policy(parsed)
    assert gate_policy.performance_materiality == Decimal("450000.00")
    assert gate_policy.auto_min_confidence == 0.95

    with pytest.raises(PolicyIncomplete):
        read_policy({"version": "x"})

    floated = {**parsed, "materiality": {**parsed["materiality"]}}
    floated["materiality"]["clearly_trivial"] = {"value": 30000.0}
    with pytest.raises(PolicyIncomplete):
        read_policy(floated)


def test_the_four_dispositions_and_no_fifth(policy: GatePolicy) -> None:
    """T0/T1/T2/T3 exactly, with SPEC section 6's predicates."""
    assert [tier.value for tier in Tier] == ["T0", "T1", "T2", "T3"]
    assert {action.value for action in Action} == {
        "AUTO_POST",
        "AUTO_SAMPLED",
        "ESCALATE",
        "REFUSE",
    }

    assert decide(verdict(confidence=0.96, amount_delta="10.00"), policy).tier is Tier.T0
    # T0 needs a deterministic key match; a partial reference match is a T1 at best.
    assert (
        decide(verdict(confidence=0.96, amount_delta="10.00", ref_match="PARTIAL"), policy).tier
        is Tier.T1
    )
    # Below clearly-trivial but above it in amount: T1.
    assert decide(verdict(confidence=0.96, amount_delta="30000.00"), policy).tier is Tier.T1
    # At or above performance materiality: escalate however confident we are.
    assert decide(verdict(confidence=0.99, amount_delta="450000.00"), policy).tier is Tier.T2
    # Below the escalate minimum: refuse.
    assert decide(verdict(confidence=0.59), policy).tier is Tier.T3


def test_red_flags_and_overrides_force_escalation(policy: GatePolicy) -> None:
    """AS 2401 red flags and SAB 99 qualitative overrides beat a high score."""
    flagged = decide(
        verdict(confidence=0.99, amount_delta="1.00"), policy, red_flags=("round_number_amount",)
    )
    assert flagged.tier is Tier.T2
    assert flagged.triggers == ("L2_AS2401_RED_FLAG:round_number_amount",)

    overridden = decide(
        verdict(confidence=0.99, amount_delta="1.00"),
        policy,
        qualitative_overrides=("related_party_counterparty",),
    )
    assert overridden.tier is Tier.T2


def test_t1_sampling_is_reproducible(policy: GatePolicy) -> None:
    """A sample nobody can reproduce is not control evidence."""
    keys = [f"wk_{n}" for n in range(2000)]
    first = {key: is_sampled(key, "run-2026-01", policy.sample_rate) for key in keys}
    second = {key: is_sampled(key, "run-2026-01", policy.sample_rate) for key in keys}
    assert first == second
    assert first != {key: is_sampled(key, "run-2026-02", policy.sample_rate) for key in keys}
    drawn = sum(first.values())
    assert 0.02 < drawn / len(keys) < 0.09, f"5% sample drew {drawn}/{len(keys)}"

    sampled_keys = [key for key, drawn_flag in first.items() if drawn_flag]
    disposition = decide(
        verdict(work_key=sampled_keys[0], confidence=0.92, amount_delta="100.00"),
        policy,
        run_seed="run-2026-01",
    )
    assert disposition.tier is Tier.T1 and disposition.sampled


# -- Every decision leaves a hash-chained event -------------------------------


def test_every_disposition_writes_one_chained_event(policy: GatePolicy, log: EventLog) -> None:
    """SPEC section 8's event shape, one per decision, chain intact."""
    cases = [
        verdict(work_key="wk_a", confidence=0.99, amount_delta="10.00"),
        verdict(work_key="wk_b", confidence=0.92, amount_delta="100.00"),
        verdict(work_key="wk_c", confidence=0.99, amount_delta="450000.00"),
        verdict(work_key="wk_d", confidence=0.99, candidate_count=2),
    ]
    dispositions = [decide(case, policy, log=log, run_seed="run-1") for case in cases]
    events = log.read_all()

    assert len(events) == len(cases)
    assert log.verify().ok
    assert [event.action for event in events] == [d.action.value for d in dispositions]
    assert events[-1].blocking is True
    assert events[-1].reason == TRIGGER_TWO_CANDIDATES
    assert events[0].policy == "2026.01-r3"
    assert events[0].actor.startswith("svc:tieout-agent@")
    assert events[0].features["amount_delta"] == "10.00"
    # No float ever reaches the canonicaliser.
    assert all(
        not isinstance(value, float)
        for event in events
        for value in event.features.values()
    )
    assert all(d.event_id for d in dispositions)


def test_disposition_is_frozen(policy: GatePolicy) -> None:
    """New objects, never mutation -- a disposition cannot be edited after the fact."""
    disposition = decide(verdict(), policy)
    assert isinstance(disposition, Disposition)
    with pytest.raises(ValidationError):
        disposition.tier = Tier.T0  # type: ignore[misc]


def test_verdict_adapter_refuses_a_float_amount() -> None:
    """Money through a float is a defect, and the gate says so rather than rounding it."""
    broken = verdict()
    broken["features"] = {**broken["features"], "amount_delta": 12.34}
    with pytest.raises(decide_module.VerdictUnreadable):
        read_verdict(broken)

    missing = verdict()
    del missing["confidence"]
    with pytest.raises(decide_module.VerdictUnreadable):
        read_verdict(missing)
