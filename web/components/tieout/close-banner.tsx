import { cn } from "@/lib/utils";

/**
 * DESIGN.md §8 "CLOSE REFUSED / CLOSED banner" — the single largest, most
 * unambiguous element on the close status screen, and SPEC §10's money shot.
 *
 * REFUSED gets the stamp: `display-lg`, small-caps, oxblood on the pale wash,
 * double rule top and bottom. CLOSED is deliberately calm — plain ink on
 * `paper-inset`, no colour, no celebration. Closing successfully is the
 * expected, unremarkable outcome, which is §1.1's T0 logic applied to the
 * period as a whole.
 *
 * `role="status"` rather than `role="alert"`: a refusal is an authoritative
 * determination, not an error, and DESIGN.md §1.1 is explicit that
 * form-validation alert styling must not be borrowed for it.
 */
export type CloseState = "REFUSED" | "CLOSED";

export type CloseBannerProps = {
  state: CloseState;
  /** e.g. "2026-01". */
  period: string;
  /** One line beneath the stamp: the reason, or the certification detail. */
  detail?: string;
  className?: string;
};

export function CloseBanner({ state, period, detail, className }: CloseBannerProps) {
  const refused = state === "REFUSED";

  return (
    <section
      data-slot="close-banner"
      data-state={state}
      role="status"
      aria-label={
        refused
          ? `Close refused for period ${period}. Open refused items block this period; no override exists.`
          : `Period ${period} closed.`
      }
      className={cn(
        "w-full px-6 py-6",
        refused
          ? "border-y-4 border-double border-refuse bg-refuse-fill"
          : "border-y border-border-hairline bg-paper-inset",
        className,
      )}
    >
      <p
        aria-hidden
        className={cn(
          "font-ui text-caption font-medium uppercase tracking-caption",
          refused ? "text-refuse" : "text-ink-muted",
        )}
      >
        Period {period}
      </p>
      <p
        aria-hidden
        className={cn(
          "mt-1 font-ui text-display-lg font-semibold uppercase tracking-caption",
          refused ? "text-refuse" : "text-ink",
        )}
      >
        {refused ? "Close refused" : "Closed"}
      </p>
      {detail ? (
        <p
          aria-hidden
          className={cn(
            "mt-2 max-w-3xl font-ui text-body",
            refused ? "text-refuse" : "text-ink-muted",
          )}
        >
          {detail}
        </p>
      ) : null}
    </section>
  );
}
