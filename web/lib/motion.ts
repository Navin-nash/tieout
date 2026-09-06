// DESIGN.md §7.1 — motion tokens as TypeScript constants.
//
// The same values live as CSS custom properties in app/globals.css (copied from
// DESIGN.md §12.1). They are duplicated here on purpose: a GSAP timeline cannot
// read a Tailwind token, and a CSS transition cannot read a TS object, so both
// surfaces need the number. Keeping them in one module means a DESIGN.md change
// has exactly two edit sites, not one per component.
//
// Durations are seconds here because that is GSAP's unit; the CSS side is ms.

export const DURATION = {
  instant: 0.1,
  fast: 0.16,
  base: 0.22,
  slow: 0.36,
  deliberate: 0.6,
} as const;

export const EASE = {
  standard: "cubic-bezier(0.4, 0, 0.2, 1)",
  outSnap: "cubic-bezier(0.16, 1, 0.3, 1)",
  inOutSoft: "cubic-bezier(0.65, 0, 0.35, 1)",
} as const;

/**
 * DESIGN.md §7.6 — the single reduced-motion gate, as a media query string.
 *
 * CSS transitions and animations are already collapsed globally in
 * app/globals.css. GSAP call sites branch on these two queries through
 * `gsap.matchMedia()` so the preference is consumed identically on both sides
 * and no component re-implements the check:
 *
 *   const mm = gsap.matchMedia();
 *   mm.add(MOTION_QUERY.allowed, () => { ...full timeline... });
 *   mm.add(MOTION_QUERY.reduced, () => { gsap.set(targets, { opacity: 1, y: 0, clearProps: "all" }); });
 *
 * DESIGN.md §7's governing rule still applies above all of this: motion never
 * gates the reading of a number. Every figure is in the DOM at full precision
 * on first paint, animated or not.
 */
export const MOTION_QUERY = {
  allowed: "(prefers-reduced-motion: no-preference)",
  reduced: "(prefers-reduced-motion: reduce)",
} as const;
