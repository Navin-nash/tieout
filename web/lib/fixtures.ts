// ###  FIXTURE DATA - NOT A REAL RUN, NOT A REAL COMPANY'S BOOKS  ###
//
// Every value in this file is synthetic sample data for the **ReconRiver**
// `month-end-close` scenario, the public evaluation dataset described in
// docs/DATASET.md. SPEC section 12 is explicit: example data is plainly
// labelled as ReconRiver and is never presented as a real company's books.
//
// These fixtures exist so the landing-page, dashboard-ui and agent-ui workers
// can build screens before the FastAPI layer lands. They are served only when
// `NEXT_PUBLIC_TIEOUT_API_MODE` is `fixture` (the default until the API
// exists), and `FIXTURE_NOTICE` must be rendered on any surface showing them.
// Do not let a fixture reach a demo unlabelled.
//
// The disposition counts below reproduce SPEC section 10's worked example
// exactly, so a screen built against fixtures matches the CLI transcript.

import type {
  CloseStatus,
  QueueItem,
  ReviewQueue,
  Scoreboard,
} from "@/lib/api-types";

/** Render this wherever fixture data is shown. It is not decoration. */
export const FIXTURE_NOTICE =
  "Sample data - ReconRiver month-end-close evaluation scenario. Not a real company's books.";

export const FIXTURE_CLOSE_STATUS: CloseStatus = {
  period: "2026-01",
  state: "REFUSED",
  policyVersion: "2026.01-r3",
  workItems: 11539,
  breakdown: [
    { disposition: "AUTO_POST", count: 10412, share: 0.902 },
    { disposition: "AUTO_SAMPLED", count: 927, share: 0.08, sampled: 46 },
    { disposition: "ESCALATE", count: 120, share: 0.01 },
    { disposition: "REFUSE", count: 80, share: 0.007 },
  ],
  straightThroughRate: 0.982,
  fabricatedMatches: 0,
  blocking: [
    { outcomeClass: "MISSING_BANK_SETTLEMENT", count: 20, total: "412880.14" },
    { outcomeClass: "MISSING_PROCESSOR", count: 30, total: "109442.00" },
    { outcomeClass: "MISSING_INTERNAL", count: 20, total: "88120.55" },
    { outcomeClass: "AMBIGUOUS_MATCH", count: 10, total: "47900.00" },
  ],
  blockingTotal: "658342.69",
  performanceMateriality: "450000.00",
  refusalReason:
    "Blocking total exceeds performance materiality ($450,000.00). The period cannot be certified. No override exists - this is invariant I4.",
};

const FIXTURE_ITEMS: QueueItem[] = [
  {
    workKey: "WK-2026-01-004182",
    disposition: "REFUSE",
    outcomeClass: "MISSING_BANK_SETTLEMENT",
    amount: "412880.14",
    currency: "USD",
    confidence: 0.0,
    ageDays: 41,
    reasonCode: "NO_ADMISSIBLE_MATCH",
    recommendation:
      "No bank credit exists for this settled batch. Obtain the bank statement line or evidence of a failed transfer before this period can close.",
    candidates: [
      {
        side: "processor",
        key: "BATCH-20260118-0007",
        date: "2026-01-18",
        amount: "412880.14",
        description: "Settled batch, processor payout initiated",
      },
    ],
    featureDeltas: [
      { feature: "amount_delta", value: "no counterpart", withinTolerance: false },
      { feature: "date_delta", value: "no counterpart", tolerance: "2 days", withinTolerance: false },
      { feature: "key_match", value: "none", withinTolerance: false },
    ],
    evidenceUrl: "/api/evidence/WK-2026-01-004182",
    blocksClose: true,
  },
  {
    workKey: "WK-2026-01-009930",
    disposition: "REFUSE",
    outcomeClass: "AMBIGUOUS_MATCH",
    amount: "47900.00",
    currency: "USD",
    confidence: 0.58,
    ageDays: 22,
    reasonCode: "MULTIPLE_ADMISSIBLE_CANDIDATES",
    recommendation:
      "Two processor events fall within tolerance of this ledger entry. Ambiguity refuses by construction (invariant I3); a human must identify the correct counterpart.",
    candidates: [
      {
        side: "ledger",
        key: "JE-20260129-1183",
        date: "2026-01-29",
        amount: "47900.00",
        description: "Card settlement, ReconRiver merchant account",
      },
      {
        side: "processor",
        key: "TXN-9930-A",
        date: "2026-01-29",
        amount: "47900.00",
        description: "Payout, batch 0112",
      },
      {
        side: "processor",
        key: "TXN-9930-B",
        date: "2026-01-30",
        amount: "47900.00",
        description: "Payout, batch 0113",
      },
    ],
    featureDeltas: [
      { feature: "amount_delta", value: "0.00", tolerance: "0.50", withinTolerance: true },
      { feature: "date_delta", value: "0-1 days", tolerance: "2 days", withinTolerance: true },
      { feature: "candidates_within_tolerance", value: "2", tolerance: "1", withinTolerance: false },
    ],
    evidenceUrl: "/api/evidence/WK-2026-01-009930",
    blocksClose: true,
  },
  {
    workKey: "WK-2026-01-002047",
    disposition: "ESCALATE",
    outcomeClass: "FEE_MISMATCH",
    amount: "-1284.63",
    currency: "USD",
    confidence: 0.74,
    ageDays: 12,
    reasonCode: "FEE_OUTSIDE_POLICY_RATE",
    recommendation:
      "Delta reconciles to a fee of 3.15% + 0.30, above the 2.90% + 0.30 policy rate. Confirm the negotiated rate or raise a processor dispute.",
    candidates: [
      {
        side: "ledger",
        key: "JE-20260112-0442",
        date: "2026-01-12",
        amount: "40100.00",
        description: "Gross card revenue",
      },
      {
        side: "processor",
        key: "TXN-2047",
        date: "2026-01-12",
        amount: "38815.37",
        description: "Net payout after fees",
      },
    ],
    featureDeltas: [
      { feature: "fee_rate", value: "3.15%", tolerance: "2.90%", withinTolerance: false },
      { feature: "fee_fixed", value: "0.30", tolerance: "0.30", withinTolerance: true },
      { feature: "date_delta", value: "0 days", tolerance: "2 days", withinTolerance: true },
    ],
    evidenceUrl: "/api/evidence/WK-2026-01-002047",
    priorDecision: {
      workKey: "WK-2025-12-008810",
      decidedBy: "controller@reconriver.example",
      decidedAt: "2025-12-19T14:02:11Z",
      action: "approve",
      note: "Negotiated rate confirmed with processor for Dec; re-confirm each period.",
    },
    blocksClose: false,
  },
  {
    workKey: "WK-2026-01-007713",
    disposition: "AUTO_SAMPLED",
    outcomeClass: "LATE_SETTLEMENT",
    amount: "9.40",
    currency: "USD",
    confidence: 0.93,
    ageDays: 4,
    reasonCode: "SAMPLED_FOR_CONTROL_EVIDENCE",
    recommendation:
      "Posted. Drawn into the queue by the 5% control sample; no action required unless the evidence disagrees.",
    candidates: [
      {
        side: "ledger",
        key: "JE-20260126-7713",
        date: "2026-01-26",
        amount: "9.40",
        description: "Card settlement",
      },
      {
        side: "bank",
        key: "BNK-20260130-3391",
        date: "2026-01-30",
        amount: "9.40",
        description: "Deposit, 4 days after settlement window",
      },
    ],
    featureDeltas: [
      { feature: "amount_delta", value: "0.00", tolerance: "0.50", withinTolerance: true },
      { feature: "date_delta", value: "4 days", tolerance: "2 days", withinTolerance: false },
    ],
    evidenceUrl: "/api/evidence/WK-2026-01-007713",
    blocksClose: false,
  },
];

export const FIXTURE_REVIEW_QUEUE: ReviewQueue = {
  period: "2026-01",
  items: FIXTURE_ITEMS,
  aging: [
    { label: "0–30", count: 118, total: "241862.55" },
    { label: "31–60", count: 54, total: "412880.14" },
    { label: "61–90", count: 21, total: "88120.55" },
    { label: "120+", count: 7, total: "47900.00" },
  ],
  total: 200,
};

export const FIXTURE_SCOREBOARD: Scoreboard = {
  period: "2026-01",
  metrics: {
    fabricationRate: 0,
    straightThroughRate: 0.982,
    escalationPrecision: 0.91,
    materialityWeightedError: 0.004,
    rowWeightedError: 0.012,
    cost: { per1kWorkItems: { tokens: 0, usd: "0.00", wallClockSeconds: 11.4 } },
    passK: { k: 5, agreement: 1.0 },
  },
  perClass: [
    { outcomeClass: "MATCHED", precision: 1.0, recall: 0.999, support: 11139 },
    { outcomeClass: "REFUND_MATCHED", precision: 0.99, recall: 0.98, support: 100 },
    { outcomeClass: "PARTIAL_REFUND", precision: 0.96, recall: 0.94, support: 100 },
    { outcomeClass: "LATE_SETTLEMENT", precision: 0.93, recall: 0.9, support: 40 },
    { outcomeClass: "AMOUNT_MISMATCH", precision: 0.88, recall: 0.85, support: 40 },
    { outcomeClass: "FEE_MISMATCH", precision: 0.9, recall: 0.9, support: 20 },
    { outcomeClass: "CURRENCY_MISMATCH", precision: 1.0, recall: 0.95, support: 20 },
    { outcomeClass: "MISSING_PROCESSOR", precision: 1.0, recall: 1.0, support: 30 },
    { outcomeClass: "MISSING_INTERNAL", precision: 1.0, recall: 1.0, support: 20 },
    { outcomeClass: "MISSING_BANK_SETTLEMENT", precision: 1.0, recall: 1.0, support: 20 },
    { outcomeClass: "AMBIGUOUS_MATCH", precision: 1.0, recall: 1.0, support: 10 },
  ],
  baselines: [
    { id: "naive-llm", label: "A - Naive LLM", fabricationRate: 0.062, straightThroughRate: 0.97 },
    { id: "deterministic", label: "B - Deterministic only", fabricationRate: 0, straightThroughRate: 0.41 },
    { id: "tieout", label: "C - Tieout", fabricationRate: 0, straightThroughRate: 0.982 },
  ],
};
