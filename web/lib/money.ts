// Money formatting for the UI layer.
//
// Amounts cross the wire as **decimal strings**, never JS numbers: PLAN standing
// rule 3 says a float must never reach a money field, and `JSON.parse` on a
// number is exactly that. So the formatter is string-in, string-out and never
// converts through `Number` — grouping is done on the digits themselves.
//
// DESIGN.md §3.3: negatives carry a leading minus sign as the meaning-bearing
// mark. The accounting parenthetical is permitted *in addition to* the sign,
// never instead of it, and colour is never the carrier.

/** A money amount as a decimal string, e.g. `"-412880.14"`. */
export type Money = string;

function group(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export type FormatMoneyOptions = {
  /** Prefix, default `"$"`. Pass `""` for a bare figure. */
  currencySymbol?: string;
  /** Also wrap negatives in parentheses (accounting convention). */
  accountingParens?: boolean;
};

/** `"-412880.14"` → `"-$412,880.14"` (or `"-($412,880.14)"` with parens on). */
export function formatMoney(value: Money, options: FormatMoneyOptions = {}): string {
  const { currencySymbol = "$", accountingParens = false } = options;
  const negative = value.trim().startsWith("-");
  const [whole = "0", fraction = ""] = value.trim().replace(/^[-+]/, "").split(".");
  const cents = (fraction + "00").slice(0, 2);
  const body = `${currencySymbol}${group(whole)}.${cents}`;

  if (!negative) return body;
  return accountingParens ? `-(${body})` : `-${body}`;
}

/**
 * DESIGN.md §11: a money cell states currency, magnitude and sign in words to
 * assistive tech rather than relying on a glyph a screen reader may skip.
 */
export function moneyAriaLabel(value: Money, options: { currency?: string } = {}): string {
  const { currency = "dollars" } = options;
  const negative = value.trim().startsWith("-");
  const [whole = "0", fraction = ""] = value.trim().replace(/^[-+]/, "").split(".");
  const cents = (fraction + "00").slice(0, 2);
  return `${group(whole)} ${currency} and ${cents} cents, ${negative ? "credit" : "debit"}`;
}
