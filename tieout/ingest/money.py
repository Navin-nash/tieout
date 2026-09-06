"""Decimal money — no float on the path from CSV to money field."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Self

QUANT = Decimal("0.01")
ROUNDING = ROUND_HALF_UP


class FloatNotAllowedError(TypeError):
    """Raised when a float is passed anywhere near a money field."""


class CurrencyMismatchError(ValueError):
    """Raised when arithmetic mixes two currencies."""


def _to_decimal(value: str | int | Decimal) -> Decimal:
    if isinstance(value, float):
        raise FloatNotAllowedError("float must never reach a money field")
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, str):
        d = Decimal(value.strip())
    else:
        raise TypeError(f"unsupported money amount type: {type(value).__name__}")
    return d.quantize(QUANT, rounding=ROUNDING)


class Money:
    """Currency-tagged amount, quantised to 2dp HALF_UP."""

    __slots__ = ("amount", "currency")

    def __init__(self, amount: str | int | Decimal, currency: str) -> None:
        self.amount = _to_decimal(amount)
        self.currency = currency

    @classmethod
    def from_csv(cls, text: str, currency: str) -> Self:
        """Parse a CSV cell string directly — never via float."""
        return cls(Decimal(text.strip()), currency)

    def __add__(self, other: Money) -> Money:
        self._check_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.currency == other.currency and self.amount == other.amount

    def __lt__(self, other: Money) -> bool:
        self._check_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._check_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._check_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._check_currency(other)
        return self.amount >= other.amount

    def __repr__(self) -> str:
        return f"Money({self.amount!s}, {self.currency!r})"

    def _check_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"cannot combine {self.currency} and {other.currency}")


def money_sum(items: list[Money], currency: str) -> Money:
    total = Money("0", currency)
    for item in items:
        if item.currency != currency:
            raise CurrencyMismatchError(f"expected {currency}, got {item.currency} in sum")
        total = total + item
    return total


def compute_fee(gross: Money, pct: Decimal, fixed: Decimal) -> Money:
    """pct * gross + fixed, quantised HALF_UP (ReconRiver fee policy)."""
    raw = gross.amount * pct + fixed
    fee_amount = raw.quantize(QUANT, rounding=ROUNDING)
    return Money(fee_amount, gross.currency)
