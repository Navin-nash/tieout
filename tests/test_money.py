"""Money invariants — no float, HALF_UP, currency guards."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tieout.ingest.manifest import fee_policy_from_manifest
from tieout.ingest.money import (
    CurrencyMismatchError,
    FloatNotAllowedError,
    Money,
    compute_fee,
    money_sum,
)

pytestmark = pytest.mark.filterwarnings("ignore")


def test_money_never_float() -> None:
    with pytest.raises(FloatNotAllowedError):
        Money(1.23, "USD")

    m = Money.from_csv("1278.74", "USD")
    assert isinstance(m.amount, Decimal)
    assert not isinstance(m.amount, float)


def test_rounding_half_up() -> None:
    assert Money("2.674", "USD").amount == Decimal("2.67")
    assert Money("2.675", "USD").amount == Decimal("2.68")
    assert Money("2.685", "USD").amount == Decimal("2.69")


def test_cross_currency_raises() -> None:
    a = Money("10.00", "USD")
    b = Money("10.00", "EUR")
    with pytest.raises(CurrencyMismatchError):
        a + b
    with pytest.raises(CurrencyMismatchError):
        a - b
    with pytest.raises(CurrencyMismatchError):
        a < b


def test_sum_negate_compare() -> None:
    a = Money("1.00", "USD")
    b = Money("2.50", "USD")
    total = money_sum([a, b], "USD")
    assert total == Money("3.50", "USD")
    assert -a == Money("-1.00", "USD")
    assert a < b
    assert b > a


def test_fee_matches_manifest_policy() -> None:
    policy = fee_policy_from_manifest(
        {
            "fee_policy": {
                "percentage_rate": "2.90%",
                "fixed_charge": 0.30,
                "rounding_mode": "HALF_UP",
            }
        }
    )
    gross = Money("100.00", "USD")
    fee = compute_fee(gross, policy.percentage_rate, policy.fixed_charge)
    assert fee == Money("3.20", "USD")

    gross2 = Money("10.33", "EUR")
    fee2 = compute_fee(gross2, policy.percentage_rate, policy.fixed_charge)
    assert fee2 == Money("0.60", "EUR")
