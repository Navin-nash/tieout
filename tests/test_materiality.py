"""Tests for SAB 108 dual-method materiality quantification and SAB 99 qualitative overrides.

Includes SPEC section 14's test_sab108_both_methods with a concrete worked accounting example.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tieout.policy.materiality import (
    Misstatement,
    QualitativeFacts,
    assess,
)
from tieout.policy.schema import Materiality, Threshold


@pytest.fixture
def standard_materiality() -> Materiality:
    ts = datetime(2026, 1, 2, 9, 14, tzinfo=UTC)
    return Materiality(
        overall=Threshold(
            value=Decimal("750000.00"),  # $750k overall materiality (0.5% of $150M)
            basis="0.5% of planning revenue",
            set_by="controller@acme",
            set_at=ts,
            rationale="FY26 planning revenue $150M",
        ),
        performance=Threshold(
            value=Decimal("450000.00"),  # $450k performance materiality (60% of overall)
            basis="60% of overall",
            set_by="controller@acme",
            set_at=ts,
            rationale="Aggregation risk",
        ),
        clearly_trivial=Threshold(
            value=Decimal("30000.00"),  # $30k clearly-trivial floor (4% of overall)
            basis="4% of overall",
            set_by="controller@acme",
            set_at=ts,
            rationale="Trivial accumulation floor",
        ),
    )


# --- SPEC Section 14: test_sab108_both_methods --------------------------------------------


def test_sab108_both_methods(standard_materiality: Materiality):
    """SPEC section 14: Material under iron curtain but not rollover still requires adjustment.

    Worked Numeric Accounting Example:
    -----------------------------------
    Entity ACME-US has overall materiality of $750,000.00.
    In Year 1, Year 2, and Year 3, the entity failed to accrue $270,000 per year of unbilled
    software maintenance expense.
    In Year 4 (current year):
    - Current-year unbilled expense originating in Y4: $190,000.00 (Rollover effect).
    - Cumulative balance sheet understatement of accrued liabilities at Y4 year-end:
      $270k (Y1) + $270k (Y2) + $270k (Y3) + $190k (Y4) = $1,000,000.00 (Iron Curtain effect).

    Evaluation under SAB 108:
    - Rollover method: $190,000 < $750,000 threshold -> NOT material under rollover.
    - Iron curtain method: $1,000,000 >= $750,000 threshold -> MATERIAL under iron curtain.
    - Conclusion: SAB 108 mandates adjustment because it is material under EITHER approach.
    """
    misstatement = Misstatement(
        work_key="adj_accrued_maintenance_cum_y4",
        rollover_amount=Decimal("190000.00"),
        iron_curtain_amount=Decimal("1000000.00"),
        description="Cumulative 4-year unrecorded maintenance expense accrual",
    )

    result = assess(misstatement, standard_materiality)

    assert result.rollover_material is False
    assert result.iron_curtain_material is True
    assert result.quantitatively_material is True
    assert result.requires_adjustment is True
    assert result.clearly_trivial is False
    assert "material under iron curtain" in result.explanation
    assert "SAB 108 requires adjustment when either method is material" in result.explanation


def test_sab108_material_under_rollover_only(standard_materiality: Materiality):
    """A case material under rollover (current income statement) but immaterial on balance sheet."""
    # Current year hit by $800k, while cumulative BS net error is $200k
    misstatement = Misstatement(
        work_key="adj_rev_reversal_err",
        rollover_amount=Decimal("800000.00"),
        iron_curtain_amount=Decimal("200000.00"),
        description="Current-year revenue reversal timing error",
    )

    result = assess(misstatement, standard_materiality)

    assert result.rollover_material is True
    assert result.iron_curtain_material is False
    assert result.quantitatively_material is True
    assert result.requires_adjustment is True
    assert "material under rollover" in result.explanation


def test_sab108_material_under_both(standard_materiality: Materiality):
    """A large misstatement material under both methods."""
    misstatement = Misstatement(
        work_key="adj_major_unrecorded_payable",
        rollover_amount=Decimal("1200000.00"),
        iron_curtain_amount=Decimal("1200000.00"),
        description="Unrecorded vendor invoices",
    )

    result = assess(misstatement, standard_materiality)

    assert result.rollover_material is True
    assert result.iron_curtain_material is True
    assert result.quantitatively_material is True
    assert result.requires_adjustment is True
    assert "material under rollover and iron curtain" in result.explanation


# --- SAB 99 Qualitative Overrides Tests ----------------------------------------------------


def test_sab99_crosses_covenant_threshold(standard_materiality: Materiality):
    """SAB 99: An adjustment of $5,000 (well below $750k) that eliminates covenant headroom."""
    misstatement = Misstatement(
        work_key="adj_interest_charge",
        rollover_amount=Decimal("5000.00"),
        iron_curtain_amount=Decimal("5000.00"),
    )
    facts = QualitativeFacts(covenant_headroom=Decimal("4000.00"))

    result = assess(misstatement, standard_materiality, facts)

    assert result.quantitatively_material is False
    assert result.requires_adjustment is True
    assert "crosses_covenant_threshold" in result.qualitative_factor_names
    assert "SAB 99 qualitative factors apply regardless of amount" in result.explanation


def test_sab99_changes_sign_income_to_loss(standard_materiality: Materiality):
    """SAB 99: An adjustment turning reported positive net income of $2,000 into a net loss."""
    misstatement = Misstatement(
        work_key="adj_bad_debt_expense",
        rollover_amount=Decimal("3500.00"),
        iron_curtain_amount=Decimal("3500.00"),
    )
    facts = QualitativeFacts(income_before=Decimal("2000.00"))

    result = assess(misstatement, standard_materiality, facts)

    assert result.quantitatively_material is False
    assert result.requires_adjustment is True
    assert "changes_sign_income_to_loss" in result.qualitative_factor_names


def test_sab99_masks_trend_reversal(standard_materiality: Materiality):
    """SAB 99: An adjustment masking a reversal in earnings growth trend."""
    # Prior was 100, current reported before adj is 105 (positive trend +5)
    # Adjustment is 10 -> corrected current is 95 (negative trend -5 compared to prior 100)
    misstatement = Misstatement(
        work_key="adj_revenue_cutoff",
        rollover_amount=Decimal("10.00"),
        iron_curtain_amount=Decimal("10.00"),
    )
    facts = QualitativeFacts(
        trend_prior=Decimal("100.00"),
        trend_current_before=Decimal("105.00"),
    )

    result = assess(misstatement, standard_materiality, facts)

    assert result.quantitatively_material is False
    assert result.requires_adjustment is True
    assert "masks_trend_reversal" in result.qualitative_factor_names


def test_sab99_declared_factors(standard_materiality: Materiality):
    """SAB 99: Test related-party, compensation, and unlawful transaction declared factors."""
    misstatement = Misstatement(
        work_key="adj_misc",
        rollover_amount=Decimal("100.00"),
        iron_curtain_amount=Decimal("100.00"),
    )

    # 1. Related party
    res1 = assess(
        misstatement,
        standard_materiality,
        QualitativeFacts(related_party_counterparty=True),
    )
    assert "related_party_counterparty" in res1.qualitative_factor_names
    assert res1.requires_adjustment is True

    # 2. Affects management compensation
    res2 = assess(
        misstatement,
        standard_materiality,
        QualitativeFacts(affects_management_compensation=True),
    )
    assert "affects_management_compensation" in res2.qualitative_factor_names
    assert res2.requires_adjustment is True

    # 3. Conceals unlawful transaction
    res3 = assess(
        misstatement,
        standard_materiality,
        QualitativeFacts(conceals_unlawful_transaction=True),
    )
    assert "conceals_unlawful_transaction" in res3.qualitative_factor_names
    assert res3.requires_adjustment is True


# --- Clearly Trivial Floor and Immaterial Tests -------------------------------------------


def test_clearly_trivial_item(standard_materiality: Materiality):
    """Amounts below clearly trivial ($30k) with no qualitative factor do not require adjustment."""
    misstatement = Misstatement(
        work_key="adj_tiny_rounding",
        rollover_amount=Decimal("250.00"),
        iron_curtain_amount=Decimal("250.00"),
    )

    result = assess(misstatement, standard_materiality)

    assert result.quantitatively_material is False
    assert result.requires_adjustment is False
    assert result.clearly_trivial is True
    assert "clearly trivial" in result.explanation


def test_immaterial_unadjusted_difference(standard_materiality: Materiality):
    """Amounts between clearly trivial ($30k) and overall ($750k) without qualitative factor."""
    misstatement = Misstatement(
        work_key="adj_medium_break",
        rollover_amount=Decimal("120000.00"),
        iron_curtain_amount=Decimal("120000.00"),
    )

    result = assess(misstatement, standard_materiality)

    assert result.quantitatively_material is False
    assert result.requires_adjustment is False
    assert result.clearly_trivial is False
    assert "not material" in result.explanation
