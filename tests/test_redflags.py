"""Tests for AS 2401 paragraph .61 fraud-risk criteria self-checks on proposed journal entries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tieout.policy.redflags import (
    ProposedJournalEntry,
    assess_red_flags,
    check_no_supporting_explanation,
    check_post_close_timing,
    check_round_number_amount,
    check_seldom_used_account,
    check_unusual_initiator,
    evaluate_red_flags,
)


@pytest.fixture
def clean_entry() -> ProposedJournalEntry:
    return ProposedJournalEntry(
        entry_id="je_202601_001",
        amount=Decimal("142.37"),
        account="1010-OPERATING-CASH",
        initiator="svc:tieout-agent@v0.3.1",
        explanation="Settlement fee delta true-up for Stripe batch B-4471 per merchant contract",
        effective_date=date(2026, 1, 15),
        period_end_date=date(2026, 1, 31),
        is_post_close=False,
        is_seldom_used=False,
        account_usage_count=45,
        authorized_initiators=("svc:tieout-agent@v0.3.1", "human:controller@acme"),
    )


# --- Individual Predicate Tests -----------------------------------------------------------


def test_round_number_predicate(clean_entry: ProposedJournalEntry):
    # Clean entry ($142.37) does not fire
    assert check_round_number_amount(clean_entry) is None

    # Exact $1,000.00 fires
    entry_1000 = clean_entry.model_copy(update={"amount": Decimal("1000.00")})
    res = check_round_number_amount(entry_1000)
    assert res is not None
    assert "round number" in res

    # Exact $500.00 fires
    entry_500 = clean_entry.model_copy(update={"amount": Decimal("500.00")})
    assert check_round_number_amount(entry_500) is not None

    # $99.00 (< 100 threshold) does not fire
    entry_99 = clean_entry.model_copy(update={"amount": Decimal("99.00")})
    assert check_round_number_amount(entry_99) is None


def test_seldom_used_account_predicate(clean_entry: ProposedJournalEntry):
    # Regular operating cash does not fire
    assert check_seldom_used_account(clean_entry) is None

    # Flagged as seldom used
    entry_seldom = clean_entry.model_copy(update={"is_seldom_used": True})
    assert check_seldom_used_account(entry_seldom) is not None

    # Low usage count (< 5)
    entry_low_count = clean_entry.model_copy(update={"account_usage_count": 2})
    res = check_seldom_used_account(entry_low_count)
    assert res is not None
    assert "low historical usage" in res

    # Suspense account name
    entry_suspense = clean_entry.model_copy(update={"account": "9999-SUSPENSE-CLEARING"})
    res_susp = check_seldom_used_account(entry_suspense)
    assert res_susp is not None
    assert "suspense" in res_susp


def test_post_close_timing_predicate(clean_entry: ProposedJournalEntry):
    # Normal mid-period date does not fire
    assert check_post_close_timing(clean_entry) is None

    # Explicit is_post_close
    entry_post_close = clean_entry.model_copy(update={"is_post_close": True})
    assert check_post_close_timing(entry_post_close) is not None

    # Effective date after period end date
    entry_late = clean_entry.model_copy(
        update={"effective_date": date(2026, 2, 5), "period_end_date": date(2026, 1, 31)}
    )
    res = check_post_close_timing(entry_late)
    assert res is not None
    assert "falls after period end" in res


def test_unusual_initiator_predicate(clean_entry: ProposedJournalEntry):
    # Authorized initiator does not fire
    assert check_unusual_initiator(clean_entry) is None

    # Unauthorized initiator
    entry_unauth = clean_entry.model_copy(update={"initiator": "intern_temp"})
    res = check_unusual_initiator(entry_unauth)
    assert res is not None
    assert "not in authorized initiators list" in res

    # Generic or unknown initiator
    entry_unknown = clean_entry.model_copy(
        update={"initiator": "unknown", "authorized_initiators": None}
    )
    res_unk = check_unusual_initiator(entry_unknown)
    assert res_unk is not None
    assert "unauthenticated or generic" in res_unk


def test_no_supporting_explanation_predicate(clean_entry: ProposedJournalEntry):
    # Substantive explanation does not fire
    assert check_no_supporting_explanation(clean_entry) is None

    # Empty explanation fires
    entry_empty = clean_entry.model_copy(update={"explanation": ""})
    res_empty = check_no_supporting_explanation(entry_empty)
    assert res_empty is not None
    assert "no supporting explanation" in res_empty

    # Whitespace only
    entry_ws = clean_entry.model_copy(update={"explanation": "   \t\n"})
    assert check_no_supporting_explanation(entry_ws) is not None

    # Trivial boilerplate ('plug', 'adjust')
    entry_plug = clean_entry.model_copy(update={"explanation": "plug"})
    res_plug = check_no_supporting_explanation(entry_plug)
    assert res_plug is not None
    assert "trivial boilerplate" in res_plug


# --- Combined Evaluation & Assessment Tests -----------------------------------------------


def test_clean_entry_passes_all_checks(clean_entry: ProposedJournalEntry):
    fired = evaluate_red_flags(clean_entry)
    assert fired == ()

    assessment = assess_red_flags(clean_entry)
    assert assessment.has_red_flags is False
    assert len(assessment.flags) == 0
    assert "no AS 2401 red flags fired" in assessment.explanation


def test_suspicious_plug_entry_trips_multiple_red_flags(clean_entry: ProposedJournalEntry):
    """A forced plug entry trips round amount, suspense account, post-close, and no rationale."""
    suspicious_entry = ProposedJournalEntry(
        entry_id="je_plug_danger_01",
        amount=Decimal("5000.00"),  # Round amount
        account="9999-SUSPENSE-PLUG",  # Suspense account
        initiator="unknown_user",  # Unauthorized
        explanation="plug",  # Boilerplate
        effective_date=date(2026, 2, 2),  # Post close
        period_end_date=date(2026, 1, 31),
        is_post_close=True,
        authorized_initiators=("svc:tieout-agent@v0.3.1",),
    )

    assessment = assess_red_flags(suspicious_entry)
    assert assessment.has_red_flags is True
    assert len(assessment.flags) == 5
    assert set(assessment.flag_names) == {
        "round_number_amount",
        "seldom_used_account",
        "post_close_timing",
        "unusual_initiator",
        "no_supporting_explanation",
    }
    assert "AS 2401 red flags fired (5)" in assessment.explanation
