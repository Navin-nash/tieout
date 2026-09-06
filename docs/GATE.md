# The Refusal Gate

> *"AccountingBench models plug because they can. We didn't prompt ours not to — we deleted the
> tool. There is no function in this system that posts an amount somebody didn't match. The plug
> isn't forbidden; it's unrepresentable."*

This document describes what is actually implemented in `tieout/gate/**` and `tieout/post/**`,
which invariant each piece enforces, and — at the end — what is *not* implemented.

Source of truth: `docs/SPEC.md` sections 6, 7, 9 and 14. Where this document and the code
disagree, the code is wrong; where this document claims something the code does not do, this
document is wrong. The "Honest gaps" section exists so that neither has to be guessed at.

| File | Role |
|---|---|
| `tieout/gate/tiers.py` | the four tiers, the policy adapter, reproducible sampling |
| `tieout/gate/decide.py` | the gate itself: preconditions, tiering, precedent, audit event |
| `tieout/gate/invariants.py` | I1–I4 asserted in code; the absence checker |
| `tieout/post/journal.py` | `MatchId`, `PersistedMatch`, journal construction |
| `tieout/post/tools.py` | the constrained tool surface — seven methods |
| `tests/test_invariants.py` | 67 tests. Several fail if something is *added* |

---

## 1. Four dispositions, and there is no fifth

`Tier` has exactly four members and `Action` exactly four; `ACTION_OF` is a total map between
them. `tests/test_invariants.py::test_the_four_dispositions_and_no_fifth` pins both sets.

### T0 · AUTO_POST

```
conf ≥ auto.min_confidence          (0.95 in policy.yaml)
∧ |amt| < clearly_trivial
∧ deterministic key match           (FeatureVector.ref_match == EXACT)
∧ no AS 2401 red flag
∧ no SAB 99 qualitative override
```

Posts with full evidence, no human touch.

### T1 · AUTO_SAMPLED

```
conf ≥ auto_sampled.min_confidence  (0.90)
∧ |amt| < performance_materiality
```

Posts, with `sample_rate` (5%) drawn into the review queue as control evidence.

**The draw is reproducible.** `tiers.is_sampled(work_key, run_seed, sample_rate)` takes the
first eight bytes of `sha256(f"{run_seed}:{work_key}")` as a fraction of 2⁶⁴ and compares it to
the rate. Not `random`, and emphatically not `hash()` — which is salted per process, so a
scoreboard in one process and a `pass^k` re-run in another would disagree about which items
were sampled. A sample nobody can reproduce is not control evidence.

### T2 · ESCALATE

```
conf ≥ escalate.min_confidence      (0.60)
∨ |amt| ≥ performance_materiality
∨ a qualitative override fired      (SAB 99, supplied by the policy layer)
∨ an AS 2401 ¶.61 red flag fired    (supplied by the policy layer)
```

Human queue, with the reason code and the triggers. **Does not block the close.**

### T3 · REFUSE — blocks the close

```
no admissible match                 (candidate_count == 0)
∨ conf < escalate.min_confidence
∨ ≥ 2 candidates within tolerance   (candidate_count ≥ 2)
∨ unexplained batch incompleteness
∨ an inadmissible outcome class     (see §2)
```

Cannot be posted at all. **No override path exists in code** — there is no parameter, flag,
environment variable or CLI option anywhere in `tieout/gate` or `tieout/post` that turns a
REFUSE into anything else.

### Resolving the overlap between the predicates

As written in SPEC section 6 the predicates overlap: T2's `conf ≥ 0.60` clause subsumes every
T0 and T1 item. `tiers.tier_for` resolves this in one fixed order, and the order is the
conservative one:

1. `conf < escalate_min` → **T3**. Nothing later can undo it.
2. Any *forcing* clause of T2 — amount at or above performance materiality, a qualitative
   override, a red flag → **T2**. A high-confidence trivial item carrying a red flag escalates;
   it does not auto-post.
3. Full T0 conjunction → **T0**.
4. `conf ≥ auto_sampled_min` (amount below performance materiality already established) → **T1**.
5. Otherwise → **T2**.

---

## 2. Precondition ordering: ambiguity is checked *before* tiering

SPEC section 6 makes I3 a **gate precondition**, and `decide()` honours that literally:
`_preconditions()` runs first and returns a T3 disposition before `tier_for` is ever called.

The reason is the attack it closes. If ambiguity were one clause among many in the tiering
predicate, an item with two candidates inside tolerance and a confidence of 0.99 would have a
scoring path to T0 — and the AMBIGUOUS_MATCH class is exactly where a model is most confident
and most wrong, because "these two rows both look right" is indistinguishable from "this row
looks right" to anything scoring a single candidate. Ambiguity is not a low-confidence state.
Checking it before tiering means **no amount of confidence buys a way out**, which is what
`test_ambiguity_is_checked_before_tiering` asserts by running the same features twice, once with
`candidate_count=1` (AUTO_POST) and once with `candidate_count=2` (REFUSE).

The preconditions, all read straight off the `FeatureVector` or the outcome class:

| Condition | Trigger code |
|---|---|
| `candidate_count ≥ 2` | `L2_TWO_CANDIDATES_WITHIN_TOLERANCE` |
| `candidate_count == 0` | `L3_NO_ADMISSIBLE_MATCH` |
| outcome class ∈ `INADMISSIBLE_OUTCOME_CLASSES` | `L3_INADMISSIBLE_OUTCOME_CLASS:<class>` |
| `batch_completeness < 1` and not explained | `L3_UNEXPLAINED_BATCH_INCOMPLETENESS` |

`INADMISSIBLE_OUTCOME_CLASSES` is SPEC section 3's four REFUSE classes: `MISSING_PROCESSOR`,
`MISSING_INTERNAL`, `MISSING_BANK_SETTLEMENT`, `AMBIGUOUS_MATCH`. Those 80 rows are the point of
the project, and they refuse on class alone regardless of what confidence was attached.

`batch_incompleteness_explained` defaults to `False`: **unexplained is the default**, and the
caller must positively assert that an explanation exists (a late settlement, say). The gate does
not decide what counts as an explanation — that is the match layer's judgement, not the gate's.

---

## 3. The LLM has no privileged path

SPEC section 5.5: the model's verdict is re-run through the same gate as everything else, with
no privileged path. Three things enforce it:

1. **`tier_for` cannot see the adjudicator.** It is not a parameter. There is nothing to branch
   on even if someone wanted to.
2. **`decide()` never reads `verdict.adjudicator`** except to carry it onto the normalised view;
   it is not consulted in any predicate.
3. **The features are not the model's to supply.** `ToolSurface.propose_verdict` takes
   `(work_key, outcome_class, reason_code, confidence, rationale, cited_row_refs)` and attaches
   the *deterministically computed* `FeatureVector` itself. A proposal cannot arrive with its own
   arithmetic, and it has no field for an amount or for a new transaction.

Two tests hold this down. `test_llm_has_no_privileged_path` runs a 24-cell grid of confidences ×
amounts through all three adjudicator values and asserts one distinct `(tier, action, blocking,
triggers)` per cell. `test_no_code_path_branches_on_the_adjudicator` reads the source of both
gate modules and fails on any `if`/`elif` mentioning `adjudicator` — a behavioural test can be
satisfied by a branch that happens not to fire on the grid; the structural one cannot.

---

## 4. The tool surface: the absence is the feature

`tieout/post/tools.py` exposes `ToolSurface`, whose public methods are **exactly** SPEC section
7's list — asserted by set equality in `test_tool_surface_is_exactly_the_spec_list`, so both
adding and removing a tool fails the suite:

```
read_work_item(work_key)            -> WorkItem
compute_features(work_key)          -> FeatureVector
propose_verdict(work_key, outcome_class, reason_code,
                confidence, rationale, cited_row_refs) -> ProposedVerdict
escalate(work_key, recommendation, evidence_refs)      -> QueueItem
refuse(work_key, reason_code, blocking_explanation)    -> Refusal
post_matched_entry(match_id: MatchId)                  -> JournalEntry
cite_prior_decision(decision_id)    -> PriorDecision
```

### What does not exist

| Absent function | Why |
|---|---|
| `create_adjusting_entry(account, amount, ...)` | the plug. There is no posting call that accepts an amount. |
| `force_balance(work_key)` | a balance is derived; there is nothing to force. |
| `write_suspense(amount)` | takes an amount; see the first row. |
| `set_threshold(name, value)` | policy is human-only. The gate reads `GatePolicy`, which is frozen, and the surface carries `policy_version` as a *string* — the agent records the policy in force and cannot reach the policy itself. |
| `mark_period_closed(period, force=True)` | closing belongs to the close gate, not the agent, and no `force` parameter exists anywhere (I4). |
| `edit_source_row(row_ref, ...)` | ingest is append-only. |
| `delete_event(event_id)` | the log is hash-chained; `tieout/audit/events.py` has no update or delete path either. |
| `read_expected_reconciliation()` | ground truth is outside the allowed-read set and is loaded only by the out-of-process scorer. |

`test_absent_functions_do_not_exist` checks all eight names against `tools`, `journal`, `decide`,
`tiers` and the `ToolSurface` class. The list is **transcribed into the test file**, not imported
from `tools.ABSENT_TOOLS` — a test that reads its policy from the module it polices can be
defeated by editing that module. `test_assert_absent_catches_a_reintroduced_plug` proves the
checker itself still bites, so the eight assertions cannot silently become vacuous.

Two further absences worth naming:

- **`MatchStore` has no `put`.** The posting path can read a persisted match and can never mint
  one. Persisting a match is the match layer's job, and it happens before the gate runs.
- **`Refusal` has no `blocking` parameter.** `blocking` is a field with a fixed default of
  `True`, not an argument. A refusal blocks; that is what a refusal is.

---

## 5. The invariants, and where each is enforced

### I1 — no posting without an admissible match

*Shape:* `post_matched_entry(match_id: MatchId) -> JournalEntry`. One parameter. Not an amount,
not an account, not a work key.

`MatchId` is a frozen dataclass, **not** a `str`. That matters: with a bare string identifier,
every string in the process is a candidate argument and `post_matched_entry("whatever")` is a
call somebody's agent eventually makes. With a distinct type that call is a `TypeError` before
it reaches any logic. The type is only the first line, though — `require_admissible_match()`
then resolves the id against the `MatchStore` and additionally requires a non-empty
`evidence_ref`. A match nobody can show a reviewer is not admissible, and `PersistedMatch`
declares `evidence_ref: str = Field(min_length=1)`, so an unevidenced match cannot be persisted
in the first place.

*Asserted by:* `test_no_post_without_match` (unresolvable id → `InvariantViolation`; bare string
→ `TypeError`; unevidenced match → `ValidationError`; and **no event is written** in any of the
three cases) and `test_post_matched_entry_takes_a_match_id_and_no_amount` (signature
introspection).

### I2 — debits equal credits by construction

*Shape:* the journal builder has no amount parameter. `build_entry(match)` derives every figure
from the matched source rows.

The construction is the invariant. A `JournalEntry` is a tuple of `BalancedPair`s — one debit
account, one credit account, **one** amount — and expanding a pair yields exactly one DR line and
one CR line carrying that same amount. There is no API that emits a single unpaired line, so
there is no expression in this system that denotes an unbalanced entry. Imbalance is not
detected; it is *unrepresentable*. Compare VynFi's GL fixture, which ships 353 deliberately
unbalanced JEs because in every other system this is a real failure mode.

The derivation itself: each processor event contributes cash-against-receivable for its `net`
and, if non-zero, fees-against-receivable for its `fee`, which together clear the gross. Where
there is no processor leg the ledger amount clears directly. **Bank rows contribute no amount of
their own** — they are the evidence that cash arrived. Taking a second, independent amount
source is precisely how a difference gets quietly absorbed, so the builder does not have one.

`require_balanced()` runs on every built entry. It can never fire; it exists so that if someone
ever adds an unpaired line type, it fires here rather than in a general ledger.

*Asserted by:* `test_journal_always_balances`, parametrised over **all eleven** SPEC section 3
outcome classes with awkward shapes on purpose — negative refunds, a partial refund that does not
divide evenly, a non-USD case, and three classes with a missing leg. It asserts the two side
totals are equal, that the total is quantised to the cent, and that every amount on the entry
came off a matched source row. `test_an_unbalanced_entry_cannot_be_constructed` asserts the
shape: `BalancedPair` has exactly one amount field, `JournalEntry` has none.

### I3 — ambiguity never resolves to a pick

*Shape:* a gate precondition, checked before tiering (§2 above). Also available standalone as
`invariants.require_unambiguous(candidate_count)` for callers outside the gate.

*Asserted by:* `test_ambiguity_never_picks` — injects two candidates inside tolerance at
confidence 0.99, asserts REFUSE, asserts the event log contains exactly one `REFUSE` event and
**no `POST` event**, and asserts the chain still verifies.

### I4 — a period with open REFUSE items cannot close

*Shape:* no `force` parameter exists. `invariants.assert_no_force_parameter(func)` introspects a
callable's signature against `OVERRIDE_PARAMETER_NAMES` = `{force, override, ignore_refusals,
skip_gate}` — a wider net than `force` alone, because the invariant is about override paths, not
about one spelling.

`invariants.require_no_open_refusals(dispositions)` is the gate-side half: it raises on any
disposition whose `blocking` flag is set, and it too has no bypass argument. The close gate
(`tieout/close/**`, a parallel worker's module) owns the state machine and the period lock.

*Asserted by:* `test_cannot_close_with_refusals` — a blocking disposition raises, a non-blocking
one does not, `ToolSurface` has no `mark_period_closed`, and a deliberately-bad local
`close_period(period, force=False)` **is** caught, so the introspection is not vacuous. The test
also conditionally imports `tieout.close.period` and checks every close/lock/certify function it
exposes; that check activates automatically the moment the close gate lands.

---

## 6. Decision memory: precedent accelerates, never rescues (SPEC section 9)

`decide(..., memory_confidence_lift=...)` is where `tieout/memory` hands the gate a precedent
lift. The memory module is another worker's file; **the bound is enforced here**, at the gate,
because trusting a caller to bound its own lift is not a bound.

Three things constrain it:

1. **A T3 never sees the lift at all.** Preconditions return before any lift logic, and a base
   tier of T3 (confidence below the escalate minimum) short-circuits too. A REFUSE stays a
   REFUSE regardless of how many similar items a human once approved.
2. **The magnitude is clamped** to `policy.max_memory_confidence_lift`. An absurd lift cannot
   leap two tiers.
3. **It can never produce a T0.** If the lifted confidence would reach the auto tier, the result
   is capped at T1. Precedent accelerates a decision; it does not confer full autonomy, and T0
   additionally requires a deterministic key match, which precedent is not.

Without bound 1 the memory becomes a laundering path for exactly the fabrication this system
exists to prevent: approve enough similar items and the refusals stop. This also answers the
standard objection — *if you don't trust the LLM to get it right, why trust it to fix it?* — the
memory only ever replays a **human's** judgement, attributed and timestamped.

*Asserted by:* `test_memory_cannot_rescue_refusal` (parametrised over lifts of 0, 0.05, 0.4, 1.0
and 99.0, against all three kinds of refusal) and `test_memory_lift_is_bounded_and_never_reaches_t0`.

---

## 7. Every decision emits a hash-chained event

`decide()` writes one event per decision through `tieout/audit/events.py` — the existing
hash-chained append-only log, reused, not reimplemented. The shape is SPEC section 8 verbatim:
`actor`, `action`, `work_key`, `outcome`, `reason`, `policy`, `features`, `evidence`, `blocking`,
with `seq`, `prev_hash` and `hash` supplied by the chain.

- **`actor`** defaults to `ServiceIdentity(name="tieout-agent", version=f"v{__version__}")` —
  a distinct service principal per deployed version, never a shared account (AS 1105 req. 1).
- **`reason`** is the first trigger that fired, falling back to the classifier's reason code. A
  refusal therefore logs *why* it refused, e.g. `L2_TWO_CANDIDATES_WITHIN_TOLERANCE`.
- **`features`** is rendered as decimal strings, never floats. The audit canonicaliser rejects
  `float` outright — money through a float is a defect — so `confidence` and `batch_completeness`
  are formatted through `Decimal` on the way in rather than handed over raw.
- **`policy`** is the verdict's own `policy_version` when it carries one, so a scoreboard can be
  recomputed against the policy in force at the time.

`ToolSurface` also records `POST`, `ESCALATE` and `REFUSE` events for its own calls.

*Asserted by:* `test_every_disposition_writes_one_chained_event` — one event per decision, chain
verifies, actions match the dispositions, blocking flag set on the refusal, no float anywhere in
any `features` block.

---

## 8. Reward-hacking guards: SPEC section 6's table vs. what is implemented

The reference failure is the Darwin Gödel Machine, which — asked to reduce hallucination —
deleted the logging tokens its detector relied on, defeating the measurement instead of the
problem. Each guard closes one avenue.

| Avenue | SPEC's guard | Implemented here? |
|---|---|---|
| Loosen thresholds to make items pass | Policy read-only to the agent; changes are human, versioned, attributed | **Yes, in this task's scope.** `GatePolicy` is a frozen pydantic model; the gate has no setter and no default for any threshold (a missing one raises `PolicyIncomplete` rather than being invented); `ToolSurface` holds `policy_version` as a string and has no `set_threshold`. Versioning and attribution of policy *changes* live in `tieout/policy/**` (another worker). |
| Edit or delete source rows | Ingest append-only; every file SHA256'd into the run manifest | **Not this task.** `edit_source_row` is absent from the tool surface, which is the part I own; append-only ingest and the manifest are `tieout/ingest/**` (merged, `manifest.py`). |
| Tamper with the scorer | Scoring out-of-process; ground truth outside the allowed-read set | **Not this task.** `read_expected_reconciliation` is absent from the tool surface; the isolation itself is `tieout/ingest/paths.py` and `tieout/score/**`. |
| Delete inconvenient log entries | Append-only hash-chained log; `tieout audit verify` detects any break | **Yes, by reuse.** The gate writes through `tieout/audit/events.py`, which has no update and no delete path. `delete_event` is absent from the tool surface. |
| Mark a period closed anyway | Invariant I4; no override parameter exists | **Half.** `assert_no_force_parameter` and `require_no_open_refusals` are implemented and tested here, and `mark_period_closed` is absent from the tool surface. The period state machine and lock are the close gate's (`tieout/close/**`), and my test checks its signatures automatically once it exists. |
| **Plug the difference** | **Invariants I1 + I2. Unrepresentable.** | **Yes. This is the task.** No posting call accepts an amount; amounts are derived; entries are tuples of balanced pairs. |

---

## 9. Coupling to work still in flight

`tieout/policy/**` and `tieout/match/**` were being built in parallel with this gate and did not
exist when it was written. Rather than guess at imports, the gate is coupled to each through
**one narrow, structurally-typed adapter**, so a rename on either side is a one-line fix:

| Dependency | Adapter | What a rename costs |
|---|---|---|
| `tieout.policy` | `tiers.read_policy()` + the `POLICY_PATHS` table | one line in `POLICY_PATHS` |
| `tieout.match` | `decide.read_verdict()` + `VERDICT_FIELDS` / `FEATURE_FIELDS` | one line in the adapter |
| a persisted match store | `journal.MatchStore` protocol | implement `get()`; nothing in `tieout/post` changes |
| ingest / features / memory / queue | the protocols in `tools.py` | satisfy the protocol |

Each adapter walks attributes *or* mapping keys, so it accepts a pydantic model, a plain object
or `yaml.safe_load` output. `tests/test_invariants.py` feeds the gate a plain `dict` in SPEC
section 3's shape specifically to prove the adapter works on a foreign shape.

**No policy logic and no matching logic is implemented in the gate.** No tolerance is applied
here and no feature is computed here. In particular:

- **`red_flags` (AS 2401 ¶.61) and `qualitative_overrides` (SAB 99) are *supplied* to `decide()`**
  by the policy layer. The gate consumes findings; it does not make materiality judgements.
- **"Within tolerance" was decided by the match layer** when it counted the candidates. The gate
  reads `candidate_count` and nothing else about tolerance.
- **`ToolSurface.compute_features` delegates** to an injected `FeatureSource`.

---

## 10. Honest gaps — what this task did *not* implement

- **The close state machine.** I4 is asserted here (`require_no_open_refusals`,
  `assert_no_force_parameter`) but the period lifecycle, the lock and the aging clocks are
  `tieout/close/**`, another worker's files. My I4 test introspects that module's signatures
  conditionally and starts checking them the moment it lands.
- **`policy.yaml` and its loader.** `read_policy` consumes the SPEC section 4 shape; nothing here
  parses or validates the YAML, and `docs/POLICY.md` is the policy worker's.
- **`max_memory_confidence_lift` has a default (0.05).** SPEC section 9 requires the lift to be
  bounded but gives no number, and `policy.yaml`'s sketch has no field for one. The gate reads
  `memory.max_confidence_lift` from the policy when present and otherwise falls back to 0.05.
  This is the only number in the gate that is not read from policy, and it is a *ceiling*, so the
  default is conservative in the safe direction. If the policy layer adds the field, the default
  stops being used.
- **`batch_incompleteness_explained` is a caller assertion.** The gate cannot tell an explained
  incompleteness from an unexplained one without doing matching, so it takes the caller's word —
  defaulting to unexplained, which refuses. If the match layer never passes `True`, the gate is
  strictly more conservative than the spec, not less.
- **The audit `log` argument is optional.** `decide(..., log=None)` returns a disposition without
  writing an event, which is what the pure unit tests use. On the reconcile path the CLI must
  supply the log. This is a genuine soft spot: the invariant "every decision emits an event" is
  currently enforced by convention at the call site, not by the type. Making `log` mandatory
  would close it, at the cost of a temp file in every unit test.
- **`ProposedVerdict` is a local model.** SPEC section 3's `Verdict` belongs to `tieout/match`,
  which did not exist. `tools.propose_verdict` returns a structurally identical local model; when
  `tieout.match` ships its `Verdict`, this should become an import. `decide()` already accepts
  either, because it reads verdicts structurally.
- **The chart of accounts is three constants.** Real GL account mapping is out of scope; the
  accounts are deliberately not configurable from the agent's side, because a settable account is
  another surface on which to hide a difference.

---

## Running the checks

```bash
uv run pytest tests/test_invariants.py -v
uv run ruff check .
```
