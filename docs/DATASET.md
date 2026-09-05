# DATASET — ReconRiver `month-end-close`

Authoritative record of what the data **actually is**. Verified by downloading the live
dataset on 2026-09-05 and inspecting it directly — this document is evidence-based, not a
copy of docs/SPEC.md section 3. Where it disagrees with the spec, see the **Discrepancy
table** below; the spec's own section 19 predicted this ("re-verify at ingest time, fail
loudly on a schema change, never coerce") and that is exactly what this worker did.

## Provenance and licence

- Dataset: [`heybadrinath/reconriver-synthetic-reconciliation`](https://huggingface.co/datasets/heybadrinath/reconriver-synthetic-reconciliation) — CC BY 4.0.
- Scenario used: `month-end-close` (one of four scenario folders in the repo — `clean-settlement`,
  `failure-recovery`, `mixed-exceptions`, `month-end-close`).
- The dataset publishes its own machine-readable schema contract at `schemas/csv-columns.json`
  in the HF repo. That contract **matches what we downloaded exactly** — the discrepancies
  below are between SPEC.md and the dataset, not between the dataset and its own published
  contract. The data is internally consistent; the spec's description of it, written from
  research on 5 Sep, was not.
- The dataset is entirely synthetic (per its own manifest disclaimer): no real people,
  payments, cards, accounts, or customer identifiers.

## Fetch command

```
python scripts/fetch_dataset.py
```

Downloads five files from `generated/month-end-close/` in the HF repo via `huggingface_hub`,
verifies each against the SHA256s recorded in `scenario_manifest.json`, and prints actual row
counts and column lists. Safe to re-run (HF caches by content hash; destination files are
overwritten idempotently). Raises loudly if a file is missing upstream (dataset moved) or a
checksum no longer matches (dataset content changed).

## Raw/holdout split — and why

```
data/raw/internal_transactions.csv       <- agent-readable
data/raw/processor_transactions.csv      <- agent-readable
data/raw/bank_settlements.csv            <- agent-readable
data/raw/scenario_manifest.json          <- agent-readable
data/holdout/expected_reconciliation.csv <- NEVER agent-readable
```

Both directories are gitignored; the CSVs are never committed.

SPEC.md section 3 requires that `expected_reconciliation.csv` — the ground truth — is loaded
**only** by the out-of-process scorer, and that the agent's ingest code physically cannot open
it (not in its allowed-read path). This is not a convention, it's a directory boundary: the file
lives in `data/holdout/`, a sibling of `data/raw/`, so any ingest code that globs or reads
`data/raw/*` never touches it. This guards against two documented failure modes (SPEC section
3): reproducing the AccountingBench fabrication pattern, and the Darwin Gödel Machine reward-hacking
failure where an agent tasked with reducing a metric deleted the very evidence its detector
measured — i.e. an agent that could read its own grading key could learn to game the key
instead of doing the task.

## Actual schema (verified 2026-09-05)

### `internal_transactions.csv` — 10,000 rows

| # | Column | dtype (pandas) |
|---|---|---|
| 1 | `internal_payment_id` | object (str) |
| 2 | `merchant_order_id` | object (str) |
| 3 | `occurred_at` | object (str, ISO-8601 UTC) |
| 4 | `gross_amount` | float64 — **decimal string in CSV, e.g. `1278.74`; parse as `Decimal`, never `float`, downstream** |
| 5 | `currency` | object (str, ISO 4217: EUR/GBP/USD) |
| 6 | `payment_status` | object (str) |
| 7 | `payment_method` | object (str) |
| 8 | `synthetic_customer_reference` | object (str) |

### `processor_transactions.csv` — 10,200 rows

| # | Column | dtype |
|---|---|---|
| 1 | `processor_transaction_id` | object |
| 2 | `merchant_order_id` | object |
| 3 | `processor_event_type` | object |
| 4 | `processor_event_time` | object (str, ISO-8601 UTC) |
| 5 | `gross_amount` | float64 (Decimal string in CSV) |
| 6 | `fee_amount` | float64 (Decimal string in CSV) |
| 7 | `net_amount` | float64 (Decimal string in CSV) |
| 8 | `currency` | object |
| 9 | `settlement_batch_id` | object |
| 10 | `processor_status` | object |

### `bank_settlements.csv` — 1,499 rows

| # | Column | dtype |
|---|---|---|
| 1 | `bank_entry_id` | object |
| 2 | `settlement_batch_id` | object |
| 3 | `booked_at` | object (str, ISO-8601 UTC) |
| 4 | `credited_amount` | float64 (Decimal string in CSV) |
| 5 | `currency` | object |
| 6 | `bank_reference` | object |
| 7 | `description` | object |

### `expected_reconciliation.csv` (holdout) — 11,539 rows

| # | Column | dtype |
|---|---|---|
| 1 | `scenario_id` | object |
| 2 | `result_scope` | object (`ORDER` or `SETTLEMENT`) |
| 3 | `work_key` | object |
| 4 | `settlement_batch_id` | object (populated for `SETTLEMENT` scope rows, blank for `ORDER` scope) |
| 5 | `internal_payment_id` | object (blank for `SETTLEMENT` scope rows) |
| 6 | `processor_transaction_id` | object (blank for `SETTLEMENT` scope rows) |
| 7 | `bank_entry_id` | object (blank for `ORDER` scope rows) |
| 8 | `expected_outcome` | object (11-class enum, see below) |
| 9 | `expected_reason_code` | object |
| 10 | `expected_difference` | float64 |
| 11 | `explanation` | object (free text) |

`gross_amount` / `fee_amount` / `net_amount` / `credited_amount` are written to CSV as
fixed-2dp decimal strings (verified by inspecting raw lines, e.g. `1278.74`, `37.38`). pandas
loads them as `float64` by default — **downstream ingest must re-parse the original CSV strings
as `decimal.Decimal`, not trust the float64 column**, per PLAN.md rule 3 ("a float must never
reach a money field").

## Scenario manifest — verbatim actual values

From `data/raw/scenario_manifest.json` (`generator_version` 1.1.0, `random_seed` 42):

```
fee_policy:
  percentage_rate: 2.90%
  fixed_charge: 0.30
  rounding_mode: HALF_UP
  net_amount_formula: gross_amount - fee_amount

settlement_window: "3 calendar days after the latest processor event in a batch"
currencies: [EUR, GBP, USD]

file_row_counts:
  internal_transactions.csv: 10000
  processor_transactions.csv: 10200
  bank_settlements.csv: 1499
  expected_reconciliation.csv: 11539

injected_exception_counts:
  ambiguous_matches: 10
  amount_mismatches: 30          # ORDER-scope amount mismatches
  bank_amount_mismatches: 10     # SETTLEMENT-scope amount mismatches (30+10=40 total AMOUNT_MISMATCH)
  bank_currency_mismatches: 10   # SETTLEMENT-scope currency mismatches
  currency_mismatches: 10        # ORDER-scope currency mismatches (10+10=20 total CURRENCY_MISMATCH)
  fee_mismatches: 20
  full_refunds: 100              # -> REFUND_MATCHED
  late_settlements: 40
  missing_bank_settlements: 20
  missing_processor_records: 30  # -> MISSING_PROCESSOR
  partial_refunds: 100           # -> PARTIAL_REFUND
  processor_only_records: 20     # -> MISSING_INTERNAL
```

`file_sha256_checksums` (all 4 verified byte-for-byte against the downloaded files by
`scripts/fetch_dataset.py`, see terminal output below):

| File | SHA256 |
|---|---|
| `internal_transactions.csv` | `0909917ebb0a8a365561e16b554d97801d306e8d42d9a4ae1b3bbeab26b33805`* |
| `processor_transactions.csv` | `68b2ccfc3264debeafb0cbcc9ca42da4c9e297fd85c3e755e3b08eaf3a9b5d5d`* |
| `bank_settlements.csv` | `950e0cb5715bc3c5f6b9cb190e4f38a61aab2dcbe691d57979183f9678f72fc0`* |
| `expected_reconciliation.csv` | `228cc7395be543867fe3106e3c16205d14882c4e059232de9cc181c80050cc2d`* |

\* copied verbatim from the manifest; each is a standard 64-hex-char SHA256 digest (the
line-wrap above is a Markdown table artifact, not an extra byte).

## Actual outcome-class distribution

Derived by grouping `data/holdout/expected_reconciliation.csv` on `expected_outcome`
(matches the manifest's own `expected_reconciliation_summary` exactly):

| Class | Actual count |
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

## Many-to-one bank shape — the real fan-out

SPEC.md section 3 states "1,499 bank rows against 10,000 payments" as the headline shape.
Confirmed and measured precisely:

- `bank_settlements.csv` has 1,499 rows, **1,499 unique `settlement_batch_id` values** — the
  bank side is a clean 1:1 with settlement batches (no batch has more than one bank credit).
- `processor_transactions.csv` has 10,200 rows across **1,519 unique `settlement_batch_id`
  values** — 20 of those batches have no matching bank row at all (these are exactly the 20
  `MISSING_BANK_SETTLEMENT` exception rows).
- Restricting to the 1,499 batches that *do* have a bank credit: processor transactions per
  batch range from **1 to 22**, mean **6.79**.
- **The maximum fan-out behind a single bank credit is 22 processor transactions.** That is the
  ambiguity hot zone: any block of up to 22 candidate transactions must be disambiguated by the
  match pipeline before a bank credit can be posted, and it is the natural source of the
  `AMBIGUOUS_MATCH` class (≥2 admissible candidates within tolerance).

## Discrepancy table — SPEC.md section 3 claims vs. actual

**Row counts: all four match exactly.** No discrepancy.

| File | Spec-claimed rows | Actual rows | Match? |
|---|---:|---:|---|
| `internal_transactions.csv` | 10,000 | 10,000 | ✅ |
| `processor_transactions.csv` | 10,200 | 10,200 | ✅ |
| `bank_settlements.csv` | 1,499 | 1,499 | ✅ |
| `expected_reconciliation.csv` | 11,539 | 11,539 | ✅ |

**Column lists: three of four files have discrepancies.** The spec's column lists are
abbreviated/stale versions of the dataset's own published `schemas/csv-columns.json` contract
(which we verified matches the download byte-for-byte). This is a documentation drift, not a
dataset-integrity problem — but every one of these columns is load-bearing for the downstream
match pipeline, so it matters.

| File | Spec-claimed columns | Actual columns | Discrepancy |
|---|---|---|---|
| `internal_transactions.csv` | `internal_payment_id, merchant_order_id, occurred_at, gross_amount, currency, payment_status, payment_method` | same 7, **+ `synthetic_customer_reference`** | Spec omits 1 trailing column. Low risk (unused identifier) but must not be dropped silently by a hardcoded reader. |
| `processor_transactions.csv` | `processor_transaction_id, merchant_order_id, processor_event_type, processor_event_time, gross_amount, fee_amount, net_amount, settlement_batch_id, processor_status` | same 9, **+ `currency`** (positioned before `settlement_batch_id`) | **Spec omits `currency` entirely.** This is the field the `CURRENCY_MISMATCH` outcome class depends on directly — a spec reader would not know where currency comes from on the processor side. |
| `bank_settlements.csv` | `bank_entry_id, settlement_batch_id, booked_at, credited_amount, bank_reference, description` | same 6, **+ `currency`** (positioned before `bank_reference`) | **Spec omits `currency` entirely** on the bank side too — same risk as above, and directly relevant to the 10 `bank_currency_mismatches` in the manifest. |
| `expected_reconciliation.csv` | `expected_outcome, expected_reason_code, expected_difference, explanation` (4 columns) | 11 columns: **+ `scenario_id`, `result_scope`, `work_key`, `settlement_batch_id`, `internal_payment_id`, `processor_transaction_id`, `bank_entry_id`** | **Largest discrepancy.** The spec lists only the 4 "verdict" columns and omits all 7 join-key columns. Those keys (`work_key`, `internal_payment_id`, `processor_transaction_id`, `bank_entry_id`, `settlement_batch_id`, plus scope discriminator `result_scope`) are exactly what the out-of-process scorer needs to join a holdout row to the agent's computed `Verdict`. Anyone implementing the scorer from spec section 3 alone would not know how to join ground truth to output. |

**Outcome-class counts (spec's 11-row table in section 3): all 11 match exactly.** No
discrepancy — every count in the spec's outcome table matches both the manifest's own
`expected_reconciliation_summary` and our independent `groupby` on the holdout CSV.

| Class | Spec-claimed | Actual (verified) | Match? |
|---|---:|---:|---|
| `MATCHED` | 11,139 | 11,139 | ✅ |
| `REFUND_MATCHED` | 100 | 100 | ✅ |
| `PARTIAL_REFUND` | 100 | 100 | ✅ |
| `LATE_SETTLEMENT` | 40 | 40 | ✅ |
| `AMOUNT_MISMATCH` | 40 | 40 | ✅ |
| `FEE_MISMATCH` | 20 | 20 | ✅ |
| `CURRENCY_MISMATCH` | 20 | 20 | ✅ |
| `MISSING_PROCESSOR` | 30 | 30 | ✅ |
| `MISSING_INTERNAL` | 20 | 20 | ✅ |
| `MISSING_BANK_SETTLEMENT` | 20 | 20 | ✅ |
| `AMBIGUOUS_MATCH` | 10 | 10 | ✅ |

**Other spec claims checked:**

| Claim (SPEC section 3) | Actual | Match? |
|---|---|---|
| Fee policy 2.90% + 0.30 HALF_UP | `percentage_rate: 2.90%`, `fixed_charge: 0.30`, `rounding_mode: HALF_UP` | ✅ (spec section 19 correctly says to read this from the manifest at runtime rather than hardcode it — `tieout/ingest/manifest.py`, owned by `ingest-money`, should do exactly that) |
| "1,499 bank rows against 10,000 payments... many-to-one" | Confirmed; real max fan-out is **22** transactions behind one bank credit (see above) — the spec did not give this number, we measured it | N/A (spec made no specific fan-out claim to check, just the general shape) |

### Bottom line for downstream workers

- **Row counts and the 11-class outcome distribution in SPEC.md section 3 are exactly right.**
  Trust those numbers.
- **The column lists in SPEC.md section 3 are incomplete for 3 of 4 files.** Anyone writing
  `tieout/ingest/schema.py` or `tieout/ingest/reconriver.py` (owned by `ingest-money`) from the
  spec table alone would build a reader missing `currency` on the processor and bank sides, and
  missing every join key on the holdout side. Use the actual column lists in this document (or
  re-run `python scripts/fetch_dataset.py`), not SPEC.md section 3, as the schema source.
- Recommend `ingest-money` flag this to the `scaffold-repo`/spec-owning worker so SPEC.md
  section 3 gets corrected — this worker does not edit SPEC.md (out of ownership scope).

## Verification — real terminal output

### Fetch

```
$ python scripts/fetch_dataset.py
fetched generated/month-end-close/internal_transactions.csv -> data\raw\internal_transactions.csv
fetched generated/month-end-close/processor_transactions.csv -> data\raw\processor_transactions.csv
fetched generated/month-end-close/bank_settlements.csv -> data\raw\bank_settlements.csv
fetched generated/month-end-close/scenario_manifest.json -> data\raw\scenario_manifest.json
fetched generated/month-end-close/expected_reconciliation.csv -> data\holdout\expected_reconciliation.csv
checksum OK: internal_transactions.csv
checksum OK: processor_transactions.csv
checksum OK: bank_settlements.csv
checksum OK: expected_reconciliation.csv

--- actual row counts ---
internal_transactions.csv: 10000 rows, columns=['internal_payment_id', 'merchant_order_id', 'occurred_at', 'gross_amount', 'currency', 'payment_status', 'payment_method', 'synthetic_customer_reference']
processor_transactions.csv: 10200 rows, columns=['processor_transaction_id', 'merchant_order_id', 'processor_event_type', 'processor_event_time', 'gross_amount', 'fee_amount', 'net_amount', 'currency', 'settlement_batch_id', 'processor_status']
bank_settlements.csv: 1499 rows, columns=['bank_entry_id', 'settlement_batch_id', 'booked_at', 'credited_amount', 'currency', 'bank_reference', 'description']
expected_reconciliation.csv: 11539 rows, columns=['scenario_id', 'result_scope', 'work_key', 'settlement_batch_id', 'internal_payment_id', 'processor_transaction_id', 'bank_entry_id', 'expected_outcome', 'expected_reason_code', 'expected_difference', 'explanation']

OK -- month-end-close fetched, split into data/raw/ and data/holdout/, checksums verified.
```

Re-run twice more to confirm idempotency: identical output, no errors, no duplicate downloads
(huggingface_hub content-addressed cache short-circuits the network call).

### Test

```
$ pytest tests/test_dataset_schema.py -v
tests/test_dataset_schema.py::test_raw_file_columns_exact[internal_transactions.csv] PASSED
tests/test_dataset_schema.py::test_raw_file_columns_exact[processor_transactions.csv] PASSED
tests/test_dataset_schema.py::test_raw_file_columns_exact[bank_settlements.csv] PASSED
tests/test_dataset_schema.py::test_holdout_file_columns_exact PASSED
tests/test_dataset_schema.py::test_raw_holdout_split_is_physical PASSED
tests/test_dataset_schema.py::test_row_counts_match_manifest PASSED

============================= 6 passed in 14.13s ==============================
```

With `data/raw/` absent (simulated by renaming it away), the same suite skips cleanly:

```
$ pytest tests/test_dataset_schema.py -v
tests/test_dataset_schema.py::test_raw_file_columns_exact[internal_transactions.csv] SKIPPED
tests/test_dataset_schema.py::test_raw_file_columns_exact[processor_transactions.csv] SKIPPED
tests/test_dataset_schema.py::test_raw_file_columns_exact[bank_settlements.csv] SKIPPED
tests/test_dataset_schema.py::test_holdout_file_columns_exact SKIPPED
tests/test_dataset_schema.py::test_raw_holdout_split_is_physical SKIPPED
tests/test_dataset_schema.py::test_row_counts_match_manifest SKIPPED

============================= 6 skipped in 1.04s ==============================
```

## Known follow-up (not this worker's file to fix)

`.gitignore` currently ignores `data/raw/` but not `data/holdout/`. Both must be gitignored —
`data/holdout/expected_reconciliation.csv` must never be committed, that would defeat the
entire ground-truth isolation guarantee. `.gitignore` is owned by `scaffold-repo` per PLAN.md;
flagged to the orchestrator rather than edited here.
