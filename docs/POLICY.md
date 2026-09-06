# Policy Layer & Threshold Governance

> **Audience:** Controller, Accounting Leadership, and External Audit Teams.  
> **Standards Cited:** PCAOB AS 2105, PCAOB AS 2401 ¶.61, SEC SAB 99, SEC SAB 108.

---

## 1. Executive Summary & Thesis

Traditional accounting and reconciliation software treats materiality thresholds and matching tolerances as static configuration constants. In practice, regulatory accounting frameworks reject numerical thresholds without contextual analysis:

- **SEC Staff Accounting Bulletin (SAB) No. 99** explicitly establishes that exclusive reliance on any percentage or numerical threshold *"has no basis in the accounting literature or the law"* and that a percentage is *"only the beginning of an analysis of materiality."*
- **PCAOB AS 2105** establishes structural relationships that must govern planning materiality, performance materiality, and the threshold below which misstatements are clearly trivial.
- **SEC Staff Accounting Bulletin (SAB) No. 108** legally requires quantifying misstatements under both the **rollover** (income statement) and **iron curtain** (balance sheet) methods, mandating adjustment if an error is material under **either** approach.
- **PCAOB AS 2401 ¶.61** identifies the specific characteristics of forced balancing entries that auditors must fraud-test for management override of controls.

Tieout implements Layer 1 not as a generic configuration loader, but as an **immutable, versioned threshold governance and policy engine** where every threshold carries full evidentiary provenance, policy mutation by autonomous agents is structurally prevented, and the system fraud-tests its own proposed balancing entries.

---

## 2. Threshold Governance & Provenance

### Why Provenance is Mandatory
Under SAB 99 and PCAOB AS 1105 (Audit Evidence), a bare number without institutional attribution, rationale, and effective dating is inadmissible as internal control evidence. In Tieout, every `Threshold` object requires:

```python
class Threshold(FrozenModel):
    value: Amount           # Decimal-backed, 2dp, ROUND_HALF_UP (floats strictly rejected)
    basis: NonEmpty         # e.g. "0.5% of planning revenue ($150M)"
    set_by: NonEmpty        # Attributed human principal, e.g. "controller@acme"
    set_at: Attested        # Timezone-aware UTC timestamp
    rationale: NonEmpty     # Business & risk rationale
```

A policy file containing a threshold without all five provenance components fails validation at load time.

### Read-Only Agent Tool Surface
To prevent autonomous agents from reward-hacking reconciliation checks by loosening tolerances, **all policy models are deeply frozen** (`pydantic.ConfigDict(frozen=True)`). No setter, `with_*` mutation helper, or API tool exists for an agent to adjust a threshold. Policy modifications are strictly human actions requiring version incrementation and provenance logging.

---

## 3. Practice Bands & AS 2105 Materiality Architecture

PCAOB AS 2105 dictates how auditors and controllers establish materiality levels. Tieout enforces these rules programmatically rather than relying on procedural guidance:

| Level | Definition | Industry Practice Band | Synthetic Benchmark Policy (`policy.yaml`) | Enforced Constraint |
|---|---|---|---|---|
| **Overall Materiality** | Maximum misstatement that could influence the economic decisions of users. | 0.5% – 7.0% of Revenue (or 5% of Pre-tax Income) | **$750,000.00** *(0.5% of $150M FY26 Planning Revenue)* | Must be a specified amount $> 0$ (AS 2105.06). |
| **Performance Materiality** | Amount set below overall materiality to reduce aggregation risk of undetected misstatements. | 50% – 75% of Overall Materiality | **$450,000.00** *(60% of Overall Materiality)* | Strictly $< \text{Overall}$ (AS 2105.09). Equality is rejected. |
| **Clearly Trivial** | Level below which misstatements will not be accumulated (trivial matters). | 3% – 5% of Overall Materiality | **$30,000.00** *(4% of Overall Materiality)* | Strictly $> 0$ and $< \text{Performance}$. |

> **Illustrative Calibration Label (SPEC Section 19 Compliance):**  
> The figures in `policy.yaml` ($750k / $450k / $30k) are **ILLUSTRATIVE values calibrated for a synthetic benchmark entity (`ACME-US`)**. In production deployments, controllers calibrate these thresholds to match the legal entity's financial statements.

---

## 4. SEC SAB 108: Dual-Method Quantification

### The Dual-Method Rule
SAB 108 addresses situations where errors accumulate on the balance sheet over multiple periods without hitting annual income statement materiality thresholds.

1. **Rollover Method (Income Statement Approach):** Quantifies the error originating in the *current-period income statement* only.
2. **Iron Curtain Method (Balance Sheet Approach):** Quantifies the *cumulative effect* of correcting the balance sheet at year-end, irrespective of the year in which the error originated.

**SAB 108 Mandate:** Financial statements require adjustment whenever an error is material under **EITHER** method.

### Worked Numeric Accounting Example

Consider an entity with **Overall Materiality = $750,000.00**:

- **Historical Context:** In Years 1, 2, and 3, the entity failed to accrue $270,000 per year of unbilled software maintenance expense ($810,000 cumulative balance sheet understatement).
- **Current Year (Year 4):** Current-year unbilled maintenance expense is $190,000.

```
Assessment:
--------------------------------------------------------------------------------
1. Rollover Method (Y4 Income Effect):       $190,000.00  (< $750,000 -> NOT Material)
2. Iron Curtain Method (Y4 Balance Sheet): $1,000,000.00  (>= $750,000 -> MATERIAL)
--------------------------------------------------------------------------------
Outcome: REQUIRES ADJUSTMENT under SAB 108 (Iron Curtain triggered).
```

Tools utilizing rollover alone let $1.0M of unrecorded liabilities escape to the balance sheet. Tieout calculates both metrics for every proposed adjustment.

---

## 5. SEC SAB 99: Qualitative Overrides

SAB 99 identifies qualitative factors that render misstatements material **regardless of dollar amount**:

1. `crosses_covenant_threshold`: The adjustment eliminates debt covenant headroom.
2. `changes_sign_income_to_loss`: The adjustment turns reported positive net income into a net loss.
3. `related_party_counterparty`: The transaction involves a related party or affiliate.
4. `masks_trend_reversal`: The adjustment converts an earnings growth trend into a decline.
5. `affects_management_compensation`: The adjustment impacts metric targets that trigger executive bonuses.
6. `conceals_unlawful_transaction`: The misstatement relates to an illegal payment or regulatory breach.

When any of these predicates evaluate to `True`, the item is escalated to human controllers and marked as requiring adjustment even if the magnitude is below the clearly-trivial threshold.

---

## 6. PCAOB AS 2401 ¶.61 Self-Check Against Our Own Journal Entries

PCAOB AS 2401 ¶.61 names the specific characteristics of journal entries that auditors must fraud-test for potential management override. Tieout implements these five criteria directly against **its own proposed entries** before posting:

| Red Flag Predicate | Audit Rationale | Implemented Rule & Scope | Current Limitation & Honest Scope |
|---|---|---|---|
| `round_number_amount` | Fraudulent plugs often use round numbers ($1,000, $5,000, $10,000). | Flags any non-zero adjustment $\ge \$100.00$ that has no cents and is divisible by 100. | In bank rec, genuine wire fees or flat charges can be round; this flags them for human review. |
| `seldom_used_account` | Forced plugs are often routed to clearing, suspense, or inactive accounts. | Flags entries where `is_seldom_used=True`, historical usage $< 5$, or account contains `suspense`, `clearing`, `plug`, `9999`. | Operates on account strings and frequency counts since full ERP chart-of-accounts master is out of scope. |
| `post_close_timing` | Entries recorded post-cutoff or after period close carry heightened override risk. | Flags entries where `is_post_close=True` or `effective_date > period_end_date`. | Relies on period boundary dates supplied in the run context. |
| `unusual_initiator` | Entries made by unauthorized users or unauthenticated automated scripts. | Flags initiators not present in `authorized_initiators` or matching generic strings (`unknown`, `system`). | Assumes authorized principal registry is passed from security/auth context. |
| `no_supporting_explanation` | Balancing plugs frequently lack business descriptions or use boilerplate. | Flags empty/whitespace strings or trivial boilerplate descriptions (`plug`, `adjust`, `misc`, etc., $<10$ chars). | Natural language quality evaluation is heuristic; deep semantic validation is delegated to human review. |

---

## 7. Write-Off Authority: The No-Default Policy Decision

SPEC Section 10 documents a negative research finding from surveying published corporate accounting manuals: **no public policy publishes a dollar write-off threshold**. Authority to write off reconciliation breaks is governed strictly by internal delegations of authority (DoA) matrices.

**System Design Decision:**
The `write_off_authority` field on `Policy` defaults to `None`. Any code path attempting to execute a write-off without an explicit, human-configured threshold raises a `PolicyRefusal` exception:

```
PolicyRefusal: policy '2026.01-r3' sets no write-off authority, and this system ships no default.
```

Tieout will never invent an autonomous write-off allowance.

---

## 8. Version Resolution & Period Supersession

Policies are historical legal records. When accounting scoreboards or prior-period close packages are recomputed, they must resolve against the policy version in force on the **first day of that period**:

- `resolve_for_period(policies, "2026-01")`: Resolves the active policy as of `2026-01-01`.
- Supersession chains are validated (`supersedes` must reference an existing policy with an earlier `effective_from` date).
- Mid-period policy changes apply prospectively to subsequent periods, preserving immutable prior decisions.
