"""Aging buckets, escalation clocks and queue priority -- SPEC section 10.

Open items age into buckets of 30 / 60 / 90 / 120 days.

Escalation clocks from published close policies:
- **U. of Houston MAPP 05.04.06**: Reconciliation due within 30 working days;
  unresolved items escalated to the Controller after 30 days.
- **VA Financial Policy Ch. 1**: Suspense differences "researched, resolved, and
  explained within 60 days."
- **California SAM §8294**: AR reconciliations monthly within 30 days; records
  retained 4 years.

Priority ordering:
The queue sorts by **materiality x age**, so the largest oldest break is always first.

Write-off authority:
Negative finding from research: no public policy publishes a dollar write-off
authority threshold -- those live in internal delegation-of-authority manuals.
Tieout treats write-off authority as a policy field **with no default value**,
and refuses to act on it until set.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from tieout.audit.identity import utc_now

T = TypeVar("T")


class AgingBucket(StrEnum):
    """The standard 30 / 60 / 90 / 120 day aging buckets (SPEC section 10)."""

    DAYS_0_30 = "0-30 days"
    DAYS_31_60 = "31-60 days"
    DAYS_61_90 = "61-90 days"
    DAYS_91_120 = "91-120 days"
    DAYS_OVER_120 = "120+ days"


#: Statutory and institutional escalation clocks (SPEC section 10).
ESCALATION_POLICIES: dict[str, str] = {
    "U_OF_HOUSTON_MAPP_05_04_06": (
        "Reconciliation due within 30 working days; unresolved items escalated "
        "to the Controller after 30 days."
    ),
    "VA_FINANCIAL_POLICY_CH_1": (
        "Suspense differences researched, resolved, and explained within 60 days."
    ),
    "CALIFORNIA_SAM_8294": (
        "Accounts receivable reconciliations monthly within 30 days; records retained 4 years."
    ),
}


class WriteOffAuthorityNotSet(ValueError):
    """Raised when attempting a write-off without an explicit human-configured threshold.

    SPEC section 10: No public policy publishes a dollar write-off threshold.
    Tieout refuses to act on write-off authority until explicitly configured by a human.
    """


class WriteOffExceedsAuthority(PermissionError):
    """Raised when an item amount exceeds the configured write-off authority threshold."""


def _as_decimal(value: Any) -> Decimal:
    """Coerce an amount to Decimal. Rejects floats to prevent precision loss."""
    raw = getattr(value, "amount", value)
    if isinstance(raw, float):
        raise TypeError(f"amount {value!r} arrived as float; money is Decimal (SPEC section 3)")
    if isinstance(raw, Decimal):
        return abs(raw)
    try:
        return abs(Decimal(str(raw)))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"cannot convert {value!r} to Decimal amount") from exc


def bucket_for_age(days: int) -> AgingBucket:
    """Assign an age in days to its standard aging bucket."""
    if days < 0:
        days = 0
    if days <= 30:
        return AgingBucket.DAYS_0_30
    if days <= 60:
        return AgingBucket.DAYS_31_60
    if days <= 90:
        return AgingBucket.DAYS_61_90
    if days <= 120:
        return AgingBucket.DAYS_91_120
    return AgingBucket.DAYS_OVER_120


def bucket_for_date(occurred_at: datetime, as_of: datetime | None = None) -> AgingBucket:
    """Assign an item date to an aging bucket relative to an `as_of` timestamp."""
    ref = as_of or utc_now()
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    delta_days = max(0, (ref.date() - occurred_at.date()).days)
    return bucket_for_age(delta_days)


def get_escalation_tier(bucket: AgingBucket) -> tuple[str, str] | None:
    """Return the policy authority and escalation notice for an aging bucket."""
    if bucket is AgingBucket.DAYS_31_60:
        return (
            "Controller Escalation",
            "Unresolved >30 days; escalated to Controller per U. of Houston MAPP 05.04.06.",
        )
    if bucket is AgingBucket.DAYS_61_90:
        return (
            "Suspense Breach Warning",
            "Unresolved >60 days; suspense resolution overdue per VA Financial Policy Ch. 1.",
        )
    if bucket in (AgingBucket.DAYS_91_120, AgingBucket.DAYS_OVER_120):
        return (
            "Executive Escalation & Audit Flag",
            "Long-standing break; statutory retention flag per California SAM §8294.",
        )
    return None


class AgingItem(BaseModel):
    """An item in the aging queue."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    work_key: str
    amount: Decimal
    age_days: int = Field(ge=0)
    outcome_class: str = ""
    tier: str = ""
    blocking: bool = False
    evidence_ref: str | None = None

    @property
    def bucket(self) -> AgingBucket:
        return bucket_for_age(self.age_days)

    @property
    def materiality_age_score(self) -> Decimal:
        """materiality x age: score used to sort the break queue."""
        return self.amount * Decimal(max(self.age_days, 1))


def materiality_age_score(amount: Any, age_days: int) -> Decimal:
    """Compute materiality x age score: largest oldest break gets highest score."""
    dec_amount = _as_decimal(amount)
    return dec_amount * Decimal(max(int(age_days), 1))


def _extract_item_score(
    item: Any, as_of: datetime | None = None
) -> tuple[Decimal, Decimal, int, str]:
    """Extract sorting key (materiality_age_score, amount, age_days, work_key) from an item."""
    if isinstance(item, AgingItem):
        return (
            item.materiality_age_score,
            item.amount,
            item.age_days,
            item.work_key,
        )

    # Duck-typed adapter
    work_key = str(
        getattr(item, "work_key", getattr(getattr(item, "verdict", None), "work_key", ""))
    )

    # Amount lookup
    raw_amt = getattr(item, "amount", None)
    if raw_amt is None:
        raw_amt = getattr(item, "amount_abs", None)
    if raw_amt is None:
        features = getattr(
            item, "features", getattr(getattr(item, "verdict", None), "features", None)
        )
        if features is not None:
            raw_amt = getattr(
                features, "amount_abs", getattr(features, "amount_delta", Decimal("0.00"))
            )
    amount = _as_decimal(raw_amt if raw_amt is not None else Decimal("0.00"))

    # Age lookup
    age_days: int = 0
    raw_age = getattr(item, "age_days", None)
    if raw_age is not None:
        age_days = max(0, int(raw_age))
    else:
        occurred_at = getattr(item, "occurred_at", getattr(item, "event_time", None))
        if isinstance(occurred_at, datetime):
            ref = as_of or utc_now()
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=UTC)
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=UTC)
            age_days = max(0, (ref.date() - occurred_at.date()).days)

    score = materiality_age_score(amount, age_days)
    return (score, amount, age_days, work_key)


def sort_by_materiality_and_age(
    items: Iterable[T],
    *,
    as_of: datetime | None = None,
) -> list[T]:
    """Sort items by materiality x age descending: largest oldest break is always first."""
    item_list = list(items)
    return sorted(
        item_list,
        key=lambda it: _extract_item_score(it, as_of=as_of),
        reverse=True,
    )


def group_by_aging_bucket(
    items: Iterable[T],
    *,
    as_of: datetime | None = None,
) -> dict[AgingBucket, list[T]]:
    """Group queue items into the five standard aging buckets."""
    grouped: dict[AgingBucket, list[T]] = defaultdict(list)
    for item in items:
        if isinstance(item, AgingItem):
            bucket = item.bucket
        else:
            _, _, age_days, _ = _extract_item_score(item, as_of=as_of)
            bucket = bucket_for_age(age_days)
        grouped[bucket].append(item)
    return {bucket: grouped[bucket] for bucket in AgingBucket}


def evaluate_write_off(
    amount: Any,
    write_off_threshold: Decimal | None,
) -> bool:
    """Evaluate whether an item amount is eligible for write-off under policy authority.

    Refuses to act if write_off_threshold is None (SPEC section 10 negative finding:
    no public policy default exists; threshold must be explicitly configured by a human).
    """
    if write_off_threshold is None:
        raise WriteOffAuthorityNotSet(
            "Write-off authority threshold has no default value (SPEC section 10). "
            "Refusing to act on write-off until a human explicitly configures the "
            "delegation-of-authority threshold in policy."
        )
    dec_amount = _as_decimal(amount)
    limit = _as_decimal(write_off_threshold)
    if dec_amount > limit:
        raise WriteOffExceedsAuthority(
            f"Write-off amount ${dec_amount:,.2f} exceeds authorized policy threshold "
            f"${limit:,.2f}."
        )
    return True
