// The one runnable check the shell leaves behind: `npm test`.
//
// Money formatting is the only non-trivial logic in this package - grouping,
// sign placement, cents padding - and it is the logic whose failure is most
// visible (DESIGN.md section 3.3: misaligned or mis-signed numerals are the
// most conspicuous failure available to this product).
//
// Node's built-in test runner, run directly on the TypeScript source via Node
// 24's type stripping. No framework, no config, no extra dependency.
import assert from "node:assert/strict";
import { test } from "node:test";

import { formatMoney, moneyAriaLabel } from "./money.ts";

test("groups thousands and pads cents", () => {
  assert.equal(formatMoney("412880.14"), "$412,880.14");
  assert.equal(formatMoney("658342.69"), "$658,342.69");
  assert.equal(formatMoney("9.4"), "$9.40");
  assert.equal(formatMoney("0"), "$0.00");
  assert.equal(formatMoney("1000"), "$1,000.00");
  assert.equal(formatMoney("999"), "$999.00");
});

test("negatives carry the sign; parentheses are additive, never a substitute", () => {
  assert.equal(formatMoney("-1284.63"), "-$1,284.63");
  assert.equal(formatMoney("-1284.63", { accountingParens: true }), "-($1,284.63)");
});

test("does not round-trip through a JS number", () => {
  // 0.1 + 0.2 territory: a float path would surface here.
  assert.equal(formatMoney("0.145"), "$0.14");
  // Beyond Number.MAX_SAFE_INTEGER cents - a float path would lose digits.
  assert.equal(formatMoney("90071992547409919.99"), "$90,071,992,547,409,919.99");
});

test("aria label states currency, magnitude and sign in words", () => {
  assert.equal(
    moneyAriaLabel("-412880.14"),
    "412,880 dollars and 14 cents, credit",
  );
  assert.equal(moneyAriaLabel("9.40"), "9 dollars and 40 cents, debit");
});
