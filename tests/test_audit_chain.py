"""SPEC section 14: test_audit_chain_detects_tamper, plus the canonicalisation tripwire."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tieout.audit.events import (
    CANON_EXCLUDED,
    Event,
    EventLog,
    canonical,
    canonical_json,
    chain_hash,
)
from tieout.audit.evidence import EvidenceStore, EvidenceTampered, build_pack
from tieout.audit.identity import DecisionTimestamps, ServiceIdentity

AGENT = ServiceIdentity(name="tieout-agent", version="v0.3.1")

FIXED_EVENT = Event(
    event_id="evt_01HQZZTESTFIXTURE0000000001",
    seq=0,
    prev_hash=None,
    hash="",
    at=datetime(2026, 9, 6, 4, 12, 9, tzinfo=UTC),
    actor="svc:tieout-agent@v0.3.1",
    action="REFUSE",
    work_key="wk_batch_4471",
    outcome="AMBIGUOUS_MATCH",
    reason="L2_TWO_CANDIDATES_WITHIN_TOLERANCE",
    policy="2026.01-r3",
    features={"amount_delta": Decimal("0.00"), "candidate_count": 2},
    evidence="ev_sha256:c41f",
    blocking=True,
)

# The regression tripwire. If canonicalisation drifts by one byte, this fails.
EXPECTED_CANONICAL = (
    '{"action":"REFUSE","actor":"svc:tieout-agent@v0.3.1","at":"2026-09-06T04:12:09.000000Z",'
    '"blocking":true,"event_id":"evt_01HQZZTESTFIXTURE0000000001","evidence":"ev_sha256:c41f",'
    '"features":{"amount_delta":"0.00","candidate_count":2},'
    '"outcome":"AMBIGUOUS_MATCH","policy":"2026.01-r3",'
    '"reason":"L2_TWO_CANDIDATES_WITHIN_TOLERANCE","seq":0,"work_key":"wk_batch_4471"}'
)
EXPECTED_DIGEST = "ddda75ffe58fa318f2fda8837132bde9097cc2a70f9d1c60900f825471ad0913"


# ── canonicalisation ──────────────────────────────────────────────────────────


def test_canonical_form_is_byte_exact():
    assert canonical(FIXED_EVENT).decode("utf-8") == EXPECTED_CANONICAL


def test_canonical_digest_is_pinned():
    assert chain_hash(FIXED_EVENT, None) == EXPECTED_DIGEST


def test_hash_and_prev_hash_excluded_from_own_input():
    assert CANON_EXCLUDED == ("hash", "prev_hash")
    mutated = FIXED_EVENT.model_copy(update={"hash": "deadbeef", "prev_hash": "cafe"})
    assert canonical(mutated) == canonical(FIXED_EVENT)
    # ...but prev_hash still binds the chain, because it is appended by the chain rule.
    assert chain_hash(FIXED_EVENT, "cafe") != chain_hash(FIXED_EVENT, None)


def test_decimal_money_never_touches_a_float():
    assert canonical_json({"m": Decimal("0.00")}) == '{"m":"0.00"}'
    assert canonical_json({"m": Decimal("1234.50")}) == '{"m":"1234.50"}'
    assert canonical_json({"m": Decimal("-0.01")}) == '{"m":"-0.01"}'
    assert canonical_json({"m": Decimal("1E+2")}) == '{"m":"100"}'


def test_float_is_rejected_outright():
    with pytest.raises(TypeError, match="float is not admissible"):
        canonical_json({"amount_delta": 0.1 + 0.2})


def test_key_order_does_not_change_the_bytes():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_timestamps_are_utc_with_fixed_precision():
    ist = timezone(timedelta(hours=5, minutes=30))
    same_instant = datetime(2026, 9, 6, 9, 42, 9, tzinfo=ist)
    assert canonical_json({"at": same_instant}) == '{"at":"2026-09-06T04:12:09.000000Z"}'
    with pytest.raises(ValueError, match="naive datetime"):
        canonical_json({"at": datetime(2026, 9, 6, 4, 12, 9)})  # noqa: DTZ001


def test_non_ascii_is_nfc_normalised_and_utf8():
    composed = canonical_json({"desc": "café"})  # é as one code point
    decomposed = canonical_json({"desc": "café"})  # e + combining acute
    assert composed == decomposed
    assert composed.encode("utf-8") == '{"desc":"café"}'.encode()


# ── the chain ─────────────────────────────────────────────────────────────────


def _seeded_log(tmp_path, count=3) -> EventLog:
    log = EventLog(tmp_path / "events.jsonl")
    for index in range(count):
        log.append(
            actor=AGENT,
            action="REFUSE",
            work_key=f"wk_{index}",
            policy="2026.01-r3",
            at=datetime(2026, 9, 6, 4, 12, index, tzinfo=UTC),
            features={"amount_delta": Decimal("0.00"), "candidate_count": 2},
            blocking=True,
        )
    return log


def test_genesis_event_has_no_prev_hash(tmp_path):
    log = _seeded_log(tmp_path, count=1)
    (genesis,) = log.read_all()
    assert genesis.seq == 0
    assert genesis.prev_hash is None
    assert genesis.hash == chain_hash(genesis, None)


def test_intact_chain_verifies(tmp_path):
    log = _seeded_log(tmp_path)
    status = log.verify()
    assert status.ok
    assert status.events_verified == 3
    assert status.first_break is None
    assert log.verify(expected_head_hash=status.head_hash).ok


def test_chain_survives_a_round_trip_through_storage(tmp_path):
    """Decimals and timestamps must reload to the same canonical bytes, or it is not a chain."""
    log = _seeded_log(tmp_path)
    for event in log.read_all():
        assert chain_hash(event, event.prev_hash) == event.hash


def _rewrite(log: EventLog, lines: list[str]) -> None:
    log.path.write_text("".join(lines), encoding="utf-8")


def _lines(log: EventLog) -> list[str]:
    return log.path.read_text(encoding="utf-8").splitlines(keepends=True)


def test_audit_chain_detects_tamper(tmp_path):
    """SPEC section 14: alter one event's payload; verify() reports the exact break point."""
    log = _seeded_log(tmp_path)
    lines = _lines(log)
    victim = json.loads(lines[1])
    victim["outcome"] = "MATCHED"  # the tamper: a refusal quietly becomes a match
    lines[1] = canonical_json(victim) + "\n"
    _rewrite(log, lines)

    status = log.verify()
    assert not status.ok
    brk = status.first_break
    assert brk is not None
    assert brk.seq == 1
    assert brk.event_id == victim["event_id"]
    assert brk.field_name == "hash"
    assert brk.actual == victim["hash"]
    assert brk.expected != brk.actual
    assert "recomputed hash" in brk.detail
    assert str(brk.seq) in brk.report() and brk.expected in brk.report()


def test_detects_an_altered_hash(tmp_path):
    log = _seeded_log(tmp_path)
    lines = _lines(log)
    victim = json.loads(lines[1])
    victim["hash"] = "0" * 64
    lines[1] = canonical_json(victim) + "\n"
    _rewrite(log, lines)

    brk = log.verify().first_break
    assert brk is not None and brk.seq == 1 and brk.field_name == "hash"
    assert brk.actual == "0" * 64


def test_detects_reordered_events(tmp_path):
    log = _seeded_log(tmp_path)
    lines = _lines(log)
    lines[1], lines[2] = lines[2], lines[1]
    _rewrite(log, lines)

    brk = log.verify().first_break
    assert brk is not None
    assert brk.seq == 2 and brk.field_name == "seq"
    assert brk.expected == "1" and brk.actual == "2"


def test_detects_a_deleted_middle_event(tmp_path):
    log = _seeded_log(tmp_path)
    lines = _lines(log)
    del lines[1]
    _rewrite(log, lines)

    brk = log.verify().first_break
    assert brk is not None and brk.seq == 2 and brk.field_name == "seq"


def test_detects_truncation_against_the_head_anchor(tmp_path):
    log = _seeded_log(tmp_path)
    anchor = log.verify().head_hash
    lines = _lines(log)
    _rewrite(log, lines[:-1])

    assert log.verify().ok  # a prefix is self-consistent -- this is why the anchor exists
    status = log.verify(expected_head_hash=anchor)
    assert not status.ok
    brk = status.first_break
    assert brk is not None
    assert brk.field_name == "head_hash"
    assert brk.expected == anchor
    assert "truncated" in brk.detail


def test_there_is_no_delete_or_update_path():
    surface = set(dir(EventLog))
    assert not {"delete", "delete_event", "update", "edit", "remove"} & surface


# ── evidence packs ────────────────────────────────────────────────────────────

TIMES = DecisionTimestamps(
    created_at=datetime(2026, 9, 6, 4, 12, 9, tzinfo=UTC),
    reviewed_at=datetime(2026, 9, 6, 5, 0, 0, tzinfo=UTC),
)

ROWS = (
    {
        "source_row_ref": "ledger.csv#L41",
        "amount": Decimal("1200.00"),
        "currency": "USD",
    },
    {
        "source_row_ref": "bank.csv#L7",
        "amount": Decimal("1199.55"),
        "currency": "USD",
    },
)


def _pack():
    return build_pack(
        work_key="wk_batch_4471",
        source_rows=ROWS,
        features={"amount_delta": Decimal("0.45"), "candidate_count": 2},
        policy_version="2026.01-r3",
        thresholds={"amount_tolerance": Decimal("0.50")},
        disposition="REFUSE",
        rationale="two candidates inside tolerance",
        timestamps=TIMES,
    )


def test_pack_id_is_content_addressed(tmp_path):
    pack = _pack()
    assert pack.pack_id.startswith("ev_sha256:")
    assert _pack().pack_id == pack.pack_id  # deterministic
    changed = pack.model_copy(update={"disposition": "AUTO_POST"})
    assert changed.pack_id != pack.pack_id


def test_pack_round_trips_and_detects_substitution(tmp_path):
    store = EvidenceStore(tmp_path / "evidence")
    pack_id = store.put(_pack())
    assert store.get(pack_id).source_row_refs == ("ledger.csv#L41", "bank.csv#L7")
    assert store.verify(pack_id)

    swapped = json.loads(store.path_for(pack_id).read_text(encoding="utf-8"))
    swapped["rationale"] = "looked fine to me"
    store.path_for(pack_id).write_text(canonical_json(swapped), encoding="utf-8")

    assert not store.verify(pack_id)
    with pytest.raises(EvidenceTampered):
        store.get(pack_id)


def test_pack_requires_row_lineage():
    with pytest.raises(ValueError, match="source_row_ref"):
        build_pack(
            work_key="wk_1",
            source_rows=({"amount": Decimal("1.00")},),
            features={},
            policy_version="2026.01-r3",
            thresholds={},
            disposition="REFUSE",
            rationale="no lineage",
            timestamps=TIMES,
        )


def test_event_references_the_pack_it_was_decided_on(tmp_path):
    store = EvidenceStore(tmp_path / "evidence")
    pack_id = store.put(_pack())
    log = EventLog(tmp_path / "events.jsonl")
    event = log.append(
        actor=AGENT,
        action="REFUSE",
        work_key="wk_batch_4471",
        policy="2026.01-r3",
        evidence=pack_id,
        blocking=True,
    )
    assert log.verify().ok
    assert store.get(event.evidence).work_key == "wk_batch_4471"


# ── integration with the real ingest models ───────────────────────────────────


def test_pack_accepts_a_real_ingest_row(tmp_path):
    """A pack must take `LedgerEntry.model_dump()` as-is, or the lineage chain is theoretical.

    Guards two shapes this layer cannot choose: `source_row_ref` is a structured
    SourceRowRef, not a string, and `amount` is a currency-tagged Money, not a bare Decimal.
    """
    from tieout.ingest.money import Money
    from tieout.ingest.schema import LedgerEntry, SourceRowRef

    entry = LedgerEntry(
        id="led_1",
        order_key="ord_9",
        occurred_at=datetime(2026, 1, 31, 23, 59, 0, tzinfo=UTC),
        amount=Money("1200.00", "USD"),
        currency="USD",
        status="settled",
        method="card",
        source_row_ref=SourceRowRef(file="ledger.csv", row_number=41),
    )

    pack = build_pack(
        work_key="wk_batch_4471",
        source_rows=(entry.model_dump(),),
        features={"amount_delta": Decimal("0.00")},
        policy_version="2026.01-r3",
        thresholds={"amount_tolerance": Decimal("0.50")},
        disposition="REFUSE",
        rationale="two candidates inside tolerance",
        timestamps=TIMES,
    )

    assert pack.source_row_refs == ("ledger.csv#L41",)

    store = EvidenceStore(tmp_path / "evidence")
    pack_id = store.put(pack)
    assert store.verify(pack_id)
    # Money survives as an exact decimal string, not a float.
    assert '"amount":"1200.00"' in store.path_for(pack_id).read_text(encoding="utf-8")


def test_money_object_canonicalises_without_a_float():
    from tieout.ingest.money import Money

    assert canonical_json({"m": Money("0.10", "USD")}) == '{"m":{"amount":"0.10","currency":"USD"}}'
