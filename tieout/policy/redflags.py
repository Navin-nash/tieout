"""AS 2401 paragraph .61 fraud-risk criteria applied against our own journal entries.

SPEC section 4: Tieout runs the PCAOB's fraud-test criteria against the journal entries it
proposes itself and escalates any that trip them. PCAOB AS 2401 paragraph .61 names the forced
balancing entry profile auditors must fraud-test for management override:
1. round_number_amount: unusual/round-number amounts (multiples of 100/1000).
2. seldom_used_account: entries made to seldom-used or unusual accounts (suspense, clearing).
3. post_close_timing: entries made at period-end, post-close, or after accounting cut-off.
4. unusual_initiator: entries made by unrecognized, unusual, or unauthorized initiators.
5. no_supporting_explanation: entries recorded with little, boilerplate, or no explanation.

The PCAOB warns that override risk is not limited to manual entries -- automated entries receive
more scrutiny, not less.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from tieout.policy.schema import JE_RED_FLAGS, Amount, FrozenModel

# Standard round number base: $1,000 or $100 with zero cents
ROUND_THRESHOLD = Decimal("100.00")


class ProposedJournalEntry(FrozenModel):
    """A proposed journal entry evaluated against AS 2401 fraud criteria.

    Carries the entry attributes and contextual signals needed to assess whether the entry
    resembles a forced plug or management override entry.
    """

    entry_id: str = Field(min_length=1)
    amount: Amount
    account: str = Field(min_length=1)
    initiator: str = Field(min_length=1)
    explanation: str = ""
    effective_date: date

    # Contextual flags & metadata
    period_end_date: date | None = None
    is_post_close: bool = False
    is_seldom_used: bool = False
    account_usage_count: int | None = None
    authorized_initiators: tuple[str, ...] | None = None
    posted_at: datetime | None = None


class FiredRedFlag(FrozenModel):
    """A single AS 2401 red flag that fired, along with human-readable rationale."""

    flag: str
    explanation: str


class RedFlagAssessment(FrozenModel):
    """The complete result of evaluating a proposed journal entry against AS 2401 criteria."""

    entry_id: str
    flags: tuple[FiredRedFlag, ...]
    has_red_flags: bool
    explanation: str

    @property
    def flag_names(self) -> tuple[str, ...]:
        return tuple(f.flag for f in self.flags)


# --- The 5 Red Flag Predicates ------------------------------------------------------------


def _is_round_number(amount: Decimal) -> bool:
    """True if non-zero amount has no cents and is an exact multiple of 100 or 1,000."""
    abs_amt = abs(amount)
    if abs_amt < ROUND_THRESHOLD:
        return False
    # Check if whole dollar and divisible by 100
    return abs_amt % Decimal("100") == Decimal("0")


def check_round_number_amount(entry: ProposedJournalEntry) -> str | None:
    """AS 2401 .61: entries containing round numbers (e.g., exact hundreds or thousands)."""
    if _is_round_number(entry.amount):
        return (
            f"entry amount {entry.amount} is a round number (divisible by $100 with no cents); "
            "AS 2401 .61 flags round-number adjustments for potential management override or plug"
        )
    return None


def check_seldom_used_account(entry: ProposedJournalEntry) -> str | None:
    """AS 2401 .61: entries made to seldom-used, suspense, or clearing accounts."""
    if entry.is_seldom_used:
        return (
            f"account '{entry.account}' is flagged as seldom-used by the general ledger chart; "
            "AS 2401 .61 requires scrutiny of adjustments hitting low-frequency accounts"
        )
    if entry.account_usage_count is not None and entry.account_usage_count < 5:
        return (
            f"account '{entry.account}' has low historical usage ({entry.account_usage_count} "
            "prior entries); AS 2401 .61 flags entries to seldom-used accounts"
        )
    # Check common suspense / plug account nomenclature
    account_lower = entry.account.lower()
    suspense_keywords = ("suspense", "clearing", "plug", "adjustment_plug", "9999")
    if any(k in account_lower for k in suspense_keywords):
        return (
            f"account '{entry.account}' matches suspense/clearing account naming pattern; "
            "AS 2401 .61 flags forced balancing entries posted to suspense accounts"
        )
    return None


def check_post_close_timing(entry: ProposedJournalEntry) -> str | None:
    """AS 2401 .61: entries made at period end, post-close, or after cut-off dates."""
    if entry.is_post_close:
        return (
            "entry is marked as post-close; AS 2401 .61 requires heightened scrutiny for entries "
            "recorded after the period cut-off"
        )
    if entry.period_end_date is not None and entry.effective_date > entry.period_end_date:
        return (
            f"effective date {entry.effective_date} falls after period end "
            f"{entry.period_end_date}; AS 2401 .61 flags post-close timing"
        )
    return None


def check_unusual_initiator(entry: ProposedJournalEntry) -> str | None:
    """AS 2401 .61: entries made by unusual or unauthorized initiators."""
    if entry.authorized_initiators is not None:
        if entry.initiator not in entry.authorized_initiators:
            return (
                f"initiator '{entry.initiator}' is not in authorized initiators list "
                f"({list(entry.authorized_initiators)}); AS 2401 .61 flags unusual users"
            )
    # Check for empty or generic unauthenticated initiators
    if entry.initiator.strip().lower() in ("unknown", "system", "anonymous", ""):
        return (
            f"initiator '{entry.initiator}' is unauthenticated or generic; "
            "AS 2401 .61 requires identifiable initiating principal"
        )
    return None


def check_no_supporting_explanation(entry: ProposedJournalEntry) -> str | None:
    """AS 2401 .61: entries made with little or no explanation or supporting documentation."""
    clean_explanation = entry.explanation.strip()
    if not clean_explanation:
        return (
            "entry has no supporting explanation; "
            "AS 2401 .61 flags entries lacking business rationale"
        )
    # Check for boilerplate trivial descriptions (< 10 chars or single word like 'plug', 'adjust')
    if len(clean_explanation) < 10:
        trivial_words = ("plug", "adjust", "rec", "misc", "balancing", "temp", "entry")
        if clean_explanation.lower() in trivial_words:
            return (
                f"explanation '{clean_explanation}' is trivial boilerplate; "
                "AS 2401 .61 requires substantive explanation of the underlying business reason"
            )
    return None


_PREDICATES = {
    "round_number_amount": check_round_number_amount,
    "seldom_used_account": check_seldom_used_account,
    "post_close_timing": check_post_close_timing,
    "unusual_initiator": check_unusual_initiator,
    "no_supporting_explanation": check_no_supporting_explanation,
}
assert tuple(_PREDICATES) == JE_RED_FLAGS, "predicate table drifted from JE_RED_FLAGS"


def evaluate_red_flags(
    entry: ProposedJournalEntry,
    enabled_flags: tuple[str, ...] = JE_RED_FLAGS,
) -> tuple[FiredRedFlag, ...]:
    """Evaluate a proposed journal entry against the specified AS 2401 red flags."""
    unknown = [f for f in enabled_flags if f not in _PREDICATES]
    if unknown:
        raise ValueError(f"unknown red flag predicates: {unknown}")

    fired: list[FiredRedFlag] = []
    for flag in enabled_flags:
        reason = _PREDICATES[flag](entry)
        if reason is not None:
            fired.append(FiredRedFlag(flag=flag, explanation=reason))
    return tuple(fired)


def assess_red_flags(
    entry: ProposedJournalEntry,
    enabled_flags: tuple[str, ...] = JE_RED_FLAGS,
) -> RedFlagAssessment:
    """Run AS 2401 checks and wrap into a RedFlagAssessment."""
    fired = evaluate_red_flags(entry, enabled_flags)
    has_flags = bool(fired)
    if has_flags:
        explanation = (
            f"AS 2401 red flags fired ({len(fired)}): "
            + "; ".join(f"{f.flag} ({f.explanation})" for f in fired)
        )
    else:
        explanation = "no AS 2401 red flags fired; entry meets baseline fraud-test criteria"

    return RedFlagAssessment(
        entry_id=entry.entry_id,
        flags=fired,
        has_red_flags=has_flags,
        explanation=explanation,
    )
