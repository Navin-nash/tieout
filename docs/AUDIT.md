# The Audit Trail — Layer 3

*For auditors and engineers. Everything below is implemented in `tieout/audit/` and proved by
`tests/test_audit_chain.py` and `tests/test_identity.py`.*

---

## 1. Why this exists

PCAOB **[AS 1105](https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105)
paragraph .10** requires the auditor to

> *"test the accuracy and completeness of the information, or test the controls over the
> information"* — including **information technology general controls**.

That is the *completeness and accuracy of information produced by the entity* (IPE) requirement,
and it is why an auditor asks: **show me the report you pulled this from, and prove nobody
edited it.** When the preparer is software rather than a person, "prove nobody edited it" is not
a conversation — it is a property the system either has or does not have.

The stake is measurable. 2024 PCAOB inspections found **ITGC testing gaps were the leading
reason auditors could not rely on automated controls**; across six global network firms,
**68% of engagements had an ICFR deficiency**, with AS 2201 the most-cited standard by a wide
margin. A close agent whose work cannot be tested is a close agent whose work must be re-performed
by hand, which is the same as not having one.

> **Retrofitting this is impossible.** Identity, lineage and timestamps have to be captured at the
> moment of the decision. They cannot be reconstructed afterwards from an output.

---

## 2. The six requirements and where each one lives

An automated journal entry must log six things. Each maps to code you can read.

| # | Requirement | Implementation | Proved by |
|---|---|---|---|
| 1 | Initiating identity — a **distinct bot/service identity, not a shared account** | `identity.ServiceIdentity` / `identity.HumanIdentity`, two unrelated types. Rendered `svc:tieout-agent@v0.3.1` and `human:controller@acme` | `test_a_service_identity_cannot_be_a_human_approver`, `test_service_identity_is_per_version_not_a_shared_account` |
| 2 | Source data lineage back to the upstream extract, plus evidence the extract was itself tested | `evidence.EvidencePack.source_rows`, each row carrying its `source_row_ref` → run manifest with per-file SHA256 (`tieout/ingest/manifest.py`) | `test_pack_requires_row_lineage`, `test_pack_round_trips_and_detects_substitution` |
| 3 | Approval by a party **distinct from the initiator** (maker-checker / four-eyes) | `identity.Approval` rejects `approver == initiator` in its constructor | `test_four_eyes_enforced` |
| 4 | Creation, review and posting timestamps — AS 2401 keys on period-end timing | `identity.DecisionTimestamps` — `created_at`, `reviewed_at`, `posted_at`, all UTC ISO-8601, ordering enforced | `test_timestamps_are_utc_iso_8601`, `test_local_time_is_never_admissible` |
| 5 | Immutability and a unique ID | `events.EventLog` — append-only JSONL, every event carrying `event_id`, contiguous `seq` and `prev_hash`, forming a SHA-256 chain | `test_audit_chain_detects_tamper` and the four other tamper tests |
| 6 | Attached supporting documentation | `evidence.EvidencePack`, addressed by the hash of its own contents | `test_pack_id_is_content_addressed` |

The three ITGC domains this is designed to satisfy are **access** (who acted — requirement 1 and 3),
**change management** (what changed and in what order — requirement 5), and **computer operations**
(when, and against which inputs — requirements 2 and 4).

---

## 3. The event log

### Shape

One JSON object per line, in chain order, exactly the shape in `docs/SPEC.md` section 8:

```json
{"action":"REFUSE","actor":"svc:tieout-agent@v0.3.1","at":"2026-09-06T04:12:09.000000Z",
 "blocking":true,"event_id":"evt_...","evidence":"ev_sha256:c41f...",
 "features":{"amount_delta":"0.00","candidate_count":2},"hash":"3e77bd...",
 "outcome":"AMBIGUOUS_MATCH","policy":"2026.01-r3","prev_hash":"9f2c1a...",
 "reason":"L2_TWO_CANDIDATES_WITHIN_TOLERANCE","seq":14071,"work_key":"wk_batch_4471"}
```

(shown wrapped; on disk it is one line, with no whitespace between tokens.)

### The chain rule

```
hash = sha256( canonical(event) + prev_hash )
```

- `canonical(event)` is the UTF-8 byte string defined in section 4.
- `prev_hash` is the predecessor's `hash`, as lowercase hex ASCII, concatenated directly with no
  separator.
- The **genesis event** (`seq = 0`) has no predecessor. It stores `"prev_hash": null` and uses the
  **empty string** as the `prev_hash` term in the hash input.
- `seq` is **contiguous** from 0, not merely increasing. Contiguity costs nothing extra to verify
  and turns a deleted middle event from an invisible gap into a detected break.

### Append-only, by construction

`EventLog` exposes `append`, `read_all`, `head` and `verify`. **There is no update path and no
delete path** — not a guarded one, not an admin one. `delete_event(event_id)` is listed in
`docs/SPEC.md` section 7 among the functions that deliberately do not exist, and it does not exist
here. `test_there_is_no_delete_or_update_path` asserts the absence rather than trusting the prose.

This closes one specific reward-hacking avenue from SPEC section 6: *delete inconvenient log
entries*. The reference failure is the Darwin Gödel Machine, which — asked to reduce hallucination
— deleted the logging tokens its detector relied on. Defeating the measurement instead of the
problem is the failure mode this layer exists to make detectable.

---

## 4. Canonicalisation — the rules, in reimplementable detail

**A chain that cannot be recomputed byte-for-byte is not a chain.** Anyone re-deriving these hashes
in another language must produce identical bytes. Every rule below is therefore fixed, and
`tests/test_audit_chain.py` pins the result against a literal expected digest — if any rule drifts
by one byte, that test fails.

Implemented in `tieout/audit/events.py`: `_canon`, `canonical_json`, `canonical`, `chain_hash`.

### 4.1 Which fields are hashed

Every field of the event **except**:

| Excluded field | Why |
|---|---|
| `hash` | Self-reference. It is the output of the function; it cannot also be an input. |
| `prev_hash` | It is appended separately by the chain rule, so it is still fully covered by the digest — just not twice. |

Everything else — `event_id`, `seq`, `at`, `actor`, `action`, `work_key`, `outcome`, `reason`,
`policy`, `features`, `evidence`, `blocking` — is inside the hash input. Fields that are `None`
are included as JSON `null`; they are not dropped, because "absent" and "null" must not collide.

### 4.2 Value rules

| Type | Rule | Example |
|---|---|---|
| `str` | Unicode **NFC**-normalised, then emitted as JSON text | `"café"` and `"café"` both → `"café"` |
| `int` | JSON number, verbatim | `2` → `2` |
| `bool` | JSON `true` / `false`. Checked **before** `int`, because `bool` is an `int` subclass in Python | `True` → `true` |
| `None` | JSON `null` | |
| `Decimal` | **String**, non-scientific notation, exponent preserved: `format(d, "f")`. Never a float, never rounded here | `Decimal("0.00")` → `"0.00"`, `Decimal("1E+2")` → `"100"` |
| `float` | **Rejected — `TypeError`.** See 4.3 | |
| `datetime` | String, UTC, `%Y-%m-%dT%H:%M:%S.%fZ` — always 6 fractional digits, always `Z`. Naive datetimes are rejected | `2026-09-06 09:42:09+05:30` → `"2026-09-06T04:12:09.000000Z"` |
| mapping | JSON object, keys NFC-normalised, **sorted by key**, ascending Unicode **code point** order (Python's `str` ordering / `sort_keys=True`) — note this differs from UTF-16 code-unit order above the BMP | |
| list / tuple | JSON array, **order preserved** — order is meaning | |
| currency-tagged amount | An object exposing `amount` and `currency` (`tieout.ingest.money.Money`) → `{"amount": <the Decimal rule>, "currency": <string>}`. Duck-typed, not imported, so the audit layer stays standalone | `Money("0.10", "USD")` → `{"amount":"0.10","currency":"USD"}` |
| anything else | **Rejected — `TypeError`.** Sets in particular: an unordered container has no canonical form | |

### 4.3 Why a float is rejected rather than converted

Money that round-trips through a binary float is a defect, not a rounding nuisance: `0.1 + 0.2`
is `0.30000000000000004`, and two implementations of the same event can disagree about the shortest
repr that identifies a double. Rather than silently pick a formatting rule, `canonical()` raises:

```
TypeError: float is not admissible in a hash input; use Decimal or str
```

**Callers must pass `Decimal` (or a string) for every fractional value**, including confidences and
ratios, not only money. This is stricter than the rest of the codebase requires, and deliberately so
— the hash input is the one place where a representation choice becomes permanent.

### 4.4 Encoding and separators

```python
json.dumps(canonicalised, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
```

- Separators are exactly `","` and `":"` — **no incidental whitespace anywhere**.
- `ensure_ascii=False`: non-ASCII characters are emitted as themselves, then the whole string is
  encoded **UTF-8**. Combined with NFC normalisation, `café` has exactly one byte representation
  regardless of which platform produced the source file. (macOS filenames arrive NFD; without
  normalisation the same descriptive text would hash two different ways.)
- The trailing `prev_hash` is appended as **ASCII** bytes, after the UTF-8 payload.

### 4.5 The tripwire

`tests/test_audit_chain.py` fixes one event and asserts both the canonical bytes and the digest:

```
canonical: {"action":"REFUSE","actor":"svc:tieout-agent@v0.3.1","at":"2026-09-06T04:12:09.000000Z",
            "blocking":true,"event_id":"evt_01HQZZTESTFIXTURE0000000001",
            "evidence":"ev_sha256:c41f","features":{"amount_delta":"0.00","candidate_count":2},
            "outcome":"AMBIGUOUS_MATCH","policy":"2026.01-r3",
            "reason":"L2_TWO_CANDIDATES_WITHIN_TOLERANCE","seq":0,"work_key":"wk_batch_4471"}

sha256:    ddda75ffe58fa318f2fda8837132bde9097cc2a70f9d1c60900f825471ad0913
```

### 4.6 Storage is the canonical form

The line written to disk *is* the canonical JSON, plus the two excluded fields. An auditor reading
`events.jsonl` is reading (modulo `hash` and `prev_hash`) the exact bytes that were hashed. A
consequence worth stating: `Decimal("0.00")` is stored as the string `"0.00"` and reloads as the
string `"0.00"`, which canonicalises identically — so a chain verifies the same before and after
a round trip through the file. `test_chain_survives_a_round_trip_through_storage` asserts this,
because a chain that only verifies in memory is not a chain either.

---

## 5. Running verification and reading a break report

```python
from tieout.audit import EventLog

status = EventLog("run/events.jsonl").verify()
```

`verify()` walks the log from genesis and checks three things per event, in this order:

1. **`seq`** is contiguous with its position.
2. **`prev_hash`** equals the previous event's `hash` (`null` for genesis).
3. **`hash`** recomputes to the stored value.

It returns a `ChainStatus`:

| Field | Meaning |
|---|---|
| `ok` | True only if the whole chain verified |
| `events_verified` | How many events verified before the break (all of them, if `ok`) |
| `head_hash` | The `hash` of the last event — the value to anchor externally |
| `first_break` | `None`, or a `ChainBreak` locating the failure exactly |

A `ChainBreak` is not a boolean. It names the break point:

```
audit chain broken at seq=1 event_id=evt_9f0c...: recomputed hash does not match the stored hash
  field    : hash
  expected : 8c1e0b6e...   ← what the event's own contents hash to
  actual   : 3e77bd41...   ← what the log claims
```

Read it as: **everything up to `seq - 1` is intact; the event at `seq` was altered.** The
`field_name` tells you how:

| `field_name` | What happened |
|---|---|
| `hash` | The event's payload was edited, or its `hash` was edited. Contents and claimed hash disagree. |
| `prev_hash` | The event does not chain to its predecessor — events were spliced or substituted. |
| `seq` | The sequence is not contiguous — events were reordered or one was deleted from the middle. |
| `head_hash` | The log is a valid prefix of itself but shorter than the anchor says — the tail was truncated. |

### Truncation needs an external anchor

Deleting entries from the **end** of an append-only log leaves a perfectly valid chain: a prefix of
a valid chain is a valid chain. No self-contained check can detect that, and claiming otherwise
would be the same kind of theatre this layer exists to prevent. Detection requires an anchor held
outside the log — the `head_hash` recorded in the run manifest, a close-gate record, or a
counter-signature:

```python
status = log.verify(expected_head_hash=anchor_from_the_run_manifest)
# → first_break.field_name == "head_hash", detail "...events were truncated"
```

Deleting from the **middle** needs no anchor: it breaks `seq` and `prev_hash` immediately.

---

## 6. Evidence packs

One bundle per decision, holding the six things `docs/SPEC.md` section 8 requires:

| Field | Content |
|---|---|
| `source_rows` | The candidate source rows **verbatim**, each carrying its `source_row_ref` |
| `features` | The computed feature vector |
| `policy_version`, `thresholds` | The policy version **and the specific thresholds applied** — not a pointer, the values |
| `disposition`, `rationale` | What was decided and why |
| `cited_decision_id` | Any cited prior human decision |
| `review` | The reviewer action: identity, action, timestamp |
| `timestamps` | `created_at` / `reviewed_at` / `posted_at` |

### Content addressing

```
pack_id = "ev_sha256:" + sha256(canonical_json(pack contents, excluding pack_id))
```

Same canonicalisation rules as section 4 — so money in an evidence pack is a `Decimal` rendered as
a string here too, and a float is rejected here too.

The event log references a pack by that id. **The id is derived from the contents, so a pack cannot
be swapped for a different one**: change any byte of the pack and it hashes to a different id, and
the id the event cites no longer resolves. `EvidenceStore.get()` re-derives the id on every read and
raises `EvidenceTampered` if the file it loaded is not the file that was filed. Verified by
`test_pack_round_trips_and_detects_substitution`.

### Lineage

Every row in `source_rows` must carry a usable `source_row_ref`; a pack without one will not
construct. Both shapes a caller can hold are accepted: a plain string, or the structured
`tieout.ingest.schema.SourceRowRef` — `{"file": ..., "row_number": ...}` — which is what
`LedgerEntry.model_dump()` produces. `source_row_refs` renders either as `<file>#L<row_number>`.
That reference resolves to **a file plus a row number**, and that file's **SHA256 lives
in the run manifest** (`tieout/ingest/manifest.py`), re-verified at scoring time. So a pack traces
back to specific bytes on disk that were hashed at ingest, which is exactly what AS 1105 ¶.10 asks
an auditor to test.

The result: *"show your work"* is a **property of the system**, not a report someone assembles after
the fact.

---

## 7. Identity: services, humans, and four eyes

### Two kinds of thing, not two strings

`svc:tieout-agent@v0.3.1` and `human:controller@acme` are different *kinds* of actor and are
modelled as **two unrelated types**:

```python
ServiceIdentity(name="tieout-agent", version="v0.3.1")  # → "svc:tieout-agent@v0.3.1"
HumanIdentity(user="controller", org="acme")  # → "human:controller@acme"
```

Neither is a subtype of the other, so a slot annotated `HumanIdentity` **cannot** receive a
`ServiceIdentity`: that is a type error under mypy and a `ValidationError` at runtime. There is no
place where an agent can approve its own work by being spelled like a person.

The service identity carries its **version**, so `v0.3.1` and `v0.4.0` are different principals.
That is requirement 1's "not a shared account" taken literally: the actor named in the log is a
specific deployed artefact, and a behaviour change moves the identity with it.

### Four eyes, rejected at write time

```python
Approval(initiator=CONTROLLER, approver=CONTROLLER, at=...)
# FourEyesViolation: four-eyes violation: approver human:controller@acme is the initiator
```

The check lives in the `Approval` constructor, so **an approval that violates it cannot be
constructed** — it is not written and flagged later, and there is no object to inspect afterwards.
Comparison is on the **principal string**, not object identity, so re-creating an equal identity
does not evade it. `FourEyesViolation` is deliberately not a `ValueError` subclass: pydantic folds
`ValueError` raised inside a validator into a generic `ValidationError`, and a control violation
must stay distinguishable from a typo. Asserted by `test_four_eyes_enforced`.

### Timestamps

`DecisionTimestamps` holds `created_at`, `reviewed_at` and `posted_at`. All three are UTC ISO-8601
in the section 4.2 representation. **Naive datetimes are rejected** — a timestamp without an offset
is not evidence, and local time never enters the log. Ordering is enforced: nothing is reviewed
before it exists, nothing is posted before it is reviewed.

AS 2401 keys fraud risk on period-end and post-close timing, so these three instants are substantive
evidence rather than metadata: an entry created after the period closed and posted minutes before
the filing looks different from one created mid-month, and the log has to be able to tell you which.

---

## 8. Running the checks

```
pytest tests/test_audit_chain.py tests/test_identity.py -q
```

Covering: the canonical form and its literal digest · Decimal-through-canonicalisation without a
float · float rejection · key-order and non-ASCII stability · genesis handling · payload tamper ·
hash tamper · reordering · middle deletion · tail truncation against an anchor · evidence pack
content addressing and substitution · row-lineage enforcement · four-eyes · the service/human
substitution.

---

## 9. Public API

Everything below is importable from `tieout.audit`.

```python
# events.py
EventLog(path)
  .append(*, actor, action, work_key, policy, at=None, outcome=None,
          reason=None, features=None, evidence=None, blocking=False) -> Event
  .read_all() -> list[Event]
  .head() -> Event | None
  .verify(expected_head_hash=None) -> ChainStatus
Event, ChainStatus, ChainBreak
canonical(event) -> bytes ; canonical_json(mapping) -> str ; chain_hash(event, prev_hash) -> str

# identity.py
ServiceIdentity(name, version) ; HumanIdentity(user, org) ; Identity = ServiceIdentity | HumanIdentity
Approval(initiator, approver: HumanIdentity, at, note="")     # raises FourEyesViolation
DecisionTimestamps(created_at, reviewed_at=None, posted_at=None).as_iso()
utc_now() -> datetime ; to_utc_iso(datetime) -> str ; FourEyesViolation

# evidence.py
build_pack(*, work_key, source_rows, features, policy_version, thresholds,
           disposition, rationale, timestamps, cited_decision_id=None, review=None) -> EvidencePack
EvidencePack.pack_id -> "ev_sha256:..." ; .source_row_refs -> tuple[str, ...]
EvidenceStore(root).put(pack) -> str ; .get(pack_id) -> EvidencePack ; .verify(pack_id) -> bool
ReviewAction(reviewer: HumanIdentity, action, at, note="") ; EvidenceTampered
```

`actor` accepts an `Identity` or a principal string; it is normalised to the principal string in the
log. There is no `delete`, no `update`, and no `force`.

---

## Sources

- PCAOB **AS 1105 ¶.10**, *Audit Evidence* — <https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105>
- PCAOB **AS 2401 ¶.61**, *Consideration of Fraud in a Financial Statement Audit* — journal-entry testing, period-end timing
- 2024 PCAOB inspections across six global network firms: 68% of engagements with an ICFR deficiency; ITGC testing gaps the leading reason auditors could not rely on automated controls (`docs/RESEARCH.md`)
- Maker-checker / four-eyes — <https://en.wikipedia.org/wiki/Maker-checker>
- `docs/SPEC.md` sections 6, 7, 8 and 14
