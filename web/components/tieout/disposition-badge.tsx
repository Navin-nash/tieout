import { Clock, Target } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The four dispositions of the refusal gate (SPEC §6). There is no fifth.
 */
export type Disposition = "AUTO_POST" | "AUTO_SAMPLED" | "ESCALATE" | "REFUSE";

/**
 * DESIGN.md §1.1 — the disposition scale encodes **epistemic status, not
 * severity**. Explicitly not a traffic light: a REFUSE is the system's correct
 * and most valuable output, so it is stamped like a ledger entry, not alarmed
 * like a form error.
 *
 * - T0 AUTO_POST   no colour, no chrome, no glyph. Settled things are
 *                  unremarkable, and unremarkable is achieved by withholding
 *                  visual weight rather than by adding a green tick.
 * - T1 AUTO_SAMPLED  slate-blue outline tag + ring/target glyph — the register
 *                  of a lab control sample, which is literally what it is.
 * - T2 ESCALATE    ochre outline tag + clock glyph, never an exclamation mark.
 *                  Deliberately the calmest coloured state: escalation is
 *                  normal, expected behaviour.
 * - T3 REFUSE      oxblood stamp: small-caps, bold, double rule top and bottom
 *                  (the ledger's own mark for a closed total). Never a filled
 *                  alert pill, never role="alert".
 *
 * DESIGN.md §11 — colour is never the sole carrier: every state pairs colour
 * with a glyph *and* a text label, plus a visually-hidden full sentence.
 */
const SR_SENTENCE: Record<Disposition, string> = {
  AUTO_POST: "Disposition: Auto-posted — settled, no review required",
  AUTO_SAMPLED: "Disposition: Auto-posted and sampled — settled, independently checked for control evidence",
  ESCALATE: "Disposition: Escalated — awaiting human judgement, does not block the close",
  REFUSE: "Disposition: Refused — blocks period close, no override exists",
};

const LABEL: Record<Disposition, string> = {
  AUTO_POST: "AUTO_POST",
  AUTO_SAMPLED: "AUTO_SAMPLED",
  ESCALATE: "ESCALATE",
  REFUSE: "REFUSE",
};

export type DispositionBadgeProps = {
  disposition: Disposition;
  className?: string;
};

export function DispositionBadge({ disposition, className }: DispositionBadgeProps) {
  const sr = <span className="sr-only">{SR_SENTENCE[disposition]}</span>;

  // T0 — bare text. No badge chrome at all, by design.
  if (disposition === "AUTO_POST") {
    return (
      <span
        data-disposition="AUTO_POST"
        className={cn(
          "inline-flex items-center font-ui text-caption font-medium uppercase tracking-caption text-ink-muted",
          className,
        )}
      >
        {sr}
        <span aria-hidden>{LABEL.AUTO_POST}</span>
      </span>
    );
  }

  // T3 — the stamp. `border-double` at 4px renders CSS's 1px / 2px gap / 1px,
  // which is precisely the ledger double rule DESIGN.md §1.1 asks for.
  if (disposition === "REFUSE") {
    return (
      <span
        data-disposition="REFUSE"
        className={cn(
          "inline-flex items-center rounded-sm border-y-4 border-double border-refuse bg-refuse-fill px-2 py-0.5",
          "font-ui text-caption font-semibold uppercase tracking-caption text-refuse",
          className,
        )}
      >
        {sr}
        <span aria-hidden>{LABEL.REFUSE}</span>
      </span>
    );
  }

  const sampled = disposition === "AUTO_SAMPLED";
  const Glyph = sampled ? Target : Clock;

  return (
    <span
      data-disposition={disposition}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5",
        "font-ui text-caption font-medium uppercase tracking-caption",
        sampled
          ? "border-sampled/40 bg-sampled-fill text-sampled"
          : "border-escalate/40 bg-escalate-fill text-escalate",
        className,
      )}
    >
      {sr}
      <Glyph aria-hidden className="size-3 shrink-0" strokeWidth={2} />
      <span aria-hidden>{LABEL[disposition]}</span>
    </span>
  );
}
