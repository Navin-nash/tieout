# The Close Gate

> *"A refusal is not a failure of the system — it is the system's output, and the only honest one
> available given the data."* — `docs/SPEC.md` section 10

This document specifies the close gate implementation in `tieout/close/**` and its verification in
`tests/test_close.py`.

Source of truth: `docs/SPEC.md` sections 6 (Invariant I4), 10 (Close Gate & Aging), 12 (Interfaces),
and 14 (Tests That Earn Their Place).

| File | Role |
|---|---|
| `tieout/close/period.py` | Period state machine, immutable lock, close gate entrypoint, structured report |
| `tieout/close/aging.py` | 30/60/90/120 day aging buckets, escalation clocks, materiality × age queue priority, write-off authority |
| `tests/test_close.py` | 15 comprehensive tests covering I4, maker-checker, locking, report shape, aging, and write-offs |
| `docs/CLOSE.md` | This specification and reference document |

---

## 1. The Thesis and the Demo's Money Shot

In contemporary month-end close systems evaluated on benchmarks like AccountingBench, automated
agents plug discrepancies or fabricate balancing lines to satisfy reconciliation checks. The books
close and balance on the surface, but latent divergence surfaces months later at ~15% of balance.

Tieout reverses this paradigm:
1. **Refusal is first-class:** Inadmissible transactions and unresolved differences explicitly
   **REFUSE (T3)** and block the financial close.
2. **Invariant I4 is inviolable:** A period containing any open REFUSE item cannot close.
3. **No override path exists:** There is no `force`, `override`, `skip_gate`, or `ignore_refusals`
   parameter on any close or certification function, and no environment variable or configuration
   key can alter this behavior.

---

## 2. The Period State Machine

Published corporate and public accounting close policies converge on a canonical state machine,
implemented directly in `tieout/close/period.py`:

```
Not started (NOT_STARTED)
   → In preparation (IN_PREPARATION)       [preparer owns]
   → Submitted for review (SUBMITTED_FOR_REVIEW) [reviewer owns]
   → [Rejected (REJECTED) → back to preparer]
   → Approved / certified (CERTIFIED)      [four-eyes maker-checker]
   → Period locked (LOCKED)                [immutable]
```

### State Transitions and Enforcements

| Transition Function | Permitted Prior States | Resulting State | Key Checks & Controls |
|---|---|---|---|
| `start_preparation()` | `NOT_STARTED`, `REJECTED` | `IN_PREPARATION` | Assigns preparer identity; emits audit event. |
| `submit_for_review()` | `IN_PREPARATION`, `REJECTED` | `SUBMITTED_FOR_REVIEW` | Freezes preparation; submits for review. |
| `reject_period()` | `SUBMITTED_FOR_REVIEW` | `REJECTED` | Reviewer provides rejection note; returns to preparer. |
| `certify_period()` | `SUBMITTED_FOR_REVIEW`, `IN_PREPARATION` | `CERTIFIED` | **Maker-checker enforced:** `reviewer.principal != preparer.principal`. Requires `HumanIdentity`. **Invariant I4 enforced:** calls `require_no_open_refusals()`. |
| `auto_certify_period()` | `IN_PREPARATION`, `NOT_STARTED` | `CERTIFIED` | **Bypass check:** total variance $\le$ `auto_certify_variance_threshold`. **Invariant I4 enforced:** any open REFUSE item prevents auto-certification. |
| `lock_period()` | `CERTIFIED` | `LOCKED` | Seals the period. Sets `locked_at` timestamp. |

### Immutability of Locked Periods

Once a period transitions to `PeriodState.LOCKED`:
- `assert_period_not_locked()` raises `PeriodLockedError`.
- All mutation, posting, reclassification, and subsequent state transition functions raise
  `PeriodLockedError`.
- The period's general ledger state is permanently sealed.

### Four-Eyes (Maker-Checker) Rule

Per AS 1105 requirement 3 and `tieout/audit/identity.py`:
- A reviewer cannot be the preparer who initiated the reconciliation (`reviewer.principal != preparer.principal`).
  Violation raises `FourEyesViolation`.
- A bot/service identity (`ServiceIdentity`) cannot certify a period in place of a human reviewer;
  `certify_period()` strictly requires `HumanIdentity`.

### Auto-Certification Bypass

SPEC section 10 frames auto-certification below a configured variance threshold as
*management's own materiality decision as configuration*, not a regulator-mandated number.
- Configured via `auto_certify_variance_threshold`.
- If variance exceeds the threshold, `auto_certify_period()` raises `AutoCertifyRefusedError`,
  requiring explicit human maker-checker review.
- If any open REFUSE item exists, `auto_certify_period()` raises `InvariantViolation("I4")` regardless
  of dollar amount.

---

## 3. Invariant I4 Enforcement

### Absolute Absence of Override Mechanisms

Invariant I4 states: **A period with open REFUSE items cannot close.**

1. **Signature Introspection:** `assert_no_force_parameter()` verifies that functions
   (`close_gate`, `certify_period`, `auto_certify_period`, `lock_period`, `build_close_report`,
   `start_preparation`, `submit_for_review`, `reject_period`) expose no parameters in
   `OVERRIDE_PARAMETER_NAMES = {"force", "override", "ignore_refusals", "skip_gate"}`.
2. **Runtime Enforcement:** `require_no_open_refusals()` inspects all dispositions and raises
   `InvariantViolation("I4", ...)` if any item has `blocking=True` or `tier=Tier.T3`.
3. **Environment and Config Immunity:** Tested in `test_no_environment_or_config_can_override_i4`.
   Setting environment variables such as `TIEOUT_FORCE_CLOSE`, `FORCE`, or `SKIP_GATE` has zero
   effect on the gate logic.
4. **Audit Trail Proof:** When close is refused, `close_gate()` writes a hash-chained
   `CLOSE_REFUSED` audit event containing the blocking count, blocking dollar totals, and
   breakdown features to the tamper-evident log (`EventLog`).

---

## 4. Structured Close Report

`CloseReport` is a frozen Pydantic model returned by `build_close_report()` and `close_gate()`.
Per SPEC section 12 and ADR-003, the CLI, web dashboard, and scoreboard consume identical JSON
payloads.

### Straight-Through Rate and Fabrication Rate

SPEC section 11 establishes that **straight-through rate and fabrication rate must always be reported
together**, because either alone is gameable:
- "Refuse everything" yields a perfect 0% fabrication rate but 0% straight-through rate.
- "Auto-post everything" yields 100% straight-through rate but high fabrication.

`CloseReport` model fields:
- `straight_through_rate: float` ($\frac{T0 + T1}{\text{total}} \times 100$)
- `fabricated_matches: int` (count of fabricated matches)
- `fabrication_rate: float` ($\frac{\text{fabricated}}{\text{posted}} \times 100$)

### SPEC Section 10 Terminal Output Rendering

`CloseReport.render_text()` faithfully formats the exact ASCII terminal output required by
SPEC section 10:

#### When Refused:
```text
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

#### When Closed:
```text
  Reconciliation summary          policy 2026.01-r3
  ─────────────────────────────────────────────────────────
  work items                              11,539
  auto-posted            T0               10,412    90.2%
  auto-posted, sampled   T1                  927     8.0%   (46 sampled)
  escalated              T2                  120     1.0%
  refused                T3                    0     0.0%
  ─────────────────────────────────────────────────────────
  straight-through rate                    98.2%
  fabricated matches                           0

  ✓ PERIOD CLOSED

  0 items blocking.
  Reconciliation certified and period locked.
```

---

## 5. Aging Buckets, Escalation Clocks & Queue Priority

`tieout/close/aging.py` implements exception queue management based on statutory and institutional
reconciliation policies.

### Aging Buckets

Items age into five standard buckets:
1. `0-30 days` (`AgingBucket.DAYS_0_30`): Standard reconciliation window.
2. `31-60 days` (`AgingBucket.DAYS_31_60`): Escalation tier 1.
3. `61-90 days` (`AgingBucket.DAYS_61_90`): Escalation tier 2.
4. `91-120 days` (`AgingBucket.DAYS_91_120`): Escalation tier 3.
5. `120+ days` (`AgingBucket.DAYS_OVER_120`): Long-standing statutory review.

### Policy Escalation Citations

- **U. of Houston MAPP 05.04.06**: Reconciliation due within 30 working days; unresolved items
  escalated to the Controller after 30 days.
- **VA Financial Policy Ch. 1**: Suspense differences *"researched, resolved, and explained within
  60 days."*
- **California SAM §8294**: Accounts receivable reconciliations monthly within 30 days; records
  retained 4 years.

### Queue Sorting: Materiality × Age

The exception break queue sorts by **materiality $\times$ age**:
$$\text{Priority Score} = |\text{amount}| \times \max(\text{age\_days}, 1)$$
This ensures that the **largest oldest break is always first in the queue**, preventing material
aged items from being buried beneath high-volume trivial breaks.

### Write-Off Authority Has No Default Value

> **Negative finding from accounting research (SPEC section 10):** No public accounting policy
> publishes a dollar write-off authority threshold — write-off limits exist exclusively in internal
> delegation-of-authority manuals.

Tieout treats write-off authority as a policy field **with no default value** (`write_off_threshold=None`).
- `evaluate_write_off()` raises `WriteOffAuthorityNotSet` if invoked when threshold is unset.
- The system strictly refuses automated write-offs until an authorized human explicitly configures
  the policy limit.

---

## 6. Narrow Policy Adapter

To avoid tight coupling with the parallel `tieout/policy` worker, `tieout/close/period.py` defines
`ClosePolicy` and `read_close_policy()`. The adapter extracts:
- `version: str`
- `performance_materiality: Decimal`
- `clearly_trivial: Decimal`
- `auto_certify_variance_threshold: Decimal`
- `write_off_threshold: Decimal | None` (defaults to `None`)

It seamlessly consumes `GatePolicy`, parsed YAML mappings, or custom policy instances with zero
leakage into the core gate logic.

---

## 7. Verification and Testing

All tests in `tests/test_close.py` pass cleanly in CI:

```bash
uv run pytest tests/test_close.py -v
uv run ruff check .
uv run ruff format --check .
```
