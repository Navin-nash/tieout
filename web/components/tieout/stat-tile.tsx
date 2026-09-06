import { cn } from "@/lib/utils";

/**
 * DESIGN.md §8 "Stat / KPI tile": `caption` label above, `numeral-lg` figure,
 * one-line context below in `ink-muted`. No sparkline inside the tile — charts
 * live in §9, not crammed into a 120px box.
 *
 * Elevation is a hairline border plus a background tint (§6). No shadow: the
 * surface is a document, not a floating card.
 *
 * The figure is passed pre-formatted as a string so a rate ("98.2%"), a count
 * ("11,539") and a money figure all use one tile. Money figures should come
 * from `formatMoney` so they never round-trip through a JS number.
 */
export type StatTileProps = {
  label: string;
  value: string;
  /** One line of context or definition. SPEC §12 pairs every rate with its counterweight. */
  context?: string;
  className?: string;
};

export function StatTile({ label, value, context, className }: StatTileProps) {
  return (
    <div
      data-slot="stat-tile"
      className={cn(
        "flex flex-col gap-1 border border-border-hairline bg-paper-inset px-4 py-3",
        className,
      )}
    >
      <p className="font-ui text-caption font-medium uppercase tracking-caption text-ink-muted">
        {label}
      </p>
      <p className="tabular font-numeral text-numeral-lg text-ink">{value}</p>
      {context ? (
        <p className="font-ui text-body-sm text-ink-muted">{context}</p>
      ) : null}
    </div>
  );
}
