// The JSON contract, typed. SPEC §12: every CLI command emits structured JSON
// with `--json`, and "the dashboard and the scoreboard consume the same data the
// CLI prints" — so these shapes are the contract, not a frontend convenience.
//
// Money is always a **decimal string**. PLAN standing rule 3: a float must never
// reach a money field, and `JSON.parse` on a JSON number produces exactly that.
// The `api-layer` worker serialises `Decimal` as a string; keep it a string all
// the way to `formatMoney`.

import type { Disposition } from "@/components/tieout/disposition-badge";
import type { Money } from "@/lib/money";

export type { Disposition, Money };

/** SPEC §3 — mirrored from ReconRiver's own taxonomy. Eleven, no more. */
export const OUTCOME_CLASSES = [
  "MATCHED",
  "REFUND_MATCHED",
  "PARTIAL_REFUND",
  "LATE_SETTLEMENT",
  "AMOUNT_MISMATCH",
  "FEE_MISMATCH",
  "CURRENCY_MISMATCH",
  "MISSING_PROCESSOR",
  "MISSING_INTERNAL",
  "MISSING_BANK_SETTLEMENT",
  "AMBIGUOUS_MATCH",
] as const;
export type OutcomeClass = (typeof OUTCOME_CLASSES)[number];

/* ── Screen 1 · Close status (SPEC §10, §12) ─────────────────────────────── */

export type DispositionBreakdown = {
  disposition: Disposition;
  count: number;
  /** Share of work items, 0–1. */
  share: number;
  /** T1 only: how many of the auto-posted rows were sampled for control evidence. */
  sampled?: number;
};

export type BlockingClass = {
  outcomeClass: OutcomeClass;
  count: number;
  total: Money;
};

export type CloseStatus = {
  period: string;
  /** SPEC §10 — a single unmistakable state. There is no third value. */
  state: "REFUSED" | "CLOSED";
  policyVersion: string;
  workItems: number;
  breakdown: DispositionBreakdown[];
  /** 0–1. SPEC §12: never reported without `fabricationRate` beside it. */
  straightThroughRate: number;
  /** Count of posted matches with no ground-truth counterpart. Target 0. */
  fabricatedMatches: number;
  blocking: BlockingClass[];
  blockingTotal: Money;
  performanceMateriality: Money;
  /** Why the close was refused, in one sentence. Absent when `state` is CLOSED. */
  refusalReason?: string;
};

/* ── Screen 2 · Review queue (SPEC §12) ──────────────────────────────────── */

export type CandidateRow = {
  side: "ledger" | "processor" | "bank";
  key: string;
  date: string;
  amount: Money;
  description: string;
};

export type FeatureDelta = {
  feature: string;
  value: string;
  tolerance?: string;
  withinTolerance: boolean;
};

/** SPEC §9 — "never asks twice": a cited prior human decision, with who and when. */
export type PriorDecision = {
  workKey: string;
  decidedBy: string;
  decidedAt: string;
  action: ReviewAction;
  note?: string;
};

export type QueueItem = {
  workKey: string;
  disposition: Disposition;
  outcomeClass: OutcomeClass;
  amount: Money;
  currency: string;
  /** 0–1. */
  confidence: number;
  ageDays: number;
  reasonCode: string;
  recommendation: string;
  candidates: CandidateRow[];
  featureDeltas: FeatureDelta[];
  /** Link to the audit evidence pack (SPEC §8). */
  evidenceUrl: string;
  priorDecision?: PriorDecision;
  /** True for the four REFUSE classes, which block the period close. */
  blocksClose: boolean;
};

export type AgingSummary = {
  label: "0–30" | "31–60" | "61–90" | "120+";
  count: number;
  total: Money;
};

export type ReviewQueue = {
  period: string;
  /** SPEC §10 — sorted by materiality × age, largest oldest break first. */
  items: QueueItem[];
  aging: AgingSummary[];
  total: number;
};

export type ReviewAction = "approve" | "reject" | "reclassify";

/**
 * SPEC §8 four-eyes: the acting identity is required and must differ from the
 * initiator. Enforcement is server-side in Python (`audit-chain`); the web app's
 * only job is to establish who the logged-in human is and pass it along.
 */
export type ReviewRequest = {
  workKey: string;
  action: ReviewAction;
  /** The authenticated human, e.g. "controller@acme.com". */
  actor: string;
  /** Required when `action` is "reclassify". */
  reclassifyTo?: OutcomeClass;
  note?: string;
};

export type ReviewResult = {
  workKey: string;
  action: ReviewAction;
  actor: string;
  recordedAt: string;
  /** Hash-chain digest of the appended audit event (SPEC §8). */
  eventDigest: string;
};

/* ── Screen 3 · Scoreboard (SPEC §11) ────────────────────────────────────── */

/** The seven metrics of SPEC §11. Rates are 0–1. */
export type ScoreMetrics = {
  fabricationRate: number;
  straightThroughRate: number;
  escalationPrecision: number;
  materialityWeightedError: number;
  rowWeightedError: number;
  cost: {
    per1kWorkItems: {
      tokens: number;
      usd: string;
      wallClockSeconds: number;
    };
  };
  /** Identical decisions across k repeated runs. Deterministic ⇒ approaches 1.0. */
  passK: { k: number; agreement: number };
};

export type PerClassScore = {
  outcomeClass: OutcomeClass;
  precision: number;
  recall: number;
  support: number;
};

export type BaselineId = "naive-llm" | "deterministic" | "tieout";

export type Baseline = {
  id: BaselineId;
  label: string;
  fabricationRate: number;
  straightThroughRate: number;
};

export type Scoreboard = {
  period: string;
  metrics: ScoreMetrics;
  perClass: PerClassScore[];
  /** SPEC §11 — all three plotted together; either axis alone is gameable. */
  baselines: Baseline[];
};
