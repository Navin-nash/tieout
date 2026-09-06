import { cn } from "@/lib/utils";
import { formatMoney, moneyAriaLabel, type Money } from "@/lib/money";

/**
 * DESIGN.md §8 "Aging bucket" + §9.3 "Aging distribution".
 *
 * Four fixed buckets, per SPEC §10 (U. of Houston MAPP 05.04.06 escalates at 30
 * days; VA Financial Policy Ch. 1 requires suspense differences resolved within
 * 60). Each bucket renders **both** representations DESIGN.md asks for: the
 * `caption`-labelled count + dollar pair, and the sequential-scale bar.
 *
 * §9.3: bar height is the **dollar total** — the materiality-weighted quantity
 * that actually matters — and the bar label is the item count. The fill walks
 * the ochre ramp from §9.2, darkest at 120+, so "this is the one that should
 * worry you" reads without a red that would collide with the REFUSE stamp's
 * meaning.
 */
export const AGING_BUCKETS = ["0–30", "31–60", "61–90", "120+"] as const;
export type AgingBucketLabel = (typeof AGING_BUCKETS)[number];

export type AgingBucket = {
  label: AgingBucketLabel;
  count: number;
  /** Decimal string. See lib/money.ts. */
  total: Money;
};

/** Ochre ramp steps, DESIGN.md §9.2. Index 0 = lightest, 3 = darkest. */
const RAMP = ["bg-ochre-1", "bg-ochre-2", "bg-ochre-3", "bg-ochre-4"] as const;

/**
 * Presentation-only magnitude, used solely to size a bar. Deliberately not part
 * of any money path: PLAN standing rule 3 keeps `Decimal`/decimal strings on the
 * data side, and nothing here feeds a posted amount.
 */
function barMagnitude(total: Money): number {
  const n = Number(total.replace(/[^0-9.\-]/g, ""));
  return Number.isFinite(n) ? Math.abs(n) : 0;
}

export type AgingBucketsProps = {
  buckets: readonly AgingBucket[];
  className?: string;
};

export function AgingBuckets({ buckets, className }: AgingBucketsProps) {
  const peak = Math.max(1, ...buckets.map((b) => barMagnitude(b.total)));

  return (
    <div
      data-slot="aging-buckets"
      className={cn("grid grid-cols-4 gap-3", className)}
    >
      {buckets.map((bucket, i) => {
        const share = Math.round((barMagnitude(bucket.total) / peak) * 100);
        return (
          <div key={bucket.label} className="flex flex-col gap-2">
            <div className="flex h-24 items-end border-b border-border-hairline">
              <div
                className={cn("w-full", RAMP[Math.min(i, RAMP.length - 1)])}
                style={{ height: `${share}%` }}
                role="img"
                aria-label={`${bucket.label} days: ${bucket.count} items, ${moneyAriaLabel(bucket.total)}`}
              />
            </div>
            <p className="font-ui text-caption font-medium uppercase tracking-caption text-ink-muted">
              {bucket.label} days
            </p>
            <p className="tabular font-numeral text-numeral-sm text-ink">
              {bucket.count.toLocaleString("en-US")} items
            </p>
            <p className="tabular font-numeral text-numeral-sm text-ink-muted">
              {formatMoney(bucket.total)}
            </p>
          </div>
        );
      })}
    </div>
  );
}
