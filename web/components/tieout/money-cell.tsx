import { cn } from "@/lib/utils";
import { formatMoney, moneyAriaLabel, type Money } from "@/lib/money";

/**
 * DESIGN.md §8 "Money cell" + §3.3 numeral rules.
 *
 * Right-aligned, mono, `tabular-nums lining-nums` (the `.tabular` utility in
 * globals.css) so the money column stays pixel-stable down the page. Negatives
 * carry a leading minus; the accounting parenthetical is optional and additive.
 * Colour is never the carrier of sign (§11).
 *
 * `density` follows DESIGN.md §5: comfortable → `numeral-md`, dense →
 * `numeral-sm` for the review queue and scoreboard tables.
 */
export type MoneyCellProps = {
  /** Decimal string, e.g. `"-412880.14"`. Never a JS number — see lib/money.ts. */
  value: Money;
  density?: "comfortable" | "dense";
  /** Also wrap negatives in parentheses, in addition to the minus sign. */
  accountingParens?: boolean;
  currencySymbol?: string;
  className?: string;
};

export function MoneyCell({
  value,
  density = "comfortable",
  accountingParens = false,
  currencySymbol = "$",
  className,
}: MoneyCellProps) {
  return (
    <span
      data-slot="money-cell"
      aria-label={moneyAriaLabel(value)}
      className={cn(
        "tabular block text-right font-numeral text-ink",
        density === "dense" ? "text-numeral-sm" : "text-numeral-md",
        className,
      )}
    >
      <span aria-hidden>{formatMoney(value, { currencySymbol, accountingParens })}</span>
    </span>
  );
}
