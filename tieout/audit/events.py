"""Append-only, hash-chained event log (AS 1105 requirement 5).

Chain rule, verbatim from docs/SPEC.md section 8::

    hash = sha256(canonical(event) + prev_hash)

The canonicalisation rules are specified in docs/AUDIT.md and pinned by a literal expected
digest in tests/test_audit_chain.py. A chain that cannot be recomputed byte-for-byte is not
a chain, so every rule below is deliberate and none of them may drift silently.

There is no update path and no delete path. ``delete_event`` is absent from the tool surface
by design (SPEC section 7) and is therefore absent from this module.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from tieout.audit.identity import Identity, principal_of, to_utc_iso, utc_now

#: Fields excluded from an event's own hash input.
#: ``hash`` -- self-reference: it is the output, it cannot be an input.
#: ``prev_hash`` -- appended separately by the chain rule above, so it is still covered.
CANON_EXCLUDED: tuple[str, ...] = ("hash", "prev_hash")

#: The genesis event has no predecessor; the empty string stands in as its prev_hash input.
GENESIS_PREV_HASH = ""

#: Seq is contiguous and starts here. Contiguity is stronger than monotonicity and just as cheap.
GENESIS_SEQ = 0


# ── Canonicalisation ──────────────────────────────────────────────────────────


def _canon(value: Any) -> Any:
    """Reduce a value to a JSON primitive under the pinned rules (see docs/AUDIT.md)."""
    if value is None:
        return None
    if isinstance(value, bool):  # before int: bool is an int subclass
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise TypeError(
            "float is not admissible in a hash input; use Decimal or str "
            f"(got {value!r}). Money through a float is a defect."
        )
    if isinstance(value, Decimal):
        # Non-scientific, exponent preserved: Decimal("0.00") -> "0.00", never 0.0.
        if not value.is_finite():
            raise ValueError(f"non-finite Decimal is not admissible: {value!r}")
        return format(value, "f")
    if isinstance(value, datetime):
        return to_utc_iso(value)
    if isinstance(value, Mapping):
        return {unicodedata.normalize("NFC", str(k)): _canon(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)) or (
        isinstance(value, Sequence) and not isinstance(value, (str, bytes))
    ):
        return [_canon(v) for v in value]
    if hasattr(value, "amount") and hasattr(value, "currency"):
        # A currency-tagged amount (tieout.ingest.money.Money). Duck-typed rather than
        # imported, so the audit layer stays standalone. The amount goes through the Decimal
        # rule above, so money still never touches a float.
        return {"amount": _canon(value.amount), "currency": _canon(value.currency)}
    raise TypeError(f"{type(value).__name__} has no canonical form: {value!r}")


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Canonical JSON text: keys sorted, no incidental whitespace, non-ASCII kept as UTF-8."""
    return json.dumps(_canon(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical(event: Event) -> bytes:
    """The exact bytes hashed for an event: canonical JSON of every field but CANON_EXCLUDED."""
    payload = {k: v for k, v in event.model_dump().items() if k not in CANON_EXCLUDED}
    return canonical_json(payload).encode("utf-8")


def chain_hash(event: Event, prev_hash: str | None) -> str:
    """``sha256(canonical(event) + prev_hash)``, with ``""`` for the genesis event."""
    tail = (prev_hash or GENESIS_PREV_HASH).encode("ascii")
    return hashlib.sha256(canonical(event) + tail).hexdigest()


# ── Records ───────────────────────────────────────────────────────────────────


def _new_event_id() -> str:
    return f"evt_{uuid4().hex}"


class Event(BaseModel):
    """One immutable decision record. Shape is SPEC section 8 verbatim."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(default_factory=_new_event_id)
    seq: int
    prev_hash: str | None = None
    hash: str = ""
    at: datetime
    actor: str
    action: str
    work_key: str
    outcome: str | None = None
    reason: str | None = None
    policy: str
    features: dict[str, Any] = Field(default_factory=dict)
    evidence: str | None = None
    blocking: bool = False


class ChainBreak(BaseModel):
    """The exact break point: which event, which field, what was expected, what was found."""

    model_config = ConfigDict(frozen=True)

    seq: int
    event_id: str
    field_name: str
    expected: str
    actual: str
    detail: str

    def report(self) -> str:
        return (
            f"audit chain broken at seq={self.seq} event_id={self.event_id}: {self.detail}\n"
            f"  field    : {self.field_name}\n"
            f"  expected : {self.expected}\n"
            f"  actual   : {self.actual}"
        )


class ChainStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    events_verified: int
    head_hash: str | None = None
    first_break: ChainBreak | None = None


# ── The log ───────────────────────────────────────────────────────────────────


class EventLog:
    """Append-only JSONL. One canonical JSON object per line, in chain order.

    The stored line is the canonical form plus ``prev_hash`` and ``hash``, so the file an
    auditor reads is byte-identical to the bytes that were hashed (modulo those two fields).
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    # -- write ---------------------------------------------------------------

    def append(
        self,
        *,
        actor: Identity | str,
        action: str,
        work_key: str,
        policy: str,
        at: datetime | None = None,
        outcome: str | None = None,
        reason: str | None = None,
        features: Mapping[str, Any] | None = None,
        evidence: str | None = None,
        blocking: bool = False,
    ) -> Event:
        """Seal one event onto the head of the chain and fsync it. The only write path."""
        head = self.head()
        draft = Event(
            seq=GENESIS_SEQ if head is None else head.seq + 1,
            prev_hash=None if head is None else head.hash,
            at=at or utc_now(),
            actor=principal_of(actor),
            action=action,
            work_key=work_key,
            policy=policy,
            outcome=outcome,
            reason=reason,
            features=dict(features or {}),
            evidence=evidence,
            blocking=blocking,
        )
        sealed = draft.model_copy(update={"hash": chain_hash(draft, draft.prev_hash)})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical_json(sealed.model_dump()) + "\n")
            fh.flush()
        return sealed

    # -- read ----------------------------------------------------------------

    def read_all(self) -> list[Event]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as fh:
            return [Event(**json.loads(line)) for line in fh if line.strip()]

    def head(self) -> Event | None:
        """The last sealed event, or None for an empty log."""
        # ponytail: linear scan of the file per append; seek to the tail if logs outgrow a
        # single close run (they are one line per decision, so tens of thousands at most).
        if not self.path.exists():
            return None
        last: str | None = None
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = line
        return None if last is None else Event(**json.loads(last))

    # -- verify --------------------------------------------------------------

    def verify(self, expected_head_hash: str | None = None) -> ChainStatus:
        """Walk the chain and report the first break precisely.

        ``expected_head_hash`` anchors the tail: without an external anchor a truncated log is
        a valid prefix of itself and no self-contained check can detect the loss.
        """
        events = self.read_all()
        prev: Event | None = None
        for index, event in enumerate(events):
            expected_seq = GENESIS_SEQ + index
            if event.seq != expected_seq:
                return _broken(event, "seq", expected_seq, event.seq, "sequence is not contiguous")

            expected_prev = None if prev is None else prev.hash
            if event.prev_hash != expected_prev:
                return _broken(
                    event,
                    "prev_hash",
                    expected_prev,
                    event.prev_hash,
                    "event does not chain to its predecessor",
                )

            recomputed = chain_hash(event, event.prev_hash)
            if recomputed != event.hash:
                return _broken(
                    event,
                    "hash",
                    recomputed,
                    event.hash,
                    "recomputed hash does not match the stored hash",
                )
            prev = event

        head_hash = prev.hash if prev else None
        if expected_head_hash is not None and head_hash != expected_head_hash:
            return ChainStatus(
                ok=False,
                events_verified=len(events),
                head_hash=head_hash,
                first_break=ChainBreak(
                    seq=prev.seq if prev else -1,
                    event_id=prev.event_id if prev else "",
                    field_name="head_hash",
                    expected=str(expected_head_hash),
                    actual=str(head_hash),
                    detail="log head does not match the external anchor; events were truncated",
                ),
            )
        return ChainStatus(ok=True, events_verified=len(events), head_hash=head_hash)


def _broken(
    event: Event, field_name: str, expected: object, actual: object, detail: str
) -> ChainStatus:
    return ChainStatus(
        ok=False,
        events_verified=event.seq - GENESIS_SEQ,
        first_break=ChainBreak(
            seq=event.seq,
            event_id=event.event_id,
            field_name=field_name,
            expected=str(expected),
            actual=str(actual),
            detail=detail,
        ),
    )
