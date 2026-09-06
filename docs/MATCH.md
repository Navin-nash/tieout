# Layer 2 — The Match Pipeline (`tieout/match`)

Documentation of Layer 2 steps 2–4: blocking, deterministic features, and the 11-class rule cascade.

---

## 1. Overview and Architecture

Layer 2 resolves reconciliation work items deterministically without involving an LLM.
The pipeline consists of three sequential, immutable stages:

1. **Blocking (`tieout/match/blocking.py`)**:
   Generates candidate `WorkItem`s cheaply via exact join on `merchant_order_id` for order-level reconciliation (Ledger ↔ Processor), and exact join on `settlement_batch_id` for settlement-level reconciliation (Processor ↔ Bank). Handles 1:1, 1:many (refunds and ambiguity), many-to-one (up to 22 processor transactions behind one bank credit), and orphan items.
2. **Feature Computation (`tieout/match/features.py`)**:
   Extracts `FeatureVector` deterministically:
   - `amount_delta` (Decimal, never float)
   - `date_delta_days` (integer)
   - `ref_match` (`EXACT`, `PARTIAL`, `NONE`)
   - `fee_explained_delta` (boolean indicator for fee policy deviations)
   - `currency_mismatch` (boolean)
   - `candidate_count` (integer)
   - `batch_completeness` (Decimal)
   - Refund indicators (`is_refund`, `is_partial_refund`, `is_full_refund`)
3. **The 11-Class Rule Cascade (`tieout/match/classify.py`)**:
   Evaluates a strictly ordered, most-specific-first cascade emitting canonical `Verdict`s with machine-readable reason codes and defendable confidence scores.

---

## 2. Invariant I3: Ambiguity Never Resolves to a Pick

PCAOB AS 2401 and SPEC section 6 invariant I3 prohibit picking among multiple candidate transactions within tolerance:
- When `candidate_count >= 2` for an order within tolerance, the cascade **always** emits `AMBIGUOUS_MATCH` (`L2_TWO_CANDIDATES_WITHIN_TOLERANCE`) with confidence `0.00`.
- The system never chooses a "best" candidate. Two admissible candidates is a factual property of the data that must be presented to a human reviewer or refused.

---

## 3. The 11-Class Cascade Order & Reason Codes

The cascade evaluates rules in order from most-specific exception to baseline match:

| Priority | Outcome Class | Reason Code | Condition | Confidence | Typical Disposition |
|:---:|---|---|---|:---:|:---:|
| 1 | `AMBIGUOUS_MATCH` | `L2_TWO_CANDIDATES_WITHIN_TOLERANCE` | `ORDER` scope & `candidate_count >= 2` & not refund | 0.00 | REFUSE (T3) |
| 2 | `MISSING_PROCESSOR` | `L2_MISSING_PROCESSOR_EVENT` | `ORDER` scope & no processor events | 0.00 | REFUSE (T3) |
| 3 | `MISSING_INTERNAL` | `L2_MISSING_INTERNAL_LEDGER` | `ORDER` scope & no ledger entries | 0.00 | REFUSE (T3) |
| 4 | `MISSING_BANK_SETTLEMENT` | `L2_MISSING_BANK_SETTLEMENT` | `SETTLEMENT` scope & no bank deposit | 0.00 | REFUSE (T3) |
| 5 | `CURRENCY_MISMATCH` | `L2_CURRENCY_MISMATCH` | `currency_mismatch == True` across legs | 0.80 | ESCALATE (T2) |
| 6 | `REFUND_MATCHED` | `L2_FULL_REFUND_MATCHED` | Full refund: `\|refund gross\| == capture gross` | 0.98 | AUTO_POST (T0) |
| 7 | `PARTIAL_REFUND` | `L2_PARTIAL_REFUND_MATCHED` | Partial refund: `\|refund gross\| < capture gross` | 0.92 | AUTO_SAMPLED (T1) |
| 8 | `FEE_MISMATCH` | `L2_FEE_CALCULATION_MISMATCH` | Gross matches, fee deviates from 2.90% + 0.30 | 0.85 | ESCALATE (T2) |
| 9 | `AMOUNT_MISMATCH` | `L2_AMOUNT_MISMATCH_EXCEEDS_TOLERANCE` | `amount_delta > tolerance.amount_abs` | 0.80 | ESCALATE (T2) |
| 10 | `LATE_SETTLEMENT` | `L2_SETTLEMENT_WINDOW_EXCEEDED` | `SETTLEMENT` scope & `date_delta_days > 3` | 0.90 | AUTO_SAMPLED (T1) |
| 11 | `MATCHED` | `L2_EXACT_MATCH` / `L2_BATCH_SETTLEMENT_MATCHED` | Exact match within tolerance & window | 1.00 | AUTO_POST (T0) |

---

## 4. Confidence Derivation & Refusal Gate Tiering

Confidence scores are directly aligned with the Refusal Gate tiers (SPEC section 6):

- **Tier 0 · AUTO_POST (conf ≥ 0.95)**:
  - `MATCHED` (conf = 1.00): Deterministic exact match across keys, amounts, and settlement window.
  - `REFUND_MATCHED` (conf = 0.98): Deterministic full refund match on prior capture.
- **Tier 1 · AUTO_SAMPLED (0.90 ≤ conf < 0.95)**:
  - `PARTIAL_REFUND` (conf = 0.92): Valid partial refund requiring sampling.
  - `LATE_SETTLEMENT` (conf = 0.90): Legitimate batch settlement arriving outside the 3-day window.
- **Tier 2 · ESCALATE (0.60 ≤ conf < 0.90)**:
  - `FEE_MISMATCH` (conf = 0.85): Deterministic fee calculation anomaly requiring review.
  - `AMOUNT_MISMATCH` (conf = 0.80): Variance exceeding policy tolerance.
  - `CURRENCY_MISMATCH` (conf = 0.80): Cross-currency discrepancy requiring manual resolution.
- **Tier 3 · REFUSE (conf < 0.60 / 0.00)**:
  - `MISSING_PROCESSOR`, `MISSING_INTERNAL`, `MISSING_BANK_SETTLEMENT`, `AMBIGUOUS_MATCH`: Inadmissible matches that block the close.

---

## 5. Measured Output Distribution on `data/raw`

The cascade's output distribution can be reproduced on `data/raw/` (without accessing holdout files) using:

```bash
python scripts/measure_cascade.py
```

### Reproducible Measurement Output:
- **Raw Input Rows**: 10,000 ledger (`internal_transactions.csv`), 10,200 processor (`processor_transactions.csv`), 1,499 bank settlement entries (`bank_settlements.csv`).
- **Total WorkItems Generated**: 11,539
  - Order scope: 10,020 work items
  - Settlement scope: 1,519 work items

### Produced Class Counts:

| Outcome Class | Emitted Count |
|---|---:|
| `MATCHED` | 11,139 |
| `PARTIAL_REFUND` | 100 |
| `REFUND_MATCHED` | 100 |
| `AMOUNT_MISMATCH` | 40 |
| `LATE_SETTLEMENT` | 40 |
| `MISSING_PROCESSOR` | 30 |
| `FEE_MISMATCH` | 20 |
| `CURRENCY_MISMATCH` | 20 |
| `MISSING_INTERNAL` | 20 |
| `MISSING_BANK_SETTLEMENT` | 20 |
| `AMBIGUOUS_MATCH` | 10 |
| **Total** | **11,539** |

### Produced Confidence Tier Split:
- **T0 · AUTO_POST (conf ≥ 0.95)**: 11,239 items (97.40%)
- **T1 · AUTO_SAMPLED (0.90 ≤ conf < 0.95)**: 140 items (1.21%)
- **T2 · ESCALATE (0.60 ≤ conf < 0.90)**: 80 items (0.69%)
- **T3 · REFUSE (conf < 0.60)**: 80 items (0.69%)

### Measurement Caveats & Ground-Truth Separation:
1. **Unmeasured Accuracy at this Layer**: The cascade's per-item accuracy and per-class precision/recall are **unmeasured** at Layer 2. True per-item accuracy and confusion matrices can only be produced by the out-of-process scorer (`tieout/score`, a separate worker) evaluating against held-out labels (`data/holdout/expected_reconciliation.csv`).
2. **Distribution Consistency vs. Correctness**: The aggregate class totals produced by the cascade are consistent with the published summary counts in `docs/DATASET.md`. However, aggregate count consistency does **not** establish per-item correctness, as offsetting misclassifications could theoretically yield identical totals.
3. **Role of Downstream Layers**: Layer 2 emits deterministic candidate verdicts and feature vectors. Residual adjudication and final refusal gate enforcement occur downstream.

---

## 6. Observability Instrumentation

All three stages are wrapped with Neatlogs spans (`tieout.obs`):
- `blocking`: span `blocking` records `candidate_group_count`.
- `features`: span `features` records `work_key`.
- `classify`: span `classify` records `work_key`, `outcome_class`, `reason_code`, `policy_version`, `disposition`, and `adjudicator=DETERMINISTIC`.
- Spans degrade cleanly to no-ops when `NEATLOGS_API_KEY` is not present, ensuring zero-configuration local runs.
