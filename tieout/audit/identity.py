"""Actor identity and the four-eyes rule (AS 1105 requirements 1, 3 and 4).

A service identity and a human identity are *different kinds of thing*. They are modelled as
two unrelated types so that a service identity cannot be passed where an approver is required:
that is a type error under mypy and a ``ValidationError`` at runtime.

Also the home of the UTC timestamp helpers, because requirement 4 (created / reviewed / posted)
lives here and :mod:`tieout.audit.events` needs the same fixed representation for hashing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

# ── UTC timestamps ────────────────────────────────────────────────────────────
# One representation, everywhere: UTC, ISO-8601, microsecond precision always present,
# 'Z' offset. Fixed width means "…:09Z" and "…:09.000000Z" can never denote the same instant
# in two different byte strings. Naive datetimes are rejected; local time never enters the log.


def utc_now() -> datetime:
    """Current instant, timezone-aware UTC."""
    return datetime.now(UTC)


def to_utc_iso(value: datetime) -> str:
    """Render a tz-aware datetime as ``YYYY-MM-DDTHH:MM:SS.ffffffZ``.

    Raises ValueError on a naive datetime -- a timestamp without an offset is not evidence.
    """
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"naive datetime is not admissible in the audit trail: {value!r}")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _require_utc(value: datetime | None) -> datetime | None:
    if value is not None:
        to_utc_iso(value)  # validates the offset
    return value


# ── Identities ────────────────────────────────────────────────────────────────


class ServiceIdentity(BaseModel):
    """A bot/service principal, e.g. ``svc:tieout-agent@v0.3.1``.

    Distinct per deployed version, never a shared account (AS 1105 requirement 1).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["svc"] = "svc"
    name: str
    version: str

    @property
    def principal(self) -> str:
        return f"svc:{self.name}@{self.version}"


class HumanIdentity(BaseModel):
    """A named human principal, e.g. ``human:controller@acme``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["human"] = "human"
    user: str
    org: str

    @property
    def principal(self) -> str:
        return f"human:{self.user}@{self.org}"


Identity = ServiceIdentity | HumanIdentity
"""Either kind of actor. Use this only where *any* actor is acceptable; an approver slot must
be annotated ``HumanIdentity`` so the substitution is rejected."""


def principal_of(actor: Identity | str) -> str:
    """Normalise an actor to its principal string for the event log."""
    return actor if isinstance(actor, str) else actor.principal


class FourEyesViolation(Exception):
    """An approval whose approver is the initiator. Raised at write time, never deferred.

    Deliberately not a ValueError: pydantic converts ValueError raised inside a validator into
    a generic ValidationError, and a control violation must stay distinguishable from a typo.
    """


# ── Maker-checker ─────────────────────────────────────────────────────────────


class Approval(BaseModel):
    """A maker-checker approval (AS 1105 requirement 3).

    ``approver`` is typed :class:`HumanIdentity`, so a :class:`ServiceIdentity` cannot approve.
    An approval where the approver's principal equals the initiator's is rejected in the
    constructor -- there is no way to build one and flag it later.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    initiator: Identity
    approver: HumanIdentity
    at: datetime
    note: str = ""

    @model_validator(mode="after")
    def _four_eyes(self) -> Approval:
        _require_utc(self.at)
        if self.approver.principal == self.initiator.principal:
            raise FourEyesViolation(
                f"four-eyes violation: approver {self.approver.principal} is the initiator"
            )
        return self


class DecisionTimestamps(BaseModel):
    """Creation, review and posting instants (AS 1105 requirement 4).

    AS 2401 keys on period-end and post-close timing, so these are evidence, not metadata.
    Ordering is enforced: nothing is reviewed before it exists, nothing is posted before review.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    created_at: datetime
    reviewed_at: datetime | None = None
    posted_at: datetime | None = None

    @model_validator(mode="after")
    def _check(self) -> DecisionTimestamps:
        for value in (self.created_at, self.reviewed_at, self.posted_at):
            _require_utc(value)
        if self.reviewed_at is not None and self.reviewed_at < self.created_at:
            raise ValueError("reviewed_at precedes created_at")
        if self.posted_at is not None:
            if self.posted_at < self.created_at:
                raise ValueError("posted_at precedes created_at")
            if self.reviewed_at is not None and self.posted_at < self.reviewed_at:
                raise ValueError("posted_at precedes reviewed_at")
        return self

    def as_iso(self) -> dict[str, str | None]:
        """The three instants in the canonical UTC representation."""
        return {
            "created_at": to_utc_iso(self.created_at),
            "reviewed_at": to_utc_iso(self.reviewed_at) if self.reviewed_at else None,
            "posted_at": to_utc_iso(self.posted_at) if self.posted_at else None,
        }
