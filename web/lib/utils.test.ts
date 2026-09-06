// Regression check for the class-merge configuration.
//
// This failed silently once already: an unconfigured tailwind-merge treats
// `text-caption` as a colour, so `cn("text-caption text-sampled")` deleted the
// size and every disposition badge rendered at the inherited font size while
// the class was still visible in the source. Nothing in a build or a lint
// catches that; only this does.
import assert from "node:assert/strict";
import { test } from "node:test";

import { cn } from "./utils.ts";

test("keeps a DESIGN.md font size alongside a DESIGN.md colour", () => {
  assert.equal(cn("text-caption text-sampled"), "text-caption text-sampled");
  assert.equal(cn("text-numeral-md text-ink"), "text-numeral-md text-ink");
  assert.equal(cn("text-display-lg text-refuse"), "text-display-lg text-refuse");
});

test("still de-duplicates within a group", () => {
  assert.equal(cn("text-ink", "text-refuse"), "text-refuse");
  assert.equal(cn("text-body", "text-body-sm"), "text-body-sm");
  assert.equal(cn("tracking-caption", "tracking-display-lg"), "tracking-display-lg");
});

test("stock Tailwind groups are unaffected", () => {
  assert.equal(cn("text-sm text-red-500"), "text-sm text-red-500");
  assert.equal(cn("px-2", "px-4"), "px-4");
});
