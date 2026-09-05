# Tieout — Visual & Interaction Design System

Scope note: this document is the **visual and interaction design system only** — direction,
theming, tokens, type, colour, grid, motion, components, data-viz, evidence typesetting,
accessibility, and implementation handoff. It does not restate architecture, data model,
invariants or business model — those live in `docs/SPEC.md` (the product spec; currently
`docs/DESIGN.md`, being renamed by a parallel worker), which this document cites by section
number rather than reproducing. Frontend stack is Next.js App Router + TypeScript + Tailwind v4
+ shadcn/ui + GSAP per ADR-002.

---

## 1. Design direction and rationale

**Direction in one line: this is an instrument of record, typeset like one — audit working
papers and ledger ruling, not a SaaS dashboard.**

The audience (SPEC's stated users: mid-market controllers, the auditors who test their work, and
a finance-tech-founder judge) reads financial statements for a living. That audience does not
need to be persuaded that software can look serious — they need the numbers to be legible,
column-aligned, and traceable to evidence, because that is the actual content of their job. Any
design move that spends attention on looking impressive instead of reading precisely is a move
against the product's own thesis: SPEC §1 argues that AccountingBench's frontier models fail by
fabricating a plug to satisfy a validation check, i.e. by **prioritising the appearance of a
closed book over the true state of the books**. A UI that prioritises the appearance of polish
over the true state of the data would be making the same mistake in a different medium.

So the vocabulary is deliberately narrow and mined from three real, load-bearing sources rather
than invented:

1. **Audit working papers and statement typesetting** — the register of a 10-K or a reconciliation
   workbook: serif for prose and citation, tight rules, numbers that column-align to the cent,
   totals underscored with a double rule the way a ledger closes a column.
2. **Terminal output** — SPEC §12's primary demo surface is `tieout close` printing `CLOSE
   REFUSED` to a monospaced terminal. The dashboard should feel like a legible, typeset rendition
   of the same event stream the CLI prints, not a different product wearing the same name.
3. **Swiss tabular data design** (Müller-Brockmann-lineage grid discipline) — for the grid
   itself: a strict column module, hairline rules instead of card shadows, and generous but not
   decorative whitespace. This is where restraint comes from; it is not itself the whole identity
   (a purely Swiss-grid fintech dashboard is now a genre with its own tells — see §2), it is the
   *structural* discipline underneath the ledger/statement surface treatment.

What this is explicitly not: a "trust and safety" SaaS aesthetic (soft shadows, pill badges,
rounded everything, a friendly rounded sans everywhere), and not a security-tool dark-mode
terminal-only aesthetic either — controllers work in daylight, on financial documents, which are
light. Dark mode is designed as a genuine second surface (§4), not a filter over the light one.

The single decision that most defines this system is the disposition palette (§1.1), because it
is the one place a wrong convention (traffic-light semantics) would actively misrepresent the
product's central claim.

### 1.1 The disposition scale — rejecting the traffic light, and what replaces it

SPEC §6 and §10 are explicit and this document treats it as a hard constraint: **a REFUSE is not
an error state, it is the system's correct and most valuable output** — "the only honest one
available given the data" (SPEC §10). A green/amber/red traffic light encodes the opposite claim:
that red means something went wrong. Shipping that encoding would visually contradict the one
sentence the product is built to prove.

Reject also the inverse fix some dashboards reach for — desaturating everything into a single
brand-blue "neutral" palette — because that erases the real distinction between "this is
settled" and "this blocks the close," which controllers must be able to scan a queue and
triage in seconds.

**The replacement principle: encode *epistemic status*, not severity.** Each disposition gets a
distinct visual register tied to what kind of claim it is making, not to how alarmed the viewer
should feel:

| Disposition | What it's actually claiming | Visual register |
|---|---|---|
| **T0 · AUTO_POST** | "Settled, unremarkable, no one needs to look at this." | **No colour, no badge fill, no border.** Plain ink-muted text, same weight as any other settled row. Unremarkable is achieved by literally withholding visual weight — the opposite of a green checkmark, which *celebrates*. Settled things don't need celebrating. |
| **T1 · AUTO_SAMPLED** | "Settled, *and independently checked* — this is control evidence." | A quiet, cool slate-blue tag, outline not fill, with a small ring/target glyph (not a checkmark). Blue reads as "measurement/audit," not "success" or "danger" — it borrows the register of a lab control sample, because that is literally what it is (SPEC §6: 5% sampled for control evidence). |
| **T2 · ESCALATE** | "Genuinely undecided. A human has not yet judged this." | An ochre/gold tag, paired with a clock glyph, never an exclamation mark. Ochre is chosen over amber specifically to avoid the "caution tape" connotation amber carries in UI — it reads closer to a court docket stamp ("pending") than a hazard warning. This is deliberately the *calmest* of the three coloured states, because ESCALATE is normal, expected system behaviour, not a warning that something is broken. |
| **T3 · REFUSE** | "Final. Blocking. Not a bug — an authoritative determination." | **Reclaims the accountant's own convention: red ink means a deficit, not a UI alarm.** Rendered as a *stamp*, not an alert: bold small-caps label, a double rule above and below (the ledger's own mark for "this total is closed"), deep oxblood ink on a pale wash — never a filled alert-red pill, never an exclamation triangle, never `role="alert"` styling borrowed from form-validation errors. The metaphor is a document stamped **VOID** or **REFUSED**, which is unambiguous, final, and carries no implication that a mistake occurred. |

This also fixes a real accessibility problem with three-state traffic lights: red/green/amber is
one of the least colour-vision-safe combinations available. Because T0 carries *no colour at all*
and T1–T3 are colour **and** shape **and** text-label coded (§11 accessibility), the scale
degrades gracefully for deuteranopia/protanopia without any fallback logic — removing colour
entirely still leaves three distinguishable glyphs and three distinguishable words.

---

## 2. What we will never ship

Explicit ban list — these are the tells that make an interface read as templated/AI-generated
regardless of how it was actually built, and this product's audience will notice them as
unseriousness:

- Purple/indigo/violet gradient hero sections.
- A radial glow or spotlight behind centered hero text.
- Glassmorphism, frosted/blurred cards, any `backdrop-filter` used decoratively.
- Floating 3D blobs, gradient orbs, gradient mesh backgrounds.
- Sparkle/star glyphs used as "AI" iconography, or any AI-signalling mascot.
- Emoji used as functional icons.
- The centered-hero → three-feature-icon-cards → gradient-CTA-band template.
- Unearned dark mode (dark-by-default with neon/saturated accents used to look "technical").
- Gradient-filled body text.
- Generic stock abstract imagery (isometric illustrations, floating UI mockup collages).
- A fake dashboard screenshot/mockup in the hero when a real, working screenshot exists — SPEC
  §12 says the dashboard ships with a completed run loaded specifically so this never has to
  happen; use it.
- "Supercharge your workflow with AI" register copy — any copy that markets the *feeling* of AI
  rather than stating the measured result.
- Rounded-pill badges for disposition or status of any kind (see §1.1 — status here is stamped
  and squared, never a pill).
- Drop-shadow "card" elevation as the default surface treatment (see §5 — rules, not shadows).

**What we do instead, positively:**

- A hero that states the number: the fabrication-rate finding, set in tabular mono at display
  size, sourced and dated, next to a one-line explanation of what it measures — not an
  illustration.
- Real terminal output (the actual `tieout close` transcript, SPEC §10) reproduced verbatim,
  typeset, as the hero's supporting visual — because it exists and is more convincing than any
  invented graphic.
- A warm, light paper background (§4) with ink-black text — a document, not a screen effect.
- Citations and regulatory references typeset like a real audit workpaper footnote (§10), because
  that register is unfakeable by a template and directly supports credibility with this audience.
- Colour spent only where SPEC gives it meaning (disposition, chart baselines) — everything else
  is ink, paper, and rule.

---

## 3. Typography

### 3.1 Families, licensing, hosting

Three families, one rationale: all three are **SIL Open Font License 1.1** (free, embeddable,
self-hostable, no attribution requirement beyond the license file), all three ship genuine
OpenType tabular-figure support, and none of them is Inter — a deliberate choice, because Inter
plus a rounded sans is now the single strongest visual tell of a templated product in 2026.

| Role | Family | Foundry / license | Use |
|---|---|---|---|
| **Statement / display** | **Source Serif 4** (variable) | Adobe, SIL OFL 1.1 | Landing headlines, evidence quotes, citations, section titles in `docs`-adjacent surfaces. A genuine text serif (not a display-only face), so it holds up at body sizes in the evidence panel too. |
| **UI / body** | **IBM Plex Sans** (variable) | IBM, SIL OFL 1.1 | All interface chrome: labels, nav, buttons, body copy, table headers. Engineered, slightly technical character without tipping into "startup rounded sans." |
| **Numerals / mono / terminal** | **IBM Plex Mono** | IBM, SIL OFL 1.1 | Every money figure, every table numeral, KPI tiles, terminal-output reproduction, work keys, hashes. Same family as the UI sans (shared x-height and stroke logic), so numerals feel native to the system rather than bolted on. |

**Hosting plan:** self-host via `next/font/google` for all three (Source Serif 4, IBM Plex Sans,
IBM Plex Mono are all published on Google Fonts under their OFL terms) — this downloads the woff2
files at build time and serves them from the app's own origin, so there is no runtime request to
fonts.googleapis.com and no FOUT/layout shift risk from a third-party host. If a future need
arises to pin an exact static (non-variable) weight set for file-size reasons, fall back to
`next/font/local` with the woff2s vendored under `web/public/fonts/` — same license, same files,
just self-selected weights.

```ts
// web/lib/fonts.ts
import { Source_Serif_4, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";

export const statement = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-statement",
  display: "swap",
});
export const ui = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ui",
  display: "swap",
});
export const numeral = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-numeral",
  display: "swap",
});
```

### 3.2 Type scale

All line-heights are unitless multipliers of the size. Tracking is in `em`.

| Token | Size / line-height | Weight | Tracking | Family | Use |
|---|---|---|---|---|---|
| `display-2xl` | 56px / 1.05 | 600 | −0.015em | statement | Landing hero statistic |
| `display-xl` | 40px / 1.1 | 600 | −0.01em | statement | Landing section headline |
| `display-lg` | 32px / 1.15 | 600 | −0.01em | statement | Page titles (close status, scoreboard) |
| `heading-md` | 24px / 1.3 | 600 | 0 | ui | Panel/section headings |
| `heading-sm` | 20px / 1.35 | 600 | 0 | ui | Card/subsection headings |
| `body-lg` | 18px / 1.6 | 400 | 0 | statement | Evidence-panel prose, landing body copy |
| `body` | 16px / 1.5 | 400 | 0 | ui | Default UI body text |
| `body-sm` | 14px / 1.45 | 400 | 0 | ui | Dense review-queue text, secondary copy |
| `caption` | 12px / 1.35 | 500 | +0.04em, uppercase | ui | Table headers, tag labels, eyebrows |
| `numeral-lg` | 32px / 1.1 | 500 | 0 | numeral | KPI/stat tile figures |
| `numeral-md` | 16px / 1.4 | 400 | 0 | numeral | Table money cells, standard rows |
| `numeral-sm` | 13px / 1.35 | 400 | 0 | numeral | Dense review-queue table cells |

### 3.3 Numeral rules (mandatory)

- Every cell where numbers column-align — money cells, KPI tiles, scoreboard metrics, aging
  buckets, work-key IDs — sets `font-variant-numeric: tabular-nums` (equivalently
  `font-feature-settings: "tnum" 1`), plus `"lnum" 1` (lining, not oldstyle figures) so digits
  sit on the baseline uniformly. This is non-negotiable per §7 (numerals are the hero).
- A dollar figure that appears **inline inside serif prose** (an evidence citation, a landing-page
  sentence) still gets a `<span class="tabular">` override to lining+tabular figures — Source
  Serif 4's default prose figures are proportional oldstyle, which is correct for reading prose
  but wrong the instant the figure is a number someone needs to compare against another number.
- Negative money values use a leading minus sign, never red-only or parenthetical-only encoding
  (parenthetical accounting negatives are permitted *in addition to* the sign, for the audience's
  own convention, but the sign/parenthesis is the carrier of meaning — not colour; see §11).

---

## 4. Colour

Two full token sets, light (primary) and dark (designed independently, not inverted). All ratios
below are **measured** WCAG 2.1 contrast ratios (relative-luminance formula, computed directly,
not estimated) — see `.contrast_check.py` methodology in this repo's history; numbers are exact.

### 4.1 Light (primary)

| Token | Hex | Role |
|---|---|---|
| `paper` | `#FAF9F6` | App/page background — warm paper, not pure white |
| `paper-inset` | `#F2F0EB` | Table zebra stripe, inset panels |
| `ink` | `#1A1613` | Primary text | 
| `ink-muted` | `#5B5650` | Secondary text, T0 disposition text, captions |
| `border-hairline` | `#D8D4CC` | Decorative dividers, table row rules (non-text, no ratio requirement) |
| `border-interactive` | `#8A8375` | Input borders, component boundaries (meets non-text 3:1) |
| `focus` | `#1B5FB0` | Focus ring — distinct hue from all disposition colours |
| `sampled` (T1) text / fill | `#3B5166` / `#E7ECEF` | AUTO_SAMPLED tag |
| `escalate` (T2) text / fill | `#7A5B12` / `#F5E9C9` | ESCALATE tag |
| `refuse` (T3) text / fill | `#7A1220` / `#F6E3E1` | REFUSE stamp |

Measured pairs:

| Pair | Ratio |
|---|---|
| `ink` on `paper` | **17.08 : 1** |
| `ink-muted` on `paper` | **6.90 : 1** |
| `border-interactive` on `paper` | **3.57 : 1** (meets non-text 3:1) |
| `focus` on `paper` | **6.03 : 1** |
| `sampled` text on `sampled` fill | **6.91 : 1** |
| `sampled` text on `paper` | **7.81 : 1** |
| `escalate` text on `escalate` fill | **5.22 : 1** |
| `escalate` text on `paper` | **5.98 : 1** |
| `refuse` text on `refuse` fill | **8.78 : 1** |
| `refuse` text on `paper` | **10.31 : 1** |

`border-hairline` on `paper` measures 1.40:1 — this is intentional and does not need to clear a
text ratio: it is a decorative row divider, never a text/component boundary carrying meaning on
its own (WCAG 1.4.11 exempts purely decorative, inactive UI elements).

### 4.2 Dark (designed, not inverted)

Dark paper is warm near-black (matches the ink family's hue, not a cool blue-black), and every
disposition colour is independently re-picked for contrast rather than auto-inverted, because
naive inversion of the oxblood REFUSE red goes muddy against a dark background.

| Token | Hex | Role |
|---|---|---|
| `paper` | `#15130F` | App background |
| `paper-inset` | `#1E1B16` | Table zebra, inset panels |
| `ink` | `#EDE9E2` | Primary text |
| `ink-muted` | `#A39C90` | Secondary text, T0 text |
| `border-hairline` | `#37322A` | Decorative dividers |
| `border-interactive` | `#726A59` | Input borders, component boundaries |
| `focus` | `#6FA8E8` | Focus ring |
| `sampled` (T1) text / fill | `#9CC1E8` / `#1D2A34` | AUTO_SAMPLED tag |
| `escalate` (T2) text / fill | `#E8C769` / `#332707` | ESCALATE tag |
| `refuse` (T3) text / fill | `#E8828C` / `#341216` | REFUSE stamp |

Measured pairs:

| Pair | Ratio |
|---|---|
| `ink` on `paper` | **15.33 : 1** |
| `ink-muted` on `paper` | **6.82 : 1** |
| `border-interactive` on `paper` | **3.47 : 1** |
| `focus` on `paper` | **7.46 : 1** |
| `sampled` text on `sampled` fill | **7.82 : 1** |
| `sampled` text on `paper` | **9.90 : 1** |
| `escalate` text on `escalate` fill | **8.93 : 1** |
| `escalate` text on `paper` | **11.31 : 1** |
| `refuse` text on `refuse` fill | **6.43 : 1** |
| `refuse` text on `paper` | **7.07 : 1** |

Every text pairing above clears WCAG AA (4.5:1 normal text) with margin; most clear AAA (7:1).

---

## 5. Space, grid and layout

Spacing scale is the standard 4px-base Tailwind scale (0, 1, 2, 3, 4, 6, 8, 10, 12, 16, 20, 24,
32, 40, 48, 64, 80, 96 → `px-1`…`px-24`) — reused rather than reinvented, per YAGNI; the only
system-specific additions are container widths and the two density modes below.

**Container widths**

- Marketing (landing): `max-width: 75rem` (1200px) page shell; a narrower `max-width: 45rem`
  (720px) reading column for evidence prose, citations and quotes specifically — long lines of
  serif prose hurt readability past ~75 characters.
- App (dashboard, review queue, scoreboard): fluid to `max-width: 90rem` (1440px), no narrow
  reading column — these are data surfaces, not prose surfaces.

**Density modes**

| Mode | Row height | Cell padding | Type | Where |
|---|---|---|---|---|
| Comfortable | 48px | 16px | `body` / `numeral-md` | Landing page, dialogs, close-status summary |
| Dense | 32px | 8px | `body-sm` / `numeral-sm` | Review queue, scoreboard tables |

**The data-table grid**

CSS Grid with named, fixed-or-flexible columns — not a generic `<table>` with auto layout, so
the money column stays pixel-stable across rows regardless of content length elsewhere:

```
grid-template-columns:
  [badge]   96px
  [key]     120px
  [desc]    minmax(200px, 1fr)
  [amount]  128px
  [conf]    72px
  [age]     64px
  [actions] 96px;
```

Ledger ruling: a single 1px `border-hairline` under every row (horizontal rule only — no vertical
column borders), **except** one vertical rule immediately to the left of the `amount` column,
reproducing the ruled "money column" of a physical ledger sheet. Column totals (scoreboard,
close-status summary) get the ledger's own device for a closed total: a double rule (1px + 1px
with a 2px gap) directly above the total row.

---

## 6. Border, radius, elevation

**Shadows are rejected as the default surface language.** A drop-shadow simulates a light source
and physical depth — the visual grammar of an OS window manager or a "card" SaaS dashboard. This
product's surface is a document: documents are differentiated by rules, not by pretending to
float above the page. Elevation is expressed by **hairline border + background-tint** (e.g. an
inset panel uses `paper-inset` + `border-hairline`, nothing else).

**The one exception:** transient overlays that must unambiguously read as floating above
everything else — the dialog and the toast — get a single, deliberately restrained shadow token
(`shadow-overlay: 0 4px 16px rgb(0 0 0 / 0.12)` light, `0 4px 20px rgb(0 0 0 / 0.4)` dark), always
paired with a `border-hairline`, never used elsewhere. One token, two uses, no shadow scale.

**Radius:** mostly square. `radius-none` (0) is the default for panels, tables, evidence blocks —
document elements don't have rounded corners. `radius-sm` (2px) for disposition badges/stamps
(barely-there, stamp-like, never a pill). `radius-md` (4px) for buttons, inputs, toasts — enough
to read as an interactive, clickable object without becoming decorative. No `radius-lg`/`-full`
anywhere in the system; a fully-rounded pill badge is explicitly on the ban list (§2).

---

## 7. Motion system (GSAP)

**Governing rule: motion must never gate the reading of a number.** Every value a controller
needs is present in the DOM at full precision on first paint; GSAP only ever animates presentation
on top of an already-correct, already-readable value. Nothing in this system requires an
animation to finish, or a scroll position to be scrubbed to a particular point, before the true
number is available to sighted or assistive-tech reading.

### 7.1 Tokens

```css
/* durations */
--motion-instant: 100ms;   /* hover, focus, toggle */
--motion-fast:    160ms;   /* button press, badge state change */
--motion-base:    220ms;   /* panel open/close, row expand, dialog/toast */
--motion-slow:    360ms;   /* page-level transitions, non-hero scroll reveals */
--motion-deliberate: 600ms; /* landing-page scroll-driven storytelling only */

/* easings */
--ease-standard:   cubic-bezier(0.4, 0, 0.2, 1);   /* general purpose */
--ease-out-snap:   cubic-bezier(0.16, 1, 0.3, 1);  /* entrances */
--ease-in-out-soft: cubic-bezier(0.65, 0, 0.35, 1); /* scroll-linked scrub */
```

### 7.2 What animates, what deliberately does not

**Animates:** landing-page section/evidence-card entrances (`gsap.from`, translateY 8px + opacity,
staggered via `ScrollTrigger.batch`); the ScrollTrigger-scrubbed build-up of the two-axis chart
(§9) as the evidence section scrolls; disposition badge *icon* transitions (approve/reject
confirmation) at `--motion-fast`; dialog scale-in (0.98→1 opacity+scale) and toast slide-in at
`--motion-base`.

**Deliberately does not animate:** the digits of any money cell or KPI figure in the dashboard —
no odometer/count-up on numbers that live in the working app (only the landing-page hero
statistic gets a one-time count-up flourish, and even there the full-precision number is present
in the markup from first paint, `aria-live` off, so nothing but a decorative overlay is
animating); disposition badge **colour/label swap** — instant, never crossfaded, so a controller
can never be shown a momentarily-ambiguous intermediate disposition; review-queue **row
re-sorting** on a materiality×age sort — snaps instantly, no FLIP animation, because an animated
reorder risks a controller clicking a row based on a position it's mid-transition out of; nothing
ever auto-scrolls, auto-advances, or auto-dismisses a state the user hasn't acknowledged.

### 7.3 ScrollTrigger rules

Scroll-driven behaviour is **landing-page only** — never in the app shell (dashboard, review
queue, scoreboard scroll natively with zero ScrollTrigger instances). On the landing page:

- Pin only the evidence/chart section, and only for the duration its scrub genuinely drives
  content (the chart's three baselines plotting in sequence, tied to scroll).
- `scrub: 0.4` (a short smoothing window), never `scrub: true` (unbounded — feels laggy and
  decouples from the user's own scroll input).
- `invalidateOnRefresh: true` on every instance (resize-safe).
- Card/stat entrances outside the pinned section use `ScrollTrigger.batch`, not one instance per
  element, to keep the observer count and layout-read count bounded.

### 7.4 `useGSAP` and cleanup

```tsx
// registered once, module scope
gsap.registerPlugin(useGSAP, ScrollTrigger);

function EvidenceSection() {
  const scope = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    const cards = gsap.utils.toArray<HTMLElement>(".evidence-card", scope.current);
    ScrollTrigger.batch(cards, {
      onEnter: (batch) =>
        gsap.from(batch, {
          opacity: 0,
          y: 8,
          duration: 0.36, // --motion-slow
          ease: "cubic-bezier(0.16,1,0.3,1)",
          stagger: 0.06,
          overwrite: true,
        }),
      start: "top 85%",
    });
  }, { scope, dependencies: [] }); // useGSAP + gsap.context auto-reverts on unmount

  return <div ref={scope}>{/* ...evidence-card children... */}</div>;
}
```

All selectors are scoped to `scope.current` — never a bare `document.querySelector` — so
client-navigated route changes never leave orphaned tweens targeting unmounted nodes.

### 7.5 Performance rules

Animate **transform and opacity only** — translate/scale, never `top`/`left`/`width`/`height`/
box-shadow blur radius (each forces layout or paint). Toggle `will-change: transform` on
`onStart`, remove it on `onComplete` — never left permanently set. Batch DOM reads via
`ScrollTrigger.batch`/`gsap.utils.toArray` rather than per-element instances. Use
`gsap.matchMedia()` to branch motion configuration by viewport/media query rather than
conditional logic scattered through components.

### 7.6 `prefers-reduced-motion` (mandatory, single gate)

Implemented once, centrally — every GSAP call site consumes the same gate, so it cannot be
missed component-by-component:

```ts
const mm = gsap.matchMedia();

mm.add("(prefers-reduced-motion: no-preference)", () => {
  // full motion config — durations/easings/ScrollTrigger pin+scrub as specified above
});

mm.add("(prefers-reduced-motion: reduce)", () => {
  // every duration collapses to ~0; ScrollTrigger pin disabled (section scrolls natively);
  // all elements set to their final opacity/transform state immediately; no stagger.
  gsap.set(".evidence-card, [data-motion]", { opacity: 1, y: 0, scale: 1, clearProps: "all" });
});
```

---

## 8. Component specs

- **Button** — `radius-md`, `body` weight 500, two variants only: `primary` (ink fill / paper
  text) and `secondary` (paper fill / `border-interactive` outline). No ghost/tertiary sprawl.
  Height 40px dense contexts, 44px comfortable (meets 44px touch target). Focus: 2px `focus` ring,
  2px offset, never `outline: none` without a replacement.
- **Input** — `radius-md`, `border-interactive` 1px, `paper` fill, `body` text. Error state: text
  label ("must be a positive amount") *and* border colour change to `refuse` text colour — never
  colour alone. Height matches button height for row alignment in forms.
- **Data table** — per §5 grid. Header row: `caption` style (uppercase, +0.04em), sticky on
  scroll in dense mode. Zebra via `paper-inset`, not borders, in comfortable mode; dense mode uses
  hairline row rules only (zebra reads as visual noise at 32px row height).
- **Disposition badge** — per §1.1: T0 is bare `ink-muted` text, no badge chrome at all. T1–T3 are
  `radius-sm` (2px) tags, outline not fill for T1/T2, stamp treatment (double rule, small-caps,
  bold) for T3. Always paired with an SR-only full-sentence label (§11).
- **Money cell** — `numeral-md`/`numeral-sm`, right-aligned, tabular-nums mandatory, leading minus
  for negatives, optional parenthetical (accounting convention) in addition to the sign, never
  colour-only for negative.
- **Stat / KPI tile** — `numeral-lg` figure, `caption` label above, one-line delta/context below
  in `ink-muted`. No sparkline inside the tile (sparklines belong in §9's dedicated charts, not
  crammed into a 120px tile).
- **Evidence panel** — `paper-inset` background, `border-hairline`, `body-lg`/statement serif for
  the narrative, citations/quotes typeset per §10, a `caption`-labelled source line always present.
- **Aging bucket** — four fixed buckets (30/60/90/120+ days) per SPEC §10; rendered both as a
  `caption`-labelled count+dollar pair and as the sequential-scale bar in §9.
- **CLOSE REFUSED / CLOSED banner** — the single largest, most unambiguous element on the close
  status screen: full-width, `display-lg`, small-caps, `refuse`-stamp treatment for REFUSED
  (double rule top+bottom) or plain `ink` on `paper-inset` for CLOSED (deliberately calm —
  closing successfully is not a celebration, it's the expected, unremarkable outcome per §1.1's
  T0 logic applied to the period as a whole).
- **Review action bar** — approve / reject / reclassify. **Identity requirement**: every action
  opens a confirmation step requiring the acting identity (pre-filled from session, per SPEC's
  four-eyes requirement) and an optional note before commit — no bare single-click destructive
  action, no keyboard shortcut that commits without the confirmation step.
- **Empty state** — `ink-muted` `body` text + one specific next action (never a generic
  illustration). E.g. review queue empty: "No items pending review. Next scheduled run: —."
- **Loading state** — skeleton rows matching the real grid's column widths exactly (so layout
  doesn't shift on load), `paper-inset` shimmer at `--motion-slow`, respects reduced-motion (static
  tint, no shimmer).
- **Error state** — `refuse` text colour + icon + specific message + retry action. Never a bare
  toast for a page-level failure — page-level errors get an inline panel with retry.
- **Toast** — `radius-md`, `shadow-overlay`, auto-dismiss only for non-critical confirmations
  (e.g. "Note saved"); anything disposition-affecting stays until dismissed manually.
- **Dialog** — `radius-md`, `shadow-overlay` + `border-hairline`, scale-in per §7, used for every
  review action's identity-confirmation step.

---

## 9. Data visualisation

Per SPEC §11, the two-axis chart is the chart that carries the demo. Categorical colour choices
deliberately **reuse the disposition-scale semantics** rather than introducing an arbitrary new
categorical palette, so the whole system reads as one coherent visual language rather than
dashboard-colours-here, brand-colours-there.

### 9.1 Fabrication rate × straight-through rate (the headline chart)

- Axes: x = straight-through rate (0–100%), y = fabrication rate (0–~8%, headroom above the
  worst observed baseline). Always plotted together — SPEC §11 is explicit that either alone is
  gameable.
- **Baseline A (Naive LLM)** — marker: filled triangle, colour `refuse` (the oxblood). Intentional
  reuse: this baseline is *what fabrication looks like when nothing stops it* — visually rhyming
  it with the REFUSE stamp colour argues the thesis without a caption needing to.
  Light `#7A1220` / dark `#E8828C`.
- **Baseline B (Deterministic only)** — marker: filled square, colour `sampled` slate-blue (safe,
  measured, control-sample register — "safe but unusable" per SPEC §11).
  Light `#3B5166` / dark `#9CC1E8`.
  Both meet the same measured ratios reported in §4 (these are text-role colours reused as marker
  fills; markers additionally get a `border-hairline` stroke so they read against either paper
  tone regardless of fill contrast).
- **Baseline C (Tieout)** — marker: filled circle in plain `ink`, plus a bracket/target region
  (dashed `border-interactive` box) marking the "zero fabrication, high STP" corner. Plain ink,
  not a celebratory colour — the target state is "unremarkable and settled," matching the T0
  register (§1.1): the system winning looks calm, not neon-green.
- Gridlines: `border-hairline`, 25% increments. Axis labels: `caption`. No legend colour swatches
  alone — every baseline's legend entry pairs colour + marker shape + text name (§11).

### 9.2 Per-class precision / recall (11 outcome classes)

Rendered as a **typeset numeric table**, not a chart — with 11 categories, a bar/donut chart
would need 11 discriminable hues, which fails the "colour is never the sole carrier" rule at that
count. Instead: class name (`body-sm`), precision (`numeral-sm`), recall (`numeral-sm`), and a
single-hue **sequential tint** behind the cell reinforcing magnitude (darker = higher), computed
from the `escalate` ochre family (chosen because this table is fundamentally about
"how much human judgement got this right," which is escalation-adjacent):

| Step | Light fill | Dark fill |
|---|---|---|
| 0–25% | `#FBF3DC` | `#241D08` |
| 25–50% | `#F3E0A8` | `#4A3A0E` |
| 50–75% | `#E8C769` | `#6E5714` |
| 75–100% | `#C7A030` | `#9C7D1E` |

Text on every fill stays `ink`/`ink-muted` (not the ochre text colour) so the number itself never
loses contrast to the magnitude tint; the tint is decorative reinforcement, the number is the
actual carrier.

### 9.3 Aging distribution

Bar chart, four buckets (30/60/90/120+ days, SPEC §10). Bar height = dollar total (the
materiality-weighted quantity that actually matters), bar label = item count. Sequential fill
using the same ochre ramp as §9.2 (aging is the same "pending judgement" semantic family as
ESCALATE), darkest at 120+ to read as "this is the one that should worry you," without needing a
red danger colour that would collide with the REFUSE stamp's meaning.

---

## 10. Evidence presentation patterns (landing page)

- **Statistic** — `numeral-lg`/`display-2xl` figure in mono, tabular, immediately followed by a
  `body-sm` `ink-muted` one-line definition of exactly what was measured, and a `caption` source
  line ("AccountingBench, n=…, see docs/RESEARCH.md"). Never a bare large number with no
  methodology line beneath it.
- **Citation (regulatory reference)** — set in `caption` style (uppercase, `ui` family, +0.04em
  tracking) with a leading tick/section-mark glyph, e.g. `§ AS 2401 ¶.61`, colour `ink-muted`,
  always a live-feeling but non-essential hover/footnote target for the full standard title —
  never colour-linked (blue link text) since these are references, not navigation.
- **Verbatim quote** — `statement` (Source Serif 4) italic, set in an indented block with a
  single `border-interactive` left rule (2px), no giant decorative quotation-mark glyphs. Source
  attribution directly below in `caption`, not inline.
- **Inline dollar figures in prose** — per §3.3, always get the tabular-lining-figure span
  override even mid-sentence in serif body copy.

---

## 11. Accessibility

- **Focus visibility** — every interactive element gets the `focus` token ring (2px, 2px offset),
  on both light and dark, at the measured ratios in §4. Never removed without a same-strength
  replacement.
- **Keyboard path through the review queue** — arrow keys move row focus; `Enter` opens the
  detail/evidence panel; `A`/`R`/`C` map to approve/reject/reclassify but only ever **open the
  identity-confirmation dialog** (§8) — no keyboard shortcut commits a disposition change
  directly, matching the four-eyes requirement.
- **Target sizes** — interactive targets ≥24×24px minimum (WCAG 2.2 §2.5.8); actual buttons/row
  action controls are 40px (dense) / 44px (comfortable), exceeding the minimum.
- **Disposition badge, screen-reader treatment** — the badge is never colour/icon alone to
  assistive tech; every instance carries a visually-hidden full-sentence label, e.g.
  `<span class="sr-only">Disposition: Refused — blocks period close</span>`.
- **Money cell, screen-reader treatment** — `aria-label` states currency, magnitude and sign in
  words rather than relying on a stray glyph, e.g. `aria-label="412,880 dollars and 14 cents,
  debit"` rather than `-$412,880.14` alone.
- **Colour is never the sole carrier** — enforced structurally, not just as a guideline: every
  disposition state pairs colour with (a) a distinct glyph/marker shape and (b) a text label,
  everywhere it appears (badges, chart legends, table cells).

---

## 12. Implementation handoff

### 12.1 Tailwind v4 `@theme`

```css
@theme {
  /* fonts */
  --font-statement: var(--font-statement), ui-serif, Georgia, serif;
  --font-ui: var(--font-ui), ui-sans-serif, system-ui, sans-serif;
  --font-numeral: var(--font-numeral), ui-monospace, "SF Mono", monospace;

  /* light surface */
  --color-paper: #FAF9F6;
  --color-paper-inset: #F2F0EB;
  --color-ink: #1A1613;
  --color-ink-muted: #5B5650;
  --color-border-hairline: #D8D4CC;
  --color-border-interactive: #8A8375;
  --color-focus: #1B5FB0;

  /* disposition — light */
  --color-sampled: #3B5166;
  --color-sampled-fill: #E7ECEF;
  --color-escalate: #7A5B12;
  --color-escalate-fill: #F5E9C9;
  --color-refuse: #7A1220;
  --color-refuse-fill: #F6E3E1;

  /* radius */
  --radius-none: 0px;
  --radius-sm: 2px;
  --radius-md: 4px;

  /* motion */
  --duration-instant: 100ms;
  --duration-fast: 160ms;
  --duration-base: 220ms;
  --duration-slow: 360ms;
  --duration-deliberate: 600ms;
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-out-snap: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out-soft: cubic-bezier(0.65, 0, 0.35, 1);

  --shadow-overlay: 0 4px 16px rgb(0 0 0 / 0.12);
}

.dark {
  --color-paper: #15130F;
  --color-paper-inset: #1E1B16;
  --color-ink: #EDE9E2;
  --color-ink-muted: #A39C90;
  --color-border-hairline: #37322A;
  --color-border-interactive: #726A59;
  --color-focus: #6FA8E8;

  --color-sampled: #9CC1E8;
  --color-sampled-fill: #1D2A34;
  --color-escalate: #E8C769;
  --color-escalate-fill: #332707;
  --color-refuse: #E8828C;
  --color-refuse-fill: #341216;

  --shadow-overlay: 0 4px 20px rgb(0 0 0 / 0.4);
}
```

### 12.2 shadcn/ui CSS-variable theme

Mapped onto shadcn's own variable names so `web-scaffold`'s shadcn components pick these up
unchanged:

```css
:root {
  --background: 40 27% 97%;        /* #FAF9F6 */
  --foreground: 25 15% 10%;        /* #1A1613 */
  --card: 40 27% 97%;
  --card-foreground: 25 15% 10%;
  --popover: 40 27% 97%;
  --popover-foreground: 25 15% 10%;
  --primary: 25 15% 10%;           /* ink-fill buttons */
  --primary-foreground: 40 27% 97%;
  --secondary: 40 15% 92%;         /* paper-inset */
  --secondary-foreground: 25 15% 10%;
  --muted: 40 15% 92%;
  --muted-foreground: 30 5% 35%;   /* ink-muted */
  --accent: 210 63% 39%;           /* focus blue, sparing use */
  --accent-foreground: 40 27% 97%;
  --destructive: 353 74% 28%;      /* refuse oxblood — used ONLY for T3, never generic errors */
  --destructive-foreground: 8 47% 92%;
  --border: 40 12% 82%;            /* border-hairline */
  --input: 35 10% 55%;             /* border-interactive */
  --ring: 210 63% 39%;             /* focus */
  --radius: 0.25rem;               /* radius-md */
}

.dark {
  --background: 30 15% 7%;         /* #15130F */
  --foreground: 40 20% 91%;        /* #EDE9E2 */
  --card: 30 15% 7%;
  --card-foreground: 40 20% 91%;
  --popover: 30 15% 7%;
  --popover-foreground: 40 20% 91%;
  --primary: 40 20% 91%;
  --primary-foreground: 30 15% 7%;
  --secondary: 32 13% 12%;         /* paper-inset dark */
  --secondary-foreground: 40 20% 91%;
  --muted: 32 13% 12%;
  --muted-foreground: 30 10% 62%;  /* ink-muted dark */
  --accent: 210 68% 68%;
  --accent-foreground: 30 15% 7%;
  --destructive: 353 73% 76%;      /* refuse dark */
  --destructive-foreground: 353 45% 14%;
  --border: 40 12% 18%;
  --input: 40 12% 40%;
  --ring: 210 68% 68%;
  --radius: 0.25rem;
}
```

`--destructive` is intentionally the *only* shadcn slot reused for the REFUSE stamp — it must
never be reused generically for form-validation errors elsewhere, or the "REFUSE is authoritative,
not an error" argument in §1.1 is undermined by the component library's own naming. Form errors
use the same hex but styled per §8's Input error spec (label + border, not a red alert banner).

---

## Contradictions with `docs/SPEC.md` to reconcile

None found that require a spec change. Two notes for the orchestrator:

1. SPEC §12 lists `tieout serve` as launching "dashboard on :8000" from the CLI/FastAPI process;
   ADR-002 makes the dashboard a separate Next.js app. This document assumes ADR-002 supersedes
   that line (as ADR-002 itself states), so `tieout serve` should be read as serving the FastAPI
   JSON API only, with the Next.js app as a separate process consuming it — worth `web-scaffold`
   and whoever edits SPEC §12/§13 confirming they agree, since it's their file to fix, not mine.
2. This document assumes the dashboard's "ships with a completed run loaded" example data (SPEC
   §12) is labelled ReconRiver per SPEC's own instruction — flagging only because §2's "no fake
   dashboard mockups" ban depends on that real, labelled data actually existing by demo time.
