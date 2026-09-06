// Dev-only proof page: every token and every primitive from DESIGN.md, on one
// screen, so the design system is verifiable at a glance and the landing-page,
// dashboard-ui and agent-ui workers have a reference to build against.
//
// The folder is named `%5Fdev` because Next.js private folders (`_name`) are
// excluded from routing entirely; `%5F` is the documented way to create an
// underscore URL segment, so this page lives at /_dev/tokens.
import {
  AgingBuckets,
  CloseBanner,
  DispositionBadge,
  MoneyCell,
  StatTile,
  type Disposition,
} from "@/components/tieout";
import { FIXTURE_CLOSE_STATUS, FIXTURE_NOTICE, FIXTURE_REVIEW_QUEUE } from "@/lib/fixtures";
import { formatMoney } from "@/lib/money";

import { ThemeToggle } from "./theme-toggle";

// Swatch classes are written out in full, never interpolated: Tailwind scans
// source text for complete class names, so `bg-${name}` produces no CSS at all.
const LIGHT_SURFACE = [
  { cls: "bg-paper", name: "paper", hex: "#FAF9F6" },
  { cls: "bg-paper-inset", name: "paper-inset", hex: "#F2F0EB" },
  { cls: "bg-ink", name: "ink", hex: "#1A1613" },
  { cls: "bg-ink-muted", name: "ink-muted", hex: "#5B5650" },
  { cls: "bg-border-hairline", name: "border-hairline", hex: "#D8D4CC" },
  { cls: "bg-border-interactive", name: "border-interactive", hex: "#8A8375" },
  { cls: "bg-focus", name: "focus", hex: "#1B5FB0" },
];

const DISPOSITION_COLOURS = [
  { cls: "bg-sampled", name: "sampled", hex: "#3B5166" },
  { cls: "bg-escalate", name: "escalate", hex: "#7A5B12" },
  { cls: "bg-refuse", name: "refuse", hex: "#7A1220" },
  { cls: "bg-sampled-fill", name: "sampled-fill", hex: "#E7ECEF" },
  { cls: "bg-escalate-fill", name: "escalate-fill", hex: "#F5E9C9" },
  { cls: "bg-refuse-fill", name: "refuse-fill", hex: "#F6E3E1" },
];

const OCHRE_RAMP = [
  { cls: "bg-ochre-1", name: "ochre-1", hex: "#FBF3DC" },
  { cls: "bg-ochre-2", name: "ochre-2", hex: "#F3E0A8" },
  { cls: "bg-ochre-3", name: "ochre-3", hex: "#E8C769" },
  { cls: "bg-ochre-4", name: "ochre-4", hex: "#C7A030" },
];

const TYPE_SCALE = [
  { cls: "font-statement text-display-2xl tracking-display-2xl font-semibold", label: "display-2xl / 56 / 1.05 · −0.015em · statement", sample: "15% of balance" },
  { cls: "font-statement text-display-xl tracking-display-xl font-semibold", label: "display-xl / 40 / 1.1 · −0.01em · statement", sample: "The books must balance." },
  { cls: "font-statement text-display-lg tracking-display-lg font-semibold", label: "display-lg / 32 / 1.15 · −0.01em · statement", sample: "Close status" },
  { cls: "font-ui text-heading-md font-semibold", label: "heading-md / 24 / 1.3 · ui", sample: "Review queue" },
  { cls: "font-ui text-heading-sm font-semibold", label: "heading-sm / 20 / 1.35 · ui", sample: "Blocking items" },
  { cls: "font-statement text-body-lg", label: "body-lg / 18 / 1.6 · statement", sample: "A refusal is not a failure of the system — it is the system's output." },
  { cls: "font-ui text-body", label: "body / 16 / 1.5 · ui", sample: "Every entry carries lineage, identity and support." },
  { cls: "font-ui text-body-sm", label: "body-sm / 14 / 1.45 · ui", sample: "Dense review-queue text and secondary copy." },
  { cls: "font-ui text-caption uppercase tracking-caption font-medium", label: "caption / 12 / 1.35 · +0.04em · ui", sample: "Posted 05 Sep 2026 · policy 2026.01-r3" },
];

const NUMERAL_SCALE = [
  { cls: "text-numeral-lg", label: "numeral-lg / 32 / 1.1 · KPI figures", sample: "$658,342.69" },
  { cls: "text-numeral-md", label: "numeral-md / 16 / 1.4 · table money cells", sample: "11,539 items · 98.2%" },
  { cls: "text-numeral-sm", label: "numeral-sm / 13 / 1.35 · dense cells", sample: "0.00 · $9.40 · WK-2026-01-004182" },
];

// DESIGN.md §5 — the standard 4px-base Tailwind scale, reused rather than
// reinvented. Written out so Tailwind emits the widths.
const SPACING = [
  { cls: "w-1", label: "1 · 4px" },
  { cls: "w-2", label: "2 · 8px" },
  { cls: "w-3", label: "3 · 12px" },
  { cls: "w-4", label: "4 · 16px" },
  { cls: "w-6", label: "6 · 24px" },
  { cls: "w-8", label: "8 · 32px" },
  { cls: "w-10", label: "10 · 40px" },
  { cls: "w-12", label: "12 · 48px" },
  { cls: "w-16", label: "16 · 64px" },
  { cls: "w-20", label: "20 · 80px" },
  { cls: "w-24", label: "24 · 96px" },
];

const RADIUS = [
  { cls: "rounded-none", label: "none / 0px", note: "panels, tables, evidence blocks" },
  { cls: "rounded-sm", label: "sm / 2px", note: "disposition badges and stamps" },
  { cls: "rounded-md", label: "md / 4px", note: "buttons, inputs, toasts — the largest in the system" },
];

const DURATIONS = [
  "instant · 100ms · hover, focus, toggle",
  "fast · 160ms · button press, badge state change",
  "base · 220ms · panel open, dialog, toast",
  "slow · 360ms · page transitions, scroll reveals",
  "deliberate · 600ms · landing scroll storytelling only",
];

const EASINGS = [
  "ease-standard · cubic-bezier(0.4, 0, 0.2, 1)",
  "ease-out-snap · cubic-bezier(0.16, 1, 0.3, 1)",
  "ease-in-out-soft · cubic-bezier(0.65, 0, 0.35, 1)",
];

const SHADCN_SLOTS = [
  { cls: "bg-background text-foreground", label: "--background" },
  { cls: "bg-card text-card-foreground", label: "--card" },
  { cls: "bg-popover text-popover-foreground", label: "--popover" },
  { cls: "bg-primary text-primary-foreground", label: "--primary" },
  { cls: "bg-secondary text-secondary-foreground", label: "--secondary" },
  { cls: "bg-muted text-muted-foreground", label: "--muted" },
  { cls: "bg-accent text-accent-foreground", label: "--accent" },
  { cls: "bg-destructive text-destructive-foreground", label: "--destructive (REFUSE only)" },
];

const DISPOSITIONS: Disposition[] = ["AUTO_POST", "AUTO_SAMPLED", "ESCALATE", "REFUSE"];

function Swatch({ cls, name, hex }: { cls: string; name: string; hex: string }) {
  return (
    <div className="flex items-center gap-3 border border-border-hairline p-2">
      <span className={`h-10 w-10 shrink-0 border border-border-hairline ${cls}`} />
      <div className="min-w-0">
        <p className="truncate font-ui text-body-sm font-medium text-ink">{name}</p>
        <p className="tabular font-numeral text-numeral-sm text-ink-muted">{hex}</p>
      </div>
    </div>
  );
}

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border-hairline py-8 first:border-t-0 first:pt-0">
      <h2 className="font-ui text-caption font-semibold uppercase tracking-caption text-ink-muted">
        {title}
      </h2>
      {note ? <p className="mt-1 mb-5 font-ui text-body-sm text-ink-muted">{note}</p> : <div className="mb-5" />}
      {children}
    </section>
  );
}

export default function TokensPage() {
  const status = FIXTURE_CLOSE_STATUS;

  return (
    <div className="mx-auto w-full max-w-4xl flex-1 px-6 py-12">
      <header className="mb-10 flex items-start justify-between gap-4">
        <div>
          <p className="font-ui text-caption font-medium uppercase tracking-caption text-ink-muted">
            Design tokens · dev proof
          </p>
          <h1 className="mt-2 font-statement text-display-lg font-semibold tracking-display-lg text-ink">
            Tieout design system
          </h1>
          <p className="mt-3 max-w-xl font-ui text-body text-ink-muted">
            Every swatch, size, easing and primitive below comes from DESIGN.md.
            Flip the theme to verify the dark overrides land in the same token
            slots. Tokens are not to be edited here — edit DESIGN.md and re-copy.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <Section
        title="The five primitives · §8"
        note="Built once, in components/tieout/, because all three downstream surfaces need them and duplicating them three ways is how a design system dies."
      >
        <div className="space-y-8">
          <div>
            <p className="mb-3 font-ui text-body-sm font-medium text-ink">
              Disposition badge — all four dispositions (§1.1)
            </p>
            <div className="flex flex-wrap items-center gap-4">
              {DISPOSITIONS.map((d) => (
                <DispositionBadge key={d} disposition={d} />
              ))}
            </div>
            <p className="mt-3 max-w-2xl font-ui text-body-sm text-ink-muted">
              Epistemic status, not severity. T0 withholds visual weight entirely;
              T1 and T2 are outline tags with distinct glyphs; T3 is a stamp with
              the ledger&rsquo;s double rule, never an alert pill. Colour is never
              the sole carrier — each also has a glyph, a text label and a
              visually-hidden full sentence.
            </p>
          </div>

          <div>
            <p className="mb-3 font-ui text-body-sm font-medium text-ink">
              Money cell — right-aligned, tabular, signed (§3.3)
            </p>
            <div className="w-64 border border-border-hairline">
              {["412880.14", "-1284.63", "9.40", "0.00", "88120.55"].map((v, i) => (
                <div
                  key={v}
                  className={`border-b border-border-hairline px-3 py-2 last:border-b-0 ${i % 2 ? "bg-paper-inset" : ""}`}
                >
                  <MoneyCell value={v} />
                </div>
              ))}
            </div>
            <div className="mt-3 flex gap-8">
              <div>
                <p className="font-ui text-caption uppercase tracking-caption text-ink-muted">dense</p>
                <MoneyCell value="-1284.63" density="dense" />
              </div>
              <div>
                <p className="font-ui text-caption uppercase tracking-caption text-ink-muted">accounting parens</p>
                <MoneyCell value="-1284.63" accountingParens />
              </div>
            </div>
          </div>

          <div>
            <p className="mb-3 font-ui text-body-sm font-medium text-ink">
              Stat tile — never a rate without its counterweight (SPEC §12)
            </p>
            <div className="grid gap-3 sm:grid-cols-3">
              <StatTile
                label="Straight-through rate"
                value={`${(status.straightThroughRate * 100).toFixed(1)}%`}
                context={`${status.workItems.toLocaleString("en-US")} work items`}
              />
              <StatTile
                label="Fabricated matches"
                value={String(status.fabricatedMatches)}
                context="Posted with no ground-truth counterpart"
              />
              <StatTile
                label="Blocking total"
                value={formatMoney(status.blockingTotal)}
                context={`Performance materiality ${formatMoney(status.performanceMateriality)}`}
              />
            </div>
          </div>

          <div>
            <p className="mb-3 font-ui text-body-sm font-medium text-ink">
              Aging buckets — dollar total is the bar, count is the label (§9.3)
            </p>
            <AgingBuckets buckets={FIXTURE_REVIEW_QUEUE.aging} />
          </div>

          <div>
            <p className="mb-3 font-ui text-body-sm font-medium text-ink">
              Close banner — both states (§8)
            </p>
            <div className="space-y-4">
              <CloseBanner state="REFUSED" period={status.period} detail={status.refusalReason} />
              <CloseBanner
                state="CLOSED"
                period="2025-12"
                detail="Certified 04 Jan 2026 by controller@reconriver.example. No open refused items."
              />
            </div>
            <p className="mt-3 max-w-2xl font-ui text-body-sm text-ink-muted">
              CLOSED is deliberately calm. Closing successfully is the expected,
              unremarkable outcome — §1.1&rsquo;s T0 logic applied to the period.
            </p>
          </div>

          <p className="border-t border-border-hairline pt-4 font-ui text-caption uppercase tracking-caption text-ink-muted">
            {FIXTURE_NOTICE}
          </p>
        </div>
      </Section>

      <Section title="Light surface · §12.1" note="Swatches follow the active theme; hex labels show the light values.">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {LIGHT_SURFACE.map((c) => (
            <Swatch key={c.name} {...c} />
          ))}
        </div>
      </Section>

      <Section title="Disposition colours · §12.1">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {DISPOSITION_COLOURS.map((c) => (
            <Swatch key={c.name} {...c} />
          ))}
        </div>
      </Section>

      <Section title="Sequential ochre ramp · §9.2" note="Aging bars and the per-class precision table. Darkest = highest.">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {OCHRE_RAMP.map((c) => (
            <Swatch key={c.name} {...c} />
          ))}
        </div>
      </Section>

      <Section title="Type scale · §3.2 · three families">
        <div className="space-y-5">
          {TYPE_SCALE.map((t) => (
            <div key={t.label} className="flex flex-col gap-1">
              <p className="font-numeral text-numeral-sm text-ink-muted">{t.label}</p>
              <p className={`${t.cls} text-ink`}>{t.sample}</p>
            </div>
          ))}
        </div>
        <div className="mt-8 space-y-4 border-t border-border-hairline pt-6">
          {NUMERAL_SCALE.map((t) => (
            <div key={t.label} className="flex flex-col gap-0.5">
              <p className="font-numeral text-numeral-sm text-ink-muted">{t.label}</p>
              <p className={`tabular font-numeral ${t.cls} text-ink`}>{t.sample}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Spacing · §5" note="The standard 4px-base Tailwind scale, reused rather than reinvented.">
        <div className="space-y-1.5">
          {SPACING.map((s) => (
            <div key={s.cls} className="flex items-center gap-3">
              <span className={`h-3 shrink-0 bg-ink ${s.cls}`} />
              <span className="tabular font-numeral text-numeral-sm text-ink-muted">{s.label}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Radius · §6" note="Mostly square. No radius-lg or -full anywhere: a pill badge is on the ban list.">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {RADIUS.map((r) => (
            <div key={r.label} className="flex items-center gap-4">
              <span className={`h-12 w-12 shrink-0 ${r.cls} border border-border-interactive bg-paper-inset`} />
              <div>
                <p className="font-ui text-body-sm font-medium text-ink">{r.label}</p>
                <p className="font-ui text-caption text-ink-muted">{r.note}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Motion · §7" note="Durations and easings also live in lib/motion.ts so GSAP timelines and CSS transitions cannot drift apart. prefers-reduced-motion is gated once, at the root.">
        <ul className="space-y-1 font-numeral text-numeral-sm text-ink-muted">
          {DURATIONS.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
        <ul className="mt-4 space-y-1 font-numeral text-numeral-sm text-ink-muted">
          {EASINGS.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
        <div className="mt-6">
          <p className="mb-2 font-numeral text-numeral-sm text-ink-muted">
            shadow-overlay — the one shadow in the system (dialog and toast only)
          </p>
          <div className="h-16 w-40 rounded-md border border-border-hairline bg-background shadow-overlay" />
        </div>
      </Section>

      <Section
        title="shadcn/ui slots · §12.2"
        note="--destructive is the only shadcn slot reused for the REFUSE stamp — never for generic form errors."
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {SHADCN_SLOTS.map((s) => (
            <div key={s.label} className="overflow-hidden border border-border-hairline">
              <div className={`flex h-14 items-center justify-center text-center font-numeral text-numeral-sm ${s.cls}`}>
                Aa
              </div>
              <p className="border-t border-border-hairline bg-background px-2 py-1.5 font-numeral text-numeral-sm text-ink-muted">
                {s.label}
              </p>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
