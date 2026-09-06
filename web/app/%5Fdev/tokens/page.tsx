// Dev-only proof page: every utility class below is generated from the
// DESIGN.md §12 tokens in app/globals.css. The swatches render the active
// theme (flip with the toggle to verify the dark overrides). Delete this
// directory before launch.
//
// The folder is named `%5Fdev` because Next.js private folders (`_name`) are
// excluded from routing entirely; `%5F` is the documented way to create an
// underscore URL segment, so this page lives at /_dev/tokens.
import { ThemeToggle } from "./theme-toggle";

const LIGHT_SURFACE = [
  { name: "paper", hex: "#FAF9F6" },
  { name: "paper-inset", hex: "#F2F0EB" },
  { name: "ink", hex: "#1A1613" },
  { name: "ink-muted", hex: "#5B5650" },
  { name: "border-hairline", hex: "#D8D4CC" },
  { name: "border-interactive", hex: "#8A8375" },
  { name: "focus", hex: "#1B5FB0" },
];

const DISPOSITION = [
  { name: "sampled", hex: "#3B5166" },
  { name: "escalate", hex: "#7A5B12" },
  { name: "refuse", hex: "#7A1220" },
];

const DISPOSITION_FILLS = [
  { name: "sampled-fill", hex: "#E7ECEF" },
  { name: "escalate-fill", hex: "#F5E9C9" },
  { name: "refuse-fill", hex: "#F6E3E1" },
];

const TYPE_SCALE = [
  { cls: "text-display-2xl tracking-display-2xl", label: "display-2xl / 56 · -0.015em", sample: "Statement Serif" },
  { cls: "text-display-xl tracking-display-xl", label: "display-xl / 40 · -0.01em", sample: "The books must balance." },
  { cls: "text-display-lg tracking-display-lg", label: "display-lg / 32 · -0.01em", sample: "Nothing to close here." },
  { cls: "text-heading-md", label: "heading-md / 24", sample: "Review queue" },
  { cls: "text-heading-sm", label: "heading-sm / 20", sample: "Close status" },
  { cls: "text-body-lg", label: "body-lg / 18", sample: "Reconciliation that refuses to fake it." },
  { cls: "text-body", label: "body / 16", sample: "Every entry carries lineage, identity and support." },
  { cls: "text-body-sm", label: "body-sm / 14", sample: "Muted supporting copy for tables and captions." },
  { cls: "text-caption tracking-caption", label: "caption / 12 · 0.04em", sample: "CAPTION · POSTED 05 SEP 2026" },
];

const NUMERAL_SCALE = [
  { cls: "text-numeral-lg", label: "numeral-lg / 32", sample: "$658,000.00" },
  { cls: "text-numeral-md tabular", label: "numeral-md / 16 · tabular", sample: "1,153 items · 98.2%" },
  { cls: "text-numeral-sm tabular", label: "numeral-sm / 13 · tabular", sample: "0.00 · $9.40" },
];

const RADIUS = [
  { cls: "rounded-none", label: "none / 0px", note: "cards, panels, buttons" },
  { cls: "rounded-sm", label: "sm / 2px", note: "chips, small fills" },
  { cls: "rounded-md", label: "md / 4px", note: "largest radius in the system" },
];

const DURATIONS = ["instant 100ms", "fast 160ms", "base 220ms", "slow 360ms", "deliberate 600ms"];

const EASINGS = [
  "ease-standard · cubic-bezier(0.4, 0, 0.2, 1)",
  "ease-out-snap · cubic-bezier(0.16, 1, 0.3, 1)",
  "ease-in-out-soft · cubic-bezier(0.65, 0, 0.35, 1)",
];

const SHADCN_SLOTS = [
  { cls: "bg-background", label: "--background" },
  { cls: "bg-card", label: "--card" },
  { cls: "bg-popover", label: "--popover" },
  { cls: "bg-primary text-primary-foreground", label: "--primary" },
  { cls: "bg-secondary", label: "--secondary" },
  { cls: "bg-muted", label: "--muted" },
  { cls: "bg-accent text-accent-foreground", label: "--accent" },
  { cls: "bg-destructive text-destructive-foreground", label: "--destructive (REFUSE only)" },
];

function Swatch({ name, hex }: { name: string; hex: string }) {
  return (
    <div className="flex items-center gap-3 rounded-sm border border-border-hairline p-2">
      <span className={`h-10 w-10 shrink-0 rounded-sm border border-border-hairline bg-${name}`} />
      <div className="min-w-0">
        <p className="truncate font-ui text-body-sm font-medium text-ink">{name}</p>
        <p className="font-numeral text-numeral-sm text-ink-muted">{hex}</p>
      </div>
    </div>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className="border-t border-border-hairline py-8 first:border-t-0 first:pt-0"
    >
      <h2 className="mb-5 font-ui text-caption font-semibold uppercase tracking-caption text-ink-muted">
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function TokensPage() {
  return (
    <div className="mx-auto w-full max-w-4xl flex-1 px-6 py-12">
      <header className="mb-10 flex items-start justify-between gap-4">
        <div>
          <p className="font-numeral text-caption uppercase tracking-caption text-ink-muted">
            Design tokens · dev proof
          </p>
          <h1 className="mt-2 font-statement text-display-lg tracking-display-lg text-ink">
            Tieout design system
          </h1>
          <p className="mt-3 max-w-xl font-ui text-body text-ink-muted">
            Every swatch, size and motion value below is a Tailwind utility
            generated from DESIGN.md §12. Flip the theme to verify the dark
            overrides. <span className="text-ink">This page ships nowhere — delete before launch.</span>
          </p>
        </div>
        <ThemeToggle />
      </header>

      <Section id="surface" title="Light surface · §12.1">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {LIGHT_SURFACE.map((c) => (
            <Swatch key={c.name} name={c.name} hex={c.hex} />
          ))}
        </div>
        <p className="mt-4 font-ui text-caption text-ink-muted">
          Swatches follow the active theme — utilities resolve var(--color-*)
          which the .dark overrides rebind. Hex labels show the light values.
        </p>
      </Section>

      <Section id="disposition" title="Disposition colours · §12.1">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {DISPOSITION.map((c) => (
            <Swatch key={c.name} name={c.name} hex={c.hex} />
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {DISPOSITION_FILLS.map((c) => (
            <Swatch key={c.name} name={c.name} hex={c.hex} />
          ))}
        </div>
      </Section>

      <Section id="type" title="Type scale · §3.2 · three families">
        <div className="space-y-4">
          {TYPE_SCALE.map((t) => (
            <div key={t.label} className="flex flex-col gap-1">
              <p className="font-numeral text-numeral-sm text-ink-muted">{t.label}</p>
              <p className={`font-statement ${t.cls} text-ink`}>{t.sample}</p>
            </div>
          ))}
        </div>
        <div className="mt-8 space-y-3 border-t border-border-hairline pt-6">
          {NUMERAL_SCALE.map((t) => (
            <div key={t.label} className="flex flex-col gap-0.5">
              <p className="font-numeral text-numeral-sm text-ink-muted">{t.label}</p>
              <p className={`font-numeral ${t.cls} text-ink`}>{t.sample}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section id="radius" title="Radius · §12.1">
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

      <Section id="motion" title="Motion · §12.1">
        <div className="flex flex-wrap gap-2">
          {DURATIONS.map((d) => (
            <span
              key={d}
              className={`rounded-sm border border-border-hairline bg-paper-inset px-3 py-1.5 font-numeral text-numeral-sm text-ink ${
                d.startsWith("deliberate") ? "duration-deliberate" : d.startsWith("slow") ? "duration-slow" : d.startsWith("base") ? "duration-base" : d.startsWith("fast") ? "duration-fast" : "duration-instant"
              }`}
            >
              {d}
            </span>
          ))}
        </div>
        <ul className="mt-4 space-y-1 font-numeral text-numeral-sm text-ink-muted">
          {EASINGS.map((e) => (
            <li key={e}>— {e}</li>
          ))}
        </ul>
        <div className="mt-6">
          <p className="mb-2 font-numeral text-numeral-sm text-ink-muted">shadow-overlay</p>
          <div className="h-16 w-40 rounded-sm border border-border-hairline bg-background shadow-overlay" />
        </div>
      </Section>

      <Section id="shadcn" title="shadcn/ui slots · §12.2">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {SHADCN_SLOTS.map((s) => (
            <div key={s.label} className="overflow-hidden rounded-sm border border-border-hairline">
              <div className={`flex h-14 items-center justify-center text-center font-numeral text-numeral-sm ${s.cls}`}>
                Aa
              </div>
              <p className="border-t border-border-hairline bg-background px-2 py-1.5 font-numeral text-numeral-sm text-ink-muted">
                {s.label}
              </p>
            </div>
          ))}
        </div>
        <p className="mt-4 font-ui text-caption text-ink-muted">
          --destructive is the only shadcn slot reused for the REFUSE stamp — never for generic form errors (globals.css).
        </p>
      </Section>
    </div>
  );
}