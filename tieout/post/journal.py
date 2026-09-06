"""Journal construction from a ``MatchId`` -- SPEC section 7, invariants I1 and I2.

Read :func:`build_entry`'s signature. It takes a persisted match and nothing else. There is
no amount parameter here, and none on ``ToolSurface.post_matched_entry`` either, because
**amounts are derived from the matched source rows**.

The derivation emits :class:`BalancedPair` values -- one debit account, one credit account, one
amount -- and an entry is a tuple of them. Expanding a pair yields exactly one DR line and one
CR line of that same amount, so the two side totals cannot diverge. An unbalanced journal entry
is not rejected by a check; it cannot be constructed, because there is no API that emits a
single unpaired line. Compare VynFi's GL fixture, which ships 353 deliberately unbalanced JEs
precisely because that is a real-world failure mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from tieout.gate.invariants import InvariantViolation, require_balanced
from tieout.ingest.money import Money, money_sum
from tieout.ingest.schema import BankEntry, LedgerEntry, ProcessorEvent

#: Chart-of-accounts constants. Deliberately not configurable from the agent's side: a
#: settable account is another surface on which to hide a difference.
ACCOUNT_CASH = "1000-CASH-CLEARING"
ACCOUNT_RECEIVABLE = "1200-ACCOUNTS-RECEIVABLE"
ACCOUNT_PROCESSOR_FEES = "6100-PROCESSOR-FEES"


@dataclass(frozen=True, slots=True)
class MatchId:
    """An opaque handle on a persisted match. Deliberately not a ``str``.

    A bare string identifier means any string is a candidate argument, and
    ``post_matched_entry("whatever")`` is a call somebody's agent will eventually make. With a
    distinct type that call is a ``TypeError`` before it reaches any logic -- and even a
    well-formed :class:`MatchId` is worthless unless it resolves in the store (I1).
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError(f"a match id must be a non-empty string, got {self.value!r}")

    def __str__(self) -> str:
        return self.value


FROZEN = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


class PersistedMatch(BaseModel):
    """A match that has been written down, with the rows it was made from and its evidence.

    ``evidence_ref`` is required, not optional: it is the ``ev_sha256:...`` id of the evidence
    pack (:mod:`tieout.audit.evidence`). A match nobody can show is not admissible.
    """

    model_config = FROZEN

    match_id: MatchId
    work_key: str
    evidence_ref: str = Field(min_length=1)
    ledger: tuple[LedgerEntry, ...] = ()
    processor: tuple[ProcessorEvent, ...] = ()
    bank: tuple[BankEntry, ...] = ()


class MatchStore(Protocol):
    """The persistence surface the posting path needs.

    This is the adapter seam onto :mod:`tieout.match`: when that package lands its own store,
    it satisfies this protocol and nothing in ``tieout/post`` changes. Note what the protocol
    does *not* have -- ``put`` is not on it, so the posting path can read matches and never
    mint one.
    """

    def get(self, match_id: MatchId) -> PersistedMatch | None: ...


class InMemoryMatchStore:
    """A dict of persisted matches. Enough for a run and for the tests; swap for the match
    layer's store when it exists."""

    def __init__(self, matches: dict[MatchId, PersistedMatch] | None = None) -> None:
        self._matches: dict[MatchId, PersistedMatch] = dict(matches or {})

    def put(self, match: PersistedMatch) -> MatchId:
        self._matches[match.match_id] = match
        return match.match_id

    def get(self, match_id: MatchId) -> PersistedMatch | None:
        return self._matches.get(match_id)


class BalancedPair(BaseModel):
    """One debit and one credit of the same amount. The only unit a journal is built from."""

    model_config = FROZEN

    debit_account: str
    credit_account: str
    amount: Money
    memo: str = ""


class JournalEntry(BaseModel):
    """An entry derived from a match. Balanced by construction; see :attr:`pairs`."""

    model_config = FROZEN

    match_id: MatchId
    work_key: str
    evidence_ref: str
    currency: str
    pairs: tuple[BalancedPair, ...] = Field(min_length=1)

    def lines(self) -> tuple[tuple[str, str, Money], ...]:
        """The entry expanded into ``(side, account, amount)`` lines, as a ledger sees it.

        Each pair yields exactly one DR and one CR of the same amount. This is the only
        expansion, which is why the two side totals cannot diverge.
        """
        return tuple(
            line
            for pair in self.pairs
            for line in (
                ("DR", pair.debit_account, pair.amount),
                ("CR", pair.credit_account, pair.amount),
            )
        )

    def _side_total(self, side: str) -> Money:
        return money_sum(
            [amount for line_side, _, amount in self.lines() if line_side == side], self.currency
        )

    @property
    def debits(self) -> Money:
        return self._side_total("DR")

    @property
    def credits(self) -> Money:
        return self._side_total("CR")

    @property
    def balances(self) -> bool:
        return self.debits == self.credits


def _currency_of(match: PersistedMatch) -> str:
    for row in (*match.processor, *match.ledger, *match.bank):
        amount = getattr(row, "gross", None) or getattr(row, "amount", None)
        amount = amount if amount is not None else getattr(row, "credited", None)
        if amount is not None:
            return str(amount.currency)
    raise InvariantViolation(
        "I1", f"match {match.match_id!r} carries no source rows to derive amounts from"
    )


def _pairs_from(match: PersistedMatch) -> tuple[BalancedPair, ...]:
    """Derive the entry's lines from the matched rows. No caller supplies an amount.

    Card settlement decomposes into two balanced pairs per processor event -- cash against the
    receivable for the net, fees against the receivable for the fee -- which together clear the
    gross. Where there is no processor leg the ledger amount clears directly. The bank rows are
    the evidence that the cash arrived; they contribute no amount of their own, because a
    second independent amount source is exactly how a difference gets absorbed.
    """
    pairs: list[BalancedPair] = []
    for event in match.processor:
        pairs.append(
            BalancedPair(
                debit_account=ACCOUNT_CASH,
                credit_account=ACCOUNT_RECEIVABLE,
                amount=event.net,
                memo=f"settlement of {event.order_key} via batch {event.batch_key}",
            )
        )
        if event.fee.amount:
            pairs.append(
                BalancedPair(
                    debit_account=ACCOUNT_PROCESSOR_FEES,
                    credit_account=ACCOUNT_RECEIVABLE,
                    amount=event.fee,
                    memo=f"processor fee on {event.order_key}",
                )
            )
    if not match.processor:
        for entry in match.ledger:
            pairs.append(
                BalancedPair(
                    debit_account=ACCOUNT_CASH,
                    credit_account=ACCOUNT_RECEIVABLE,
                    amount=entry.amount,
                    memo=f"settlement of {entry.order_key}",
                )
            )
    if not pairs:
        raise InvariantViolation(
            "I1", f"match {match.match_id!r} carries no source rows to derive amounts from"
        )
    return tuple(pairs)


def build_entry(match: PersistedMatch) -> JournalEntry:
    """Build the journal entry for a persisted match.

    Note the signature: one argument, and it is not an amount. This is I2's enforcement point.
    """
    entry = JournalEntry(
        match_id=match.match_id,
        work_key=match.work_key,
        evidence_ref=match.evidence_ref,
        currency=_currency_of(match),
        pairs=_pairs_from(match),
    )
    return require_balanced(entry)
