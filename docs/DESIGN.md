# Tieout — Design Specification

**The close agent that refuses to plug — because plugging is unrepresentable in its tool surface, not because we asked it nicely.**

| | |
|---|---|
| **Event** | Syndicate by Maximor, 5–7 Sep 2026 |
| **Track** | 2 — Autonomous Office of the CFO |
| **Anchor workflow** | Bank reconciliation (ledger ↔ processor ↔ bank) |
| **Dataset** | ReconRiver `month-end-close` (CC BY 4.0, labelled) |
| **Headline metric** | Fabrication rate. Target: 0 |
| **Spec version** | v1 — 5 Sep 2026 |

---

## Table of Contents

1. [Thesis](#1-thesis)
2. [Architecture](#2-architecture)
3. [Data Model](#3-data-model)
4. [Layer 1 — The Policy Layer](#4-layer-1--the-policy-layer)
5. [Layer 2 — The Match Pipeline](#5-layer-2--the-match-pipeline)
6. [The Refusal Gate](#6-the-refusal-gate)
7. [The Constrained Tool Surface](#7-the-constrained-tool-surface)
8. [Layer 3 — The Audit Trail](#8-layer-3--the-audit-trail)
9. [Decision Memory](#9-decision-memory--never-asks-twice)
10. [The Close Gate](#10-the-close-gate)
11. [The Scoreboard](#11-the-scoreboard)
12. [Interfaces](#12-interfaces)
13. [Code Layout](#13-code-layout)
14. [Tests](#14-tests-that-earn-their-place)
15. [Demo Script](#15-the-demo-video--shot-by-shot)
16. [Business Model](#16-business-model)
17. [Build Plan & AO Delegation](#17-build-plan--ao-delegation)
18. [Cut Lines & Risks](#18-cut-lines--risks)
19. [Open Questions & Assumptions](#19-open-questions--assumptions)

---

## 1. Thesis

Frontier models fail at closing the books in one specific, documented way. Given a mismatch they cannot resolve, they **fabricate a transaction to satisfy the validation check.**

[AccountingBench](https://accounting.penrose.com/) — the only independent benchmark in finance AI — gives frontier models a real SaaS company's full year of data (Ramp, Rippling, Stripe, Mercury) and asks them to close the books month by month against a CPA-prepared baseline. Results:

- **o3, o4-mini and Gemini 2.5 Pro could not complete even one month.**
- **Claude and Grok 4** tracked ~1% from the CPA baseline for the first few months, then diverged by **more than 15% of overall balance — roughly $500,000** for that company.
- **Subscription revenue** — all revenue for that business — was consistently **overstated by 5–30%**, even for the best model.

The four documented failure modes:

1. **Reconciliation hacking** — rather than resolve genuine mismatches, models fabricate transactions or pull in unrelated entries to satisfy validation checks, *in violation of explicit instructions*.
2. **Error accumulation** — when reconciliation fails, models "become confused and introduce additional errors rather than recover."
3. **Accrual reversion** — struggle with deferred revenue and accrued expenses, "sometimes reverting to cash-basis approaches despite contrary instructions."
4. **Double-counting** without the ability to undo, carried forward into future months.

From a benchmark team member on Hacker News:

> The failures aren't exclusively a context length problem, as we reset the context monthly… **the types of errors appear to be more reward hacking vs pure hallucinations.**

Every vendor response to this is a prompt instruction: *do not fabricate.* **That is the wrong layer.** A model that reward-hacks a validation check will reward-hack an instruction not to.

### The design thesis, in one sentence

> **Tieout does not ask the agent not to plug. It removes the capability.**
>
> There is no tool that posts an entry with a free-text amount. Every posting call requires a `match_id` referencing an admissible, evidenced match. A plug is not forbidden — it is **unrepresentable**.

### Why this is the right problem

**The regulator agrees.** PCAOB **AS 2401 ¶.61** names the forced balancing entry — unusual or seldom-used account, period-end timing, little or no explanation, round numbers — as precisely the profile auditors must fraud-test for management override. *A system that plugs to close is a system that manufactures audit findings.* The PCAOB further warns that override risk "is not limited to journal entries processed manually" — **an automated JE gets more scrutiny, not less.**

**The judge agrees.** Maximor's CEO has published the same idea as a product thesis:

> The product is built around the remaining 1%: **knowing when to stop**, what to escalate, whom to bring in, and how to show your work.
>
> — Ramnandan Krishnamurthy, *"What we mean by autonomous finance,"* Aug 2026

**The data supports scoring it.** ReconRiver ships labelled ground truth including `AMBIGUOUS_MATCH` and `MISSING_*` rows — exactly where AccountingBench models fabricate. We can *demonstrate* the refusal, not assert it.

### What is deliberately NOT the product

- **Not the matching quality.** Fuzzy transaction matching is commodity — Numeric claims 90%+ of bank recs automated; BlackLine ships Verity Prepare. Concede this before a judge raises it.
- **Not a new ledger.** No ERP replacement, no connectors, no OAuth. Tieout reads three files and emits decisions plus evidence.
- **Not full autonomy theatre.** But equally **not undifferentiated human-in-the-loop** — the judge is on record calling that *"code for 'we like being slow'."* The answer is confidence-tiered autonomy: auto-post below threshold, escalate above, refuse when inadmissible.

---

## 2. Architecture

Deliberately mapped onto Maximor's own three published layers. Speaking a judge's vocabulary back to them is free.

| Layer | Their words | What we build |
|---|---|---|
| **1 — Policy** | *"Encodes your accounting logic, not generic rules."* | Materiality and tolerance as first-class versioned objects with provenance — who set it, when, on what rationale. Not config constants. |
| **2 — Agents** | *"Processing, matching, reconciling, posting."* | Blocking → features → deterministic classification → LLM adjudication on the residual only → the refusal gate assigns one of four dispositions. |
| **3 — Audit** | *"Deterministic, explainable, auditable."* | Hash-chained append-only event log plus evidence packs — the six things AS 1105 ¶.10 makes testable. |

### Flow

```
  three source files          ledger · processor · bank
          │
          ▼
  INGEST                      canonical model, SHA256 per file, append-only
          │
          ▼
  BLOCKING                    candidate groups on join keys + amount + date window
          │
          ▼
  FEATURES                    amount Δ, date Δ, ref match, fee-explained Δ, currency
          │
          ▼
  CLASSIFY (deterministic)    outcome class + reason code + confidence
          │
          ├── resolved ────────────────────────────┐
          │                                        │
          ▼ residual only                          │
  ADJUDICATE (LLM, optional)  structured verdict, never a free amount
          │                                        │
          └────────────────┬───────────────────────┘
                           ▼
                  ┌─────────────────┐
                  │ THE REFUSAL GATE│
                  └────────┬────────┘
                           │
     ┌─────────────┬───────┴───────┬──────────────┐
     ▼             ▼               ▼              ▼
 AUTO_POST   AUTO_SAMPLED      ESCALATE        REFUSE
     │             │               │              │
     └──────┬──────┘               ▼              ▼
            ▼                 review queue   BLOCKS THE CLOSE
     constrained post         (decision memory)
            │
            ▼
    EVENT LOG (hash-chained) ──► EVIDENCE PACK ──► SCOREBOARD
```

### Stack

| Concern | Choice | Why |
|---|---|---|
| Language | **Python 3.11+** | Maximor's job postings: *"Our stack is Python."* Deliberate signal. |
| Data | pandas + stdlib `decimal` | **Never float for money.** `Decimal` with explicit `ROUND_HALF_UP` — ReconRiver's own fee policy is HALF_UP. |
| Validation | pydantic v2 | Schema validation at every boundary; frozen models for immutability. |
| LLM | `claude-sonnet-5` via Anthropic SDK, structured output | Adjudication only, on the residual. Swappable and **optional**. |
| API | FastAPI + uvicorn | Serves JSON to a static dashboard. No build step. |
| Frontend | Vanilla HTML/CSS/JS reading JSON | Zero toolchain. In a 30-hour window a build step is a liability. |
| Observability | **Neatlogs** (`pip install neatlogs`) | Sponsor tool, MIT, ~2 lines, produces the reliability evidence the rubric asks for. |
| Tests | pytest | Concentrated on gate invariants, not coverage theatre. |
| Storage | JSONL event log + SQLite read model | Append-only log is the source of truth; SQLite is derived. |

> **Resilience decision worth stating in the demo: the system runs end-to-end with zero LLM calls.**
> Deterministic classification handles the bulk and the refusal gate is pure logic. LLM adjudication improves the tail but is never a dependency. If rate limits, credits or the API fail at hour 26, the demo still runs and the scoreboard still computes.

---

## 3. Data Model

### Sources — ReconRiver `month-end-close`

| File | Rows | Key fields |
|---|---:|---|
| `internal_transactions.csv` | 10,000 | `internal_payment_id, merchant_order_id, occurred_at, gross_amount, currency, payment_status, payment_method` |
| `processor_transactions.csv` | 10,200 | `processor_transaction_id, merchant_order_id, processor_event_type, processor_event_time, gross_amount, fee_amount, net_amount, settlement_batch_id, processor_status` |
| `bank_settlements.csv` | 1,499 | `bank_entry_id, settlement_batch_id, booked_at, credited_amount, bank_reference, description` |
| `expected_reconciliation.csv` | 11,539 | `expected_outcome, expected_reason_code, expected_difference, explanation` — **held out; never read by the agent** |
| `scenario_manifest.json` | — | seed, **fee policy 2.90% + 0.30 HALF_UP**, settlement window, SHA256s, injected-exception counts |

The bank side is 1,499 rows against 10,000 payments — **one deposit settles many transactions**. That many-to-one shape is the canonical hard case, and it is where ambiguity lives.

> ### Ground-truth isolation is an architectural constraint, not a convention
>
> `expected_reconciliation.csv` is loaded **only** by the scoring process, which runs **out-of-process** from the agent. The agent's ingest module physically cannot open it — the path is not in its allowed-read set.
>
> This guards against two things: reproducing the AccountingBench failure accidentally, and the Darwin Gödel Machine failure mode where an agent asked to reduce hallucination **deleted the logging tokens its detector relied on** — defeating the measurement instead of the problem.

### Canonical model

All frozen. Immutable in, immutable out — new objects, never mutation.

```
Money          = Decimal          # ROUND_HALF_UP, 2dp, currency-tagged

LedgerEntry    id, order_key, occurred_at, amount: Money, currency,
               status, method, source_row_ref

ProcessorEvent id, order_key, event_type, event_time, gross: Money,
               fee: Money, net: Money, batch_key, status, source_row_ref

BankEntry      id, batch_key, booked_at, credited: Money, reference,
               description, source_row_ref

WorkItem       work_key                    # the unit of reconciliation
               ledger:    [LedgerEntry]
               processor: [ProcessorEvent]
               bank:      [BankEntry]

FeatureVector  amount_delta: Money         fee_explained_delta: Money
               date_delta_days: int        currency_mismatch: bool
               ref_match: enum{EXACT, PARTIAL, NONE}
               candidate_count: int        batch_completeness: float
               # every field derived deterministically; no LLM in this struct

Verdict        work_key, outcome_class, reason_code,
               confidence: float, rationale: str,
               features: FeatureVector, policy_version: str,
               adjudicator: enum{DETERMINISTIC, LLM, HUMAN}

Disposition    verdict, tier,
               action: enum{AUTO_POST, AUTO_SAMPLED, ESCALATE, REFUSE},
               blocking: bool, triggers: [str]
```

### Outcome classes — mirrored from ReconRiver's own taxonomy

| Class | In scenario | Deterministic rule | Typical disposition |
|---|---:|---|---|
| `MATCHED` | 11,139 | Exact key + amount within trivial tolerance + within settlement window | AUTO_POST |
| `REFUND_MATCHED` | 100 | Negative-signed counterpart to a prior match, same order key | AUTO_POST |
| `PARTIAL_REFUND` | 100 | Negative counterpart, \|amount\| < original | AUTO_SAMPLED |
| `LATE_SETTLEMENT` | 40 | Key matches, `date_delta > settlement_window` | AUTO_SAMPLED |
| `AMOUNT_MISMATCH` | 40 | Key matches, delta > tolerance, not fee-explained | ESCALATE |
| `FEE_MISMATCH` | 20 | Delta reconciles to a fee deviating from the 2.90% + 0.30 policy | ESCALATE |
| `CURRENCY_MISMATCH` | 20 | Currency codes differ across sides | ESCALATE |
| `MISSING_PROCESSOR` | 30 | Ledger entry with no processor event | **REFUSE** |
| `MISSING_INTERNAL` | 20 | Processor event with no ledger entry | **REFUSE** |
| `MISSING_BANK_SETTLEMENT` | 20 | Settled batch with no bank credit | **REFUSE** |
| `AMBIGUOUS_MATCH` | 10 | **≥2 admissible candidates within tolerance** | **REFUSE** |

**The 80 rows across the four REFUSE classes are the entire point of the project.** They are exactly where AccountingBench models fabricate.

---

## 4. Layer 1 — The Policy Layer

> ### Why this layer exists at all
>
> SEC **SAB 99** states that exclusive reliance on any percentage or numerical threshold *"has no basis in the accounting literature or the law"* — a percentage is *"only the beginning of an analysis of materiality."*
>
> Yet every tool in this market ships thresholds as config constants. **Threshold governance is a genuinely underbuilt surface**, and it is where Tieout's novelty score comes from.

### `policy.yaml` — every threshold carries provenance

```yaml
version: "2026.01-r3"
effective_from: 2026-01-01
entity: ACME-US
supersedes: "2026.01-r2"

materiality:
  overall:
    value: 750000.00          # AS 2105: must be a specified amount
    basis: "0.5% of revenue"  # practice band 0.5–7%
    set_by: "controller@acme"
    set_at: 2026-01-02T09:14:00Z
    rationale: "FY26 planning revenue $150M; conservative end of band"
  performance:
    value: 450000.00          # AS 2105: must be < overall
    basis: "60% of overall"   # practice band 50–75%
    rationale: "Aggregation risk across 3 entities"
  clearly_trivial:
    value: 30000.00           # practice band 3–5% of overall
    basis: "4% of overall"

tolerances:                   # by category, NOT universal
  - category: card_settlement
    amount_abs: 0.02
    amount_pct: 0.0005
    date_window_days: 3
    rationale: "Processor rounding + T+2 settlement"
  - category: wire
    amount_abs: 0.00          # wires must match to the cent
    date_window_days: 1
  - category: fx_settlement
    amount_pct: 0.005
    date_window_days: 5
    rationale: "Rate timing between booking and credit"

fee_policy:                   # read from ReconRiver's manifest at runtime
  pct: 0.0290
  fixed: 0.30
  rounding: HALF_UP

confidence_tiers:
  auto:          {min_confidence: 0.95, max_amount: clearly_trivial}
  auto_sampled:  {min_confidence: 0.90, max_amount: performance,
                  sample_rate: 0.05}
  escalate:      {min_confidence: 0.60}
  # below 0.60, or inadmissible, or ambiguous → REFUSE

qualitative_overrides:        # SAB 99 — force escalation regardless of amount
  - crosses_covenant_threshold
  - changes_sign_income_to_loss
  - related_party_counterparty
  - masks_trend_reversal
  - affects_management_compensation
  - conceals_unlawful_transaction

je_red_flags:                 # AS 2401 ¶.61 applied to OUR OWN output
  - round_number_amount
  - seldom_used_account
  - post_close_timing
  - unusual_initiator
  - no_supporting_explanation

aging:
  reconcile_within_working_days: 30      # U. of Houston MAPP 05.04.06
  suspense_resolve_within_days: 60       # VA Financial Policy Ch. 1
  escalate_to_controller_after_days: 30
  buckets: [30, 60, 90, 120]
```

### SAB 108 — both methods, always

Every proposed adjustment is quantified two ways and is material if **either** is material. This is a legal requirement most tools skip, and it is four lines of code.

| Method | Quantifies | Consequence |
|---|---|---|
| **Rollover** | The amount of the error originating in the current-year income statement | Balance-sheet errors accumulate silently across years |
| **Iron curtain** | The effect of correcting the misstatement in the year-end balance sheet, irrespective of year of origination | Catches the accumulation the rollover method hides |

SAB 108: *"financial statements would require adjustment when **either** approach results in quantifying a misstatement that is material."*

### AS 2401 ¶.61 applied to our own journal entries

> **A novel, nearly-free feature.** The PCAOB requires auditors to fraud-test entries that hit unusual or seldom-used accounts, are recorded at period end or post-close, have little or no explanation, or contain round numbers.
>
> Tieout runs those exact criteria **against the journal entries it proposes itself** and escalates any that trip them.
>
> *"We run AS 2401 against our own output"* is the single most domain-literate sentence available in this project.

The agent has **read-only** access to policy. Policy changes are a human action, versioned, with rationale, and every decision records the `policy_version` it was made under — so a scoreboard can be recomputed against the policy in force at the time.

---

## 5. Layer 2 — The Match Pipeline

1. **Ingest & normalise.** Three CSVs → canonical frozen models. SHA256 every input file into the run manifest. Validate at the boundary with pydantic; **reject rather than coerce**. Every row keeps a `source_row_ref` so lineage survives to the evidence pack. Malformed rows are quarantined with a reason, never silently dropped — ReconRiver's `mixed-exceptions` scenario deliberately ships malformed rows and a duplicated source file.

2. **Blocking.** Generate candidate `WorkItem`s cheaply: exact join on `merchant_order_id`, then `settlement_batch_id` for the bank leg, then a fallback block on (amount bucket × date window × currency) for orphans. Pure pandas; handles the bulk at near-zero cost.

3. **Feature computation.** Deterministic, auditable, no LLM. Amount delta in `Decimal`; date delta in days; reference match strength; **fee-explained delta** (does the gap reconcile to exactly 2.90% + 0.30 HALF_UP?); currency comparison; candidate count; batch completeness (do the constituent transactions sum to the bank credit?).

4. **Deterministic classification.** A rule cascade, ordered most-specific first, emitting outcome class + reason code + confidence. Fee-explained gaps become `FEE_MISMATCH`, not `AMOUNT_MISMATCH`. **Two or more admissible candidates becomes `AMBIGUOUS_MATCH` — never a pick.** Expect this stage to resolve the large majority of the 11,539 items on its own.

5. **LLM adjudication — residual only.** Only items the cascade leaves at low confidence reach a model. The prompt receives the feature vector, the candidate rows, and the policy in force. It returns **structured output only**: `{outcome_class, reason_code, confidence, rationale, cited_row_refs}`. It cannot return an amount. It cannot return a new transaction. Its verdict is re-run through the same refusal gate as everything else, **with no privileged path**.

6. **The refusal gate.** See §6.

> ### Why deterministic-first is not laziness
>
> It is the defence against three separate documented failures:
> - **Cost** — Anthropic measured multi-agent systems at ~15× chat tokens.
> - **Reliability** — the corpus's #1 production complaint is non-determinism, and a rule cascade is reproducible by construction.
> - **Auditability** — AS 1105 ¶.10 requires testing the *accuracy and completeness* of machine-produced information, far easier for a rule than for a sampled generation.
>
> The LLM earns its place on the tail, which is exactly where research says the value and the cost both live.

---

## 6. The Refusal Gate

The core of the system. **Four dispositions, and there is no fifth.**

### T0 · AUTO_POST
```
conf ≥ 0.95
∧ |amt| < clearly_trivial
∧ deterministic key match
∧ no red flag, no qualitative override
```
Posts. Logged with full evidence. No human touch.

### T1 · AUTO_SAMPLED
```
conf ≥ 0.90
∧ |amt| < performance_materiality
```
Posts, with 5% randomly sampled into the review queue for control evidence.

### T2 · ESCALATE
```
conf ≥ 0.60
∨ |amt| ≥ performance_materiality
∨ qualitative override fired
∨ AS 2401 red flag fired
```
Human queue with the recommendation, the reason code, the feature deltas and the evidence. Does not block the close if below performance materiality.

### T3 · REFUSE — blocks the close
```
no admissible match
∨ conf < 0.60
∨ ≥2 candidates within tolerance
∨ batch incompleteness unexplained
```
**Cannot be posted at all.** The period cannot close while any REFUSE item is open. **No override path exists in code.**

### The four invariants — asserted in code, tested in CI

| # | Invariant | Enforced by |
|---|---|---|
| **I1** | **No posting without an admissible match.** Every journal entry references a `match_id` resolving to a persisted, evidenced match | Type signature — `post()` takes `MatchId`, not an amount |
| **I2** | **Debits equal credits by construction.** Entry amounts are *derived* from matched source rows, never supplied | Journal builder has no amount parameter |
| **I3** | **Ambiguity never resolves to a pick.** `candidate_count ≥ 2` within tolerance forces REFUSE | Gate precondition, checked before tiering |
| **I4** | **A period with open REFUSE items cannot close.** No flag, env var or CLI option overrides this | Close gate; the function has no `force` parameter |

### Reward-hacking guards

The Darwin Gödel Machine, asked to reduce hallucination, **deleted the logging tokens its detector relied on** — defeating the measurement instead of the problem. That is the reference failure. Each guard closes one avenue:

| Avenue | Guard |
|---|---|
| Loosen thresholds to make items pass | Policy is read-only to the agent. Changes are human, versioned, attributed. |
| Edit or delete source rows | Ingest is append-only; every file SHA256'd into the run manifest; hashes re-verified before scoring. |
| Tamper with the scorer | Scoring runs **out-of-process**; ground truth is outside the agent's allowed-read set. |
| Delete inconvenient log entries | Event log is append-only and **hash-chained**; `tieout audit verify` detects any break. |
| Mark a period closed anyway | Invariant I4. No override parameter exists. |
| **Plug the difference** | **Invariants I1 + I2. Unrepresentable.** |

---

## 7. The Constrained Tool Surface

This is where the thesis becomes concrete. **Read the signatures — the absence is the feature.**

```python
# ─── What the agent CAN do ───────────────────────────────────

read_work_item(work_key)            -> WorkItem
compute_features(work_key)          -> FeatureVector
propose_verdict(work_key, outcome_class, reason_code,
                confidence, rationale, cited_row_refs) -> Verdict
escalate(work_key, recommendation, evidence_refs)      -> QueueItem
refuse(work_key, reason_code, blocking_explanation)    -> Refusal
post_matched_entry(match_id: MatchId)                  -> JournalEntry
                                       # amounts DERIVED from the
                                       # matched rows. No amount param.
cite_prior_decision(decision_id)    -> PriorDecision


# ─── What does not exist, and why ────────────────────────────

create_adjusting_entry(account, amount, ...)   ← the plug. Absent.
force_balance(work_key)                        ← absent.
write_suspense(amount)                         ← absent.
set_threshold(name, value)                     ← policy is human-only.
mark_period_closed(period, force=True)         ← no force param exists.
edit_source_row(row_ref, ...)                  ← ingest is append-only.
delete_event(event_id)                         ← log is hash-chained.
read_expected_reconciliation()                 ← outside allowed-read set.
```

> ### Say this line in the demo, verbatim
>
> *"AccountingBench models plug because they can. We didn't prompt ours not to — we deleted the tool. There is no function in this system that posts an amount somebody didn't match. The plug isn't forbidden; it's unrepresentable."*

One consequence worth naming: because `post_matched_entry` **derives** amounts rather than accepting them, an **unbalanced journal entry cannot be constructed**. Compare VynFi's GL fixture, which ships 353 deliberately unbalanced JEs precisely because that is a real-world failure. Tieout's type system makes it *impossible* rather than *detectable*.

---

## 8. Layer 3 — The Audit Trail

PCAOB **AS 1105 ¶.10** requires the auditor to *"test the accuracy and completeness of the information, or test the controls over [it], including information technology general controls."* That is the "completeness and accuracy of IPE" requirement — why auditors ask *show me the report you pulled this from, and prove nobody edited it.*

Six things must therefore be logged:

| # | Requirement | Implementation |
|---|---|---|
| 1 | Initiating identity — a **distinct bot/service identity, not a shared account** | `actor: "svc:tieout-agent@v0.3.1"` vs `actor: "human:controller@acme"`. Never interchangeable. |
| 2 | Source data lineage back to the upstream extract, plus evidence the extract was itself tested | `source_row_ref` on every row → run manifest with per-file SHA256 → re-verified at scoring time |
| 3 | Approval by a party **distinct from the initiator** (maker-checker / four-eyes) | Enforced: `approver_id != initiator_id`, rejected at write time |
| 4 | Creation, review and posting timestamps — AS 2401 keys on period-end timing | `created_at`, `reviewed_at`, `posted_at`, all UTC ISO-8601 |
| 5 | Immutability and a unique ID | Append-only JSONL; each event carries `prev_hash` forming a chain |
| 6 | Attached supporting documentation | Evidence pack per decision, addressed by content hash |

2024 PCAOB inspections found **ITGC testing gaps were the leading reason auditors couldn't rely on automated controls** — across six global network firms, 68% of engagements had an ICFR deficiency.

### Event record

```json
{
  "event_id":  "evt_01HQ...",
  "seq":       14071,
  "prev_hash": "9f2c1a...",
  "hash":      "3e77bd...",
  "at":        "2026-09-06T04:12:09Z",
  "actor":     "svc:tieout-agent@v0.3.1",
  "action":    "REFUSE",
  "work_key":  "wk_batch_4471",
  "outcome":   "AMBIGUOUS_MATCH",
  "reason":    "L2_TWO_CANDIDATES_WITHIN_TOLERANCE",
  "policy":    "2026.01-r3",
  "features":  { "amount_delta": "0.00", "candidate_count": 2 },
  "evidence":  "ev_sha256:c41f...",
  "blocking":  true
}
```

`hash = sha256(canonical(event) + prev_hash)`

### Evidence pack

One bundle per decision, content-addressed:
- the candidate source rows verbatim
- the computed feature vector
- the policy version and the specific thresholds applied
- the disposition and rationale
- any cited prior human decision
- the reviewer action with identity and timestamp

This makes *"show your work"* a **property of the system** rather than a report someone assembles later.

> **Retrofitting this is impossible** — identity, lineage and timestamps have to be captured at the moment of the decision. Build it from the first commit, not at hour 26.

---

## 9. Decision Memory — "Never Asks Twice"

> When it's confident, it acts. When it isn't, it escalates to your team — **and remembers the answer, so it never asks twice.**
>
> — Maximor CEO. Implement this literally.

Every human review writes a `PriorDecision`: the feature vector, the reason code, the human's verdict, their rationale, their identity and the timestamp.

On subsequent runs, before escalating, the gate looks for a prior decision with the **same reason code** and a feature vector within a similarity threshold. If one exists it is **cited** in the recommendation, and confidence is lifted by a **bounded** increment — enough to promote a borderline T2 into T1, never enough to promote anything into T0 or to rescue a T3.

> ### The bound is deliberate and must be stated
>
> Learned precedent can **accelerate** a decision; it can never **create admissibility**. A REFUSE stays a REFUSE no matter how many similar items a human once approved — otherwise the memory becomes a laundering path for exactly the fabrication the system exists to prevent.
>
> This also answers the standard objection — *"if you don't trust the LLM to get it right, why trust it to fix it?"* — because the memory only ever replays a **human's** judgment, attributed and timestamped.

Implementation is deliberately dull: reason code as an exact-match bucket, then nearest-neighbour over the normalised numeric features within that bucket. No embeddings, no vector store.

```python
# ponytail: linear scan over decisions; add an index if the queue
# outgrows a few thousand items
```

---

## 10. The Close Gate

The demo's money shot.

Published close policies converge on one state machine, and Tieout implements it directly:

```
Not started
   → In preparation      (preparer owns)
   → Submitted for review (reviewer owns)
   → [Rejected → back to preparer]
   → Approved / certified
   → Period locked        (immutable)
```

…with an **auto-certification bypass** below the configured variance threshold — management's own materiality decision as configuration, *not* a regulator-mandated number.

```
$ tieout close --period 2026-01

  Reconciliation summary          policy 2026.01-r3
  ─────────────────────────────────────────────────────────
  work items                              11,539
  auto-posted            T0               10,412    90.2%
  auto-posted, sampled   T1                  927     8.0%   (46 sampled)
  escalated              T2                  120     1.0%
  refused                T3                   80     0.7%
  ─────────────────────────────────────────────────────────
  straight-through rate                    98.2%
  fabricated matches                           0

  ✕ CLOSE REFUSED

  80 items are inadmissible and block this period:

    MISSING_BANK_SETTLEMENT     20   $  412,880.14
    MISSING_PROCESSOR           30   $  109,442.00
    MISSING_INTERNAL            20   $   88,120.55
    AMBIGUOUS_MATCH             10   $   47,900.00
                                     ─────────────
    total blocking                   $  658,342.69

  Blocking total exceeds performance materiality
  ($450,000.00). The period cannot be certified.

  Next: resolve via `tieout queue --blocking`
  No override exists. This is invariant I4.
```

Contrast that with what AccountingBench documents happening today: **the books close, they balance, and the divergence surfaces months later at 15% of balance.** A refusal is not a failure of the system — *it is the system's output*, and the only honest one available given the data.

### Aging and escalation

Open items age into buckets of 30 / 60 / 90 / 120 days.

- **U. of Houston MAPP 05.04.06** — reconciliation due within 30 working days; unresolved items escalated to the Controller after 30 days.
- **VA Financial Policy Ch. 1** — suspense differences *"researched, resolved, and explained within 60 days."*
- **California SAM §8294** — AR reconciliations monthly within 30 days; records retained 4 years.

The queue sorts by **materiality × age**, so the largest oldest break is always first.

> **Negative finding carried from research:** no public policy publishes a dollar write-off authority threshold — those live in internal delegation-of-authority manuals. Tieout therefore treats write-off authority as a policy field **with no default value**, and refuses to act on it until set.

---

## 11. The Scoreboard

This is what satisfies the rubric's "evidence of measurable results." **It runs out-of-process against held-out labels.**

### Seven metrics

| Metric | Definition | Why it's here |
|---|---|---|
| **Fabrication rate** *(headline)* | Posted matches with no ground-truth counterpart, ÷ posted | The AccountingBench failure, measured directly. Target 0. |
| **Straight-through rate** | Auto-posted ÷ total work items | Without it, "refuse everything" scores perfectly. The necessary counterweight. |
| Per-class precision / recall | Across all 11 outcome classes | Shows the system distinguishes *kinds* of break. Note the research finding that error-*type* classification is far harder than localisation — 22.2% macro-F1 in the agent literature. |
| **Escalation precision** | Of items escalated, the share genuinely needing a human (not `MATCHED` in ground truth) | Catches over-escalation — the judge's *"we like being slow"* failure. |
| **Materiality-weighted error** | Dollar-weighted rather than row-weighted | A $0.02 miss is not a $50,000 miss. Row-weighted metrics hide the only errors that matter. |
| Cost & latency | Per 1,000 work items — tokens, USD, wall-clock | Three of the rubric's four named axes. Deterministic-first should show a startling number. |
| **pass^k reliability** | Identical decisions across k=5 repeated runs | Non-determinism is the corpus's #1 production complaint; τ-bench established pass^k. A deterministic cascade should approach 1.0. |

### Three baselines — the measurable improvement

| Baseline | What it is | Expected shape |
|---|---|---|
| **A · Naive LLM** | The three files handed to a model with "reconcile these," no tool constraints, no gate | **Should fabricate — reproducing AccountingBench on your own bench.** High STP, non-zero fabrication. |
| **B · Deterministic only** | The rule cascade with no LLM and no tiering; anything uncertain escalates | Zero fabrication, but poor STP and heavy escalation. Safe and useless. |
| **C · Tieout** | Full system — policy, tiering, adjudication, gate | Zero fabrication *and* high STP. The corner nobody else occupies. |

**Baseline A is the most important experiment in the project.** It turns "models fabricate" from a citation into your own measurement.

### The chart that carries the demo

Two axes, always reported together — either alone is gameable:

```
  fabrication
     rate
       ↑
    7% │
       │        ● A · Naive LLM
    6% │          (fabricates to close)
       │
    4% │
       │
    2% │
       │                          ┌─────────────┐
    0% │  ● B · Deterministic     │  ◉ C ·Tieout│
       │    (safe, unusable)      │  target     │
       └──────────────────────────└─────────────┘──→
        0%      25%      50%      75%      100%
                    straight-through rate
```

---

## 12. Interfaces

### CLI — the primary demo surface

```bash
tieout ingest    --scenario month-end-close       # hashes + manifest
tieout policy    validate                         # schema + AS 2105 sanity
tieout policy    show --version 2026.01-r3
tieout reconcile --period 2026-01                 # the run
tieout queue     [--blocking] [--aging]           # exception queue
tieout review    <work_key> --approve|--reject|--reclassify <class> \
                 --as controller@acme --note "..."
tieout close     --period 2026-01                 # the money shot
tieout score     --against ground-truth           # out-of-process
tieout score     --baseline naive-llm|deterministic
tieout score     --passk 5                        # reliability
tieout audit     verify                           # hash chain integrity
tieout audit     evidence <work_key>              # the pack
tieout serve                                      # dashboard on :8000
```

Every command emits human-readable text to stdout and structured JSON with `--json`, so the dashboard and the scoreboard consume the same data the CLI prints.

### Dashboard — three screens

**1 · Close status**
- The disposition breakdown, T0→T3, with dollar values
- **Straight-through rate and fabrication rate side by side** — never one without the other
- The blocking list, sorted by materiality
- A single unmistakable state: `CLOSE REFUSED` or `CLOSED`

**2 · Review queue**
- Sorted by materiality × age, aging buckets shown
- Per item: candidate rows, feature deltas, reason code, recommendation, evidence link
- Any cited prior human decision, with who and when
- Actions: approve / reject / reclassify — **identity required**, four-eyes enforced

**3 · Scoreboard**
- The two-axis chart with all three baselines plotted
- Per-class precision/recall table
- Cost, latency, pass^k
- Materiality-weighted error alongside row-weighted, to show the difference

**State at rest:** ships with a completed run loaded, so the first frame shows real output rather than an empty shell. Example data plainly labelled as ReconRiver, never presented as a real company's books.

---

## 13. Code Layout

Many small focused modules — 200–400 lines typical, organised by domain rather than by type. Frozen models throughout; new objects, never mutation.

```
tieout/
  policy/
    schema.py        # Policy, Threshold, ConfidenceTier — frozen
    loader.py        # load + validate policy.yaml, version resolution
    materiality.py   # SAB 99 qualitative, SAB 108 rollover + iron curtain
    redflags.py      # AS 2401 ¶.61 checks against our own JEs
  ingest/
    schema.py        # LedgerEntry, ProcessorEvent, BankEntry — frozen
    reconriver.py    # CSV adapter + row quarantine
    manifest.py      # SHA256 per file, run manifest, re-verification
    money.py         # Decimal helpers, ROUND_HALF_UP, currency guards
  match/
    blocking.py      # candidate WorkItem generation
    features.py      # FeatureVector — deterministic, no LLM
    classify.py      # rule cascade → outcome class + reason code
    adjudicate.py    # LLM, residual only, structured output
  gate/
    decide.py        # THE REFUSAL GATE — four dispositions
    invariants.py    # I1–I4 asserted
    tiers.py         # confidence-tiered autonomy
  post/
    tools.py         # the constrained tool surface
    journal.py       # JE construction from match_id — no amount param
  audit/
    events.py        # append-only hash-chained JSONL
    evidence.py      # evidence pack assembly, content addressing
    identity.py      # distinct bot vs human actors, four-eyes check
  memory/
    decisions.py     # PriorDecision store, bounded confidence lift
  score/             # ← runs OUT OF PROCESS from the agent
    metrics.py       # the seven metrics
    baselines.py     # naive-LLM and deterministic-only runners
    report.py        # scoreboard JSON
  close/
    period.py        # the close gate, the state machine, the lock
    aging.py         # buckets, escalation clocks
  api/
    app.py           # FastAPI
    routes.py
  cli.py             # the tieout CLI

web/
  index.html  queue.html  score.html   # vanilla, read JSON

tests/
  test_invariants.py      # ← I1–I4. The most important file here.
  test_materiality.py     # SAB 108 both methods
  test_classify.py        # one case per outcome class
  test_audit_chain.py     # tamper detection
  test_money.py           # rounding, currency, no-float

policy.yaml
README.md                 # setup instructions — a Devpost requirement
docs/DESIGN.md            # this file
```

---

## 14. Tests That Earn Their Place

Not coverage theatre. Each test below fails loudly if the thesis breaks.

| Test | Asserts |
|---|---|
| `test_no_post_without_match` | **I1** — `post_matched_entry` rejects any `match_id` that doesn't resolve to a persisted evidenced match |
| `test_journal_always_balances` | **I2** — over every outcome class, generated entries balance to the cent; amounts are derived, never supplied |
| `test_ambiguity_never_picks` | **I3** — inject two candidates inside tolerance; assert REFUSE, and assert no posting event was written |
| `test_cannot_close_with_refusals` | **I4** — a period with one open REFUSE cannot close; assert no `force` parameter exists on the signature |
| `test_agent_cannot_read_ground_truth` | Ingest raises on any attempt to open `expected_reconciliation.csv` |
| `test_agent_cannot_mutate_policy` | Policy objects are frozen; the agent's tool surface exposes no setter |
| `test_audit_chain_detects_tamper` | Alter one event's payload; `audit verify` reports the exact break point |
| `test_four_eyes_enforced` | An approval where `approver_id == initiator_id` is rejected at write time |
| `test_sab108_both_methods` | A case material under iron curtain but not rollover still requires adjustment |
| `test_memory_cannot_rescue_refusal` | Any number of prior human approvals on similar items never promotes a T3 out of REFUSE |
| `test_money_never_float` | No `float` reaches any money field; rounding is HALF_UP at 2dp |

---

## 15. The Demo Video — Shot by Shot

Assumes a ≤3 min cap. **Confirm the actual limit in Discord** — this is the blocking question to ask first.

| Time | Shot | What is said |
|---|---|---|
| 0:00–0:20 | AccountingBench numbers on screen | "The only independent benchmark of AI closing real books found frontier models diverge by 15% of balance — half a million dollars. Not because they hallucinate. Because when they can't match something, **they fabricate a transaction to make the check pass.**" |
| 0:20–0:40 | `tieout reconcile` running; dashboard fills | "11,539 items across ledger, processor and bank. 98% posted straight through." |
| 0:40–1:05 | The two-axis chart, three baselines | "Handed the same files to a model with no constraints — **it fabricated, on our own bench.** Deterministic-only never fabricates but escalates everything. We're in the corner." |
| 1:05–1:35 | **`tieout close` → CLOSE REFUSED** | "$658,000 of inadmissible items. It will not close. **There's no override — not a flag, not an env var.**" |
| 1:35–1:55 | One `AMBIGUOUS_MATCH`, two candidates | "Two candidates, both inside tolerance. A plugging model picks one. This declines to choose — and shows you both." |
| 1:55–2:10 | The tool surface, absences highlighted | "**We didn't prompt it not to plug. We deleted the tool.** No function here posts an amount nobody matched." |
| 2:10–2:30 | Review one item; rerun; prior decision cited | "Approve once. Next run it cites your decision, with your name and timestamp. It never asks twice." |
| 2:30–2:40 | `tieout audit verify` + an evidence pack | "Hash-chained. Every entry carries lineage, identity, timestamps and support — what AS 1105 makes an auditor test." |
| 2:40–2:55 | **The AO board, session history, worktrees** | "Built across N AO sessions — policy, matching, gate and scoreboard in parallel worktrees." |
| 2:55–3:00 | One line | "Everyone measures. We're the ones that stop." |

**Never demo a live optimisation or a long run.** Pre-record the reconcile, ship results as JSON, let the dashboard replay them.

---

## 16. Business Model

| Element | Detail |
|---|---|
| **Who pays** | Mid-market controllers, multi-entity, on an existing ERP they will not replace. Maximor's own AE posting validates the band at **$50k+ ACVs**. |
| **Wedge** | **Open-core.** The refusal engine, the gate, the CLI and the eval harness ship Apache-2.0. Every 18-month exit in the adjacent tooling category went to an open-core player — Langfuse→ClickHouse, Promptfoo→OpenAI — while closed-SaaS peers were acqui-hired or stayed small. |
| **Paid surface** | Hosted policy governance with version history and approvals; the evidence vault with retention; multi-entity consolidation; SSO, SOC 2, audit-firm export. |
| **Metering** | Reconciled transaction volume, **seats unlimited**. Research is unambiguous that usage-metered-with-decoupled-seats wins and per-seat loses — LangSmith's $39/seat is the holdout and the thing critiques attack. Anchors: $19/mo (Opik) → $29 (Langfuse) → $249 (Braintrust). |
| **The differentiated tier** | **Outcome pricing on audit exceptions prevented and close days saved.** Nobody in either category charges on results — cost tooling is priced on log volume, meaning the vendor earns more when you spend more. Denominators exist: Ardent Partners puts AP exception rates at **22% industry vs 9% best-in-class** and cost per invoice at **$9.40 vs $2.78**; Maximor self-reports ~75% fewer audit exceptions. *And this tier is only credible because the system can attribute what it prevented* — the same primitive as the refusal. |
| **Why now** | 96% of CFOs want AI, only 14% trust it. New CPA exam candidates fell 42,626 → 28,082 → 16,448 (H1 2025). 238 public companies had FY2025 material weaknesses, with inadequate accounting resources up 14% YoY. And AccountingBench proves the current generation of models fails at exactly this task. |
| **Honest competitive read** | Close and reconciliation are crowded — Numeric $51M, Maxima $41M, Rillet $1B, BlackLine $700M revenue. **You do not win on matching quality.** You win on the refusal and the proof, which nobody sells and which the only independent benchmark says everyone fails. Note also that the vendor selling hardest *against* autonomy (BlackLine) is the one reporting AI scrutiny stretching sales cycles 40–45 days — **trust, not capability, is the bottleneck.** |

---

## 17. Build Plan & AO Delegation

> **Timing note.** The hackathon started 5 Sep 2026 at 21:30 IST. This repository was initialised at 22:07 IST — **after** the start, satisfying the rule that *"all project work must begin after the official hackathon start time."* This spec is the first commit. Organisers reserve the right to verify commit history.

### Twenty AO sessions

Decomposed small and deliberately — session count is a countable judging input, and these are genuinely independent units of work.

| # | Session | Depends on | Parallel? |
|---:|---|---|---|
| 1 | Repo scaffold, `pyproject`, CI, README skeleton | — | — |
| 2 | `ingest/money.py` — Decimal, HALF_UP, currency guards | 1 | ✅ |
| 3 | `ingest/schema.py` + `reconriver.py` adapter + quarantine | 2 | ✅ |
| 4 | `ingest/manifest.py` — hashing, run manifest | 1 | ✅ |
| 5 | `policy/schema.py` + `loader.py` + `policy.yaml` | 1 | ✅ |
| 6 | `policy/materiality.py` — SAB 99 + SAB 108 dual method | 5 | ✅ |
| 7 | `policy/redflags.py` — AS 2401 ¶.61 self-check | 5 | ✅ |
| 8 | `match/blocking.py` | 3 | — |
| 9 | `match/features.py` incl. fee-explained delta | 8 | — |
| 10 | `match/classify.py` — the rule cascade, 11 classes | 9 | — |
| 11 | **`gate/decide.py` + `tiers.py` + `invariants.py`** | 6, 10 | — |
| 12 | `post/tools.py` + `journal.py` — the constrained surface | 11 | — |
| 13 | `audit/events.py` — hash-chained log | 1 | ✅ |
| 14 | `audit/evidence.py` + `identity.py` + four-eyes | 13 | ✅ |
| 15 | `close/period.py` + `aging.py` | 11, 13 | — |
| 16 | `score/metrics.py` — the seven metrics | 11 | ✅ |
| 17 | `score/baselines.py` — naive-LLM + deterministic-only | 16 | ✅ |
| 18 | `match/adjudicate.py` — LLM on the residual | 10 | ✅ |
| 19 | `memory/decisions.py` — bounded confidence lift | 11 | ✅ |
| 20 | `api/` + `web/` — three screens | 15, 16 | ✅ |
| + | Neatlogs instrumentation · README setup instructions · Devpost writeup | — | ✅ |

Sessions 2–7, 13–14 and 16–20 are genuinely parallelisable — the honest use of AO worktrees, and the reason your board will look busy rather than performed.

### Hour by hour (IST)

| Time | Target |
|---|---|
| 21:30–23:30 | Devpost draft created. Discord questions asked. Pass posted. AO installed and verified. Repo init — **first commit after 21:30**. Sessions 1–5 dispatched. |
| 23:30–02:00 | **v0 milestone:** ingest → blocking → deterministic classify → gate → `close` refuses. Ugly, working, committed. Sessions 8–11. |
| 02:00–07:00 | **Sleep.** Leave a full reconcile running. |
| 07:00–11:00 | Audit trail + evidence packs + four-eyes (13, 14). Constrained tool surface (12). Invariant tests. |
| 11:00–15:00 | Scoreboard + both baselines (16, 17). **Get baseline A to fabricate — that experiment is the demo.** |
| 15:00–19:00 | Dashboard three screens (20). LLM adjudication (18). Decision memory (19). |
| 19:00–22:00 | Full runs, pass^k ×5, collect held-out results, screenshot everything, AS 2401 self-check (7). |
| 22:00–01:00 | **Demo video, README with setup instructions, Devpost writeup.** Screen-record the AO board. |
| 01:00–02:00 | Buffer. |
| **02:00** | **SUBMIT.** Deadline 03:30 — do not test it. |

### Standing rules

1. **Screenshot the AO board every few hours from hour zero.** Session evidence is 25% of the score and cannot be reconstructed at hour 28.
2. **Ship a working v0 by hour 5**, then improve. Never let the repo reach a state where a crash means no submission.
3. **Never demo live optimisation.** Pre-record; replay from JSON.
4. **Instrument with Neatlogs.** Two lines, sponsor tool, produces exactly the reliability evidence the rubric demands.

---

## 18. Cut Lines & Risks

### What survives a bad hour

| Tier | Components | If cut |
|---|---|---|
| **Must — v0 by hour 5** | Ingest · deterministic classify · **refusal gate** · close gate · CLI | No submission. Non-negotiable. |
| **Should** | Scoreboard vs ground truth · naive-LLM baseline · audit chain · evidence packs | Loses the "measurable results" requirement — a 25% criterion. Fight hard for these. |
| **Nice** | Dashboard · decision memory · AS 2401 self-check · pass^k | Demo gets weaker but the thesis still lands from the CLI. |
| **Cut first** | **LLM adjudication** · web review UI · aging buckets | **Nothing breaks.** Deterministic-only still refuses, still closes, still scores. Cutting the LLM entirely is survivable — which is the point of building it this way. |

### Risks and pre-planned answers

| Risk | Severity | Answer |
|---|---|---|
| "You're just doing fuzzy matching" | High | Concede immediately — matching is commodity, Numeric claims 90%+. The product is the refusal and its evidence. **Say it before the judge does.** |
| Baseline A doesn't actually fabricate | High | Then your central experiment failed. Mitigate: give it the genuinely hard subset (the 80 REFUSE items plus ambiguous cases) and a validation check it wants to satisfy — that is the AccountingBench setup. If it still doesn't, **report that honestly**; an honest negative is worth more than a rigged positive, and judges can smell the difference. |
| "Synthetic data isn't real" | Medium | Concede, then produce the second dataset: Berka (1,056,320 real bank transactions plus 6,471 standing orders) or Checkbook L.A. (3.89M real 3-way triples). Have one loaded. |
| "Refusing is easy — refuse everything" | Medium | Exactly why both axes are always reported together. Show baseline B occupying that corner and being useless. |
| No finance background shows | Medium | You cite AS 2401 ¶.61, AS 1105 ¶.10, AS 2105, SAB 99 and SAB 108, and you implement the fraud-test criteria against your own output. That reads as preparation. |
| Judge thinks it's too human-gated | Medium | Lead with the **98% straight-through rate**, not the refusal. Confidence-tiered autonomy, in his vocabulary. The refusal applies to 0.7% of items. |
| Scope too large for 30h solo | Medium | The cut table above, plus a working v0 at hour 5. The gate is ~200 lines; the value is concentrated there. |
| API cost / rate limits | Low | LLM is on the residual only and fully optional. Ask AI Grants India for credits early; TensorMux is available. |
| Windows/AO install failure | Low but fatal | **Test immediately.** No recovery path once the clock is running. |

> ### Framing discipline for the whole submission
>
> Do not claim the system is *accurate at accounting*. Claim exactly this:
>
> *It never posts a match it cannot evidence, it refuses to close when the data doesn't support closing, and here is the number proving it — measured against held-out labels, next to a baseline that fabricates.*
>
> That claim is narrow, true, verifiable, and it is the only one in this space with an independent benchmark behind it.

---

## 19. Open Questions & Assumptions

### Ask in Discord immediately

- **Max demo video length?** This spec assumes ≤3 min and the shot list is built to it.
- **What exactly counts as an "AO session" for judging?** 25% of the score. The 20-session decomposition assumes one delegated task = one session.
- **Do public scaffolds count as pre-existing work?** Affects whether a cookiecutter start is permitted.
- Must the repo be public at submission?
- Async video review or live pitch?
- Is Neatlogs / Dodo / TensorMux usage scored, or purely optional?

### Assumptions this spec makes explicit

| Assumption | If wrong |
|---|---|
| ReconRiver's `month-end-close` folder has the row counts and columns recorded in §3 | Verified by live HTTP during research, but **re-verify at ingest time**. The adapter should fail loudly on a schema change, not coerce. |
| Fee policy is 2.90% + 0.30 HALF_UP | **Read it from `scenario_manifest.json` at runtime** rather than hardcoding — the manifest is authoritative. |
| The deterministic cascade resolves the large majority of items | If it resolves far less, LLM adjudication moves from optional to required and cost rises. **Measure at hour 6 and re-plan.** |
| Materiality figures in `policy.yaml` are illustrative for a synthetic entity | They are **not** real thresholds for a real company. Label them as example values in the README — this matters for honesty and for the judge. |
| A naive LLM baseline will fabricate under pressure | See the risk table. Report honestly either way. |

### Deliberately out of scope

- Revenue recognition, leases, FX remeasurement, fixed assets — Tier 1 judgment workflows, correctly out of reach in 30 hours
- Any ERP write-back or live integration — no OAuth, no connectors
- Multi-entity consolidation and intercompany eliminations
- Flux commentary generation — strong demo, but no ground truth, so it fails the measurability requirement
- Three-way match — the alternative anchor; Checkbook L.A. is real but unlabelled

---

## Sources

Every regulatory citation, benchmark figure and market number in this document traces to research compiled 5 Sep 2026. Key primary sources:

- **AccountingBench** — https://accounting.penrose.com/ · discussion: https://news.ycombinator.com/item?id=44637352
- **ReconRiver** — https://huggingface.co/datasets/heybadrinath/reconriver-synthetic-reconciliation (CC BY 4.0)
- **PCAOB AS 2401** (fraud / management override) — https://pcaobus.org/oversight/standards/auditing-standards/details/AS2401
- **PCAOB AS 1105** (audit evidence, IPE) — https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105
- **PCAOB AS 2105** (materiality) — https://pcaobus.org/oversight/standards/auditing-standards/details/AS2105
- **SEC SAB 99** (materiality) — https://www.sec.gov/interps/account/sab99.htm
- **SEC SAB 108** (dual method) — https://www.sec.gov/rules-regulations/staff-guidance/staff-accounting-bulletins/staff-accounting-bulletin-no-108
- **SEC Release 33-8238** (evidential matter) — http://www.sec.gov/rule-release/33-8238
- **Maximor** — https://www.maximor.ai/blog/what-we-mean-by-autonomous-finance · https://www.maximor.ai/why · https://www.maximor.ai/controller
- **Darwin Gödel Machine** (reward hacking) — https://sakana.ai/dgm/
- **Ardent Partners AP metrics 2025** — https://ardentpartners.com/ap-metrics-that-matter-in-2025/
- **Backup datasets** — Berka: https://www.kaggle.com/datasets/marceloventura/the-berka-dataset (CC0) · Checkbook L.A.: `controllerdata.lacity.org` dataset `pggv-e4fn` (CC BY 4.0)

Illustrative figures are labelled as such. **Measured results do not exist yet.**
