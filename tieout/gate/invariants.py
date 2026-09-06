"""Invariants I1-I4, asserted in code -- SPEC section 6.

Each invariant is enforced primarily by a *shape* -- a type signature, an absent parameter,
an ordering -- and these functions are the second line: the runtime assertion that says so out
loud, and the thing ``tests/test_invariants.py`` and the close gate both call.

**I1 -- no posting without an admissible match.** Shape: ``post_matched_entry(match_id: MatchId)``
takes no amount and no account. Assertion: :func:`require_admissible_match`.

**I2 -- debits equal credits by construction.** Shape: the journal builder emits balanced pairs
and has no amount parameter. Assertion: :func:`require_balanced`.

**I3 -- ambiguity never resolves to a pick.** Shape: a gate precondition, checked before
tiering. Assertion: :func:`require_unambiguous`.

**I4 -- a period with open REFUSE items cannot close.** Shape: the close function has no
``force`` parameter. Assertions: :func:`assert_no_force_parameter`,
:func:`require_no_open_refusals`.

Everything here is duck-typed on purpose: this module must be importable by the close gate and
the tool surface without importing either, and without importing the match or policy layers.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from typing import Any, Protocol

#: Parameter names that would reintroduce an override path. I4 has no override in code, so a
#: close function carrying any of these is a defect regardless of what it does with them.
OVERRIDE_PARAMETER_NAMES = frozenset({"force", "override", "ignore_refusals", "skip_gate"})


class InvariantViolation(AssertionError):
    """A breach of I1-I4. An ``AssertionError`` subclass so it reads as what it is, but it is
    raised explicitly and never compiled away by ``python -O``."""

    def __init__(self, invariant: str, message: str) -> None:
        super().__init__(f"{invariant}: {message}")
        self.invariant = invariant


class MatchLookup(Protocol):
    """The one thing the gate needs from a persisted match store."""

    def get(self, match_id: Any) -> Any | None: ...


# -- I1 -----------------------------------------------------------------------


def require_admissible_match(match_id: Any, store: MatchLookup) -> Any:
    """Resolve ``match_id`` to a persisted, evidenced match, or refuse to proceed.

    "Evidenced" is not decorative: a match with no evidence reference cannot be shown to a
    reviewer, so it is not admissible and nothing may be posted against it.
    """
    match = store.get(match_id)
    if match is None:
        raise InvariantViolation(
            "I1", f"{match_id!r} does not resolve to a persisted match; nothing may be posted"
        )
    if not getattr(match, "evidence_ref", None):
        raise InvariantViolation(
            "I1", f"{match_id!r} resolves to a match carrying no evidence pack reference"
        )
    return match


# -- I2 -----------------------------------------------------------------------


def require_balanced(entry: Any) -> Any:
    """Assert an entry's debits equal its credits.

    By construction this can never fail -- the builder emits balanced pairs and has no amount
    parameter, so there is no way to express an imbalance. The check exists so that if someone
    ever adds one, it fails here, loudly, rather than in a general ledger.
    """
    debits, credits = entry.debits, entry.credits
    if debits != credits:
        raise InvariantViolation(
            "I2", f"journal entry does not balance: debits {debits!r} != credits {credits!r}"
        )
    return entry


# -- I3 -----------------------------------------------------------------------


def require_unambiguous(candidate_count: int) -> None:
    """Two or more admissible candidates within tolerance is a refusal, never a pick."""
    if candidate_count >= 2:
        raise InvariantViolation(
            "I3",
            f"{candidate_count} candidates within tolerance; ambiguity refuses and never picks",
        )


# -- I4 -----------------------------------------------------------------------


def assert_no_force_parameter(func: Any) -> None:
    """Introspect a callable and assert it exposes no override parameter.

    Called on the close gate's period-close function. Introspection rather than a call,
    because the point is that the *signature* offers no such option: a caller reading the API
    must find nothing to reach for.
    """
    offending = sorted(set(inspect.signature(func).parameters) & OVERRIDE_PARAMETER_NAMES)
    if offending:
        raise InvariantViolation(
            "I4",
            f"{getattr(func, '__qualname__', func)!r} exposes override parameter(s) "
            f"{offending}; no override path exists in code",
        )


def require_no_open_refusals(dispositions: Iterable[Any]) -> None:
    """A period holding any blocking disposition cannot close. There is no bypass argument."""
    blocking = [d for d in dispositions if getattr(d, "blocking", False)]
    if blocking:
        keys = sorted(str(getattr(d.verdict, "work_key", "?")) for d in blocking)
        raise InvariantViolation(
            "I4",
            f"{len(blocking)} open REFUSE item(s) block the close: {keys}",
        )


# -- The absences (SPEC section 7) --------------------------------------------


def assert_absent(namespace: Any, names: Iterable[str]) -> None:
    """Assert none of ``names`` exists on a module or class.

    The absence is the feature. This is the check that fails when someone helpfully adds
    ``create_adjusting_entry`` back.
    """
    present = sorted(name for name in names if hasattr(namespace, name))
    if present:
        raise InvariantViolation(
            "I1/I2",
            f"{getattr(namespace, '__name__', namespace)} exposes {present}; these functions "
            "do not exist in this system by design (SPEC section 7)",
        )
