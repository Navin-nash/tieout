import Link from "next/link";

/**
 * Public shell for the (marketing) route group - layout only. The landing page
 * itself belongs to the landing-page worker.
 *
 * DESIGN.md section 5: marketing shell is max-width 75rem. A narrower 45rem
 * reading column for evidence prose is applied per-section by that worker, not
 * here, because only some sections are prose.
 */
export default function MarketingLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="border-b border-border-hairline">
        <div className="mx-auto flex h-14 w-full max-w-[75rem] items-center justify-between px-6">
          <Link href="/" className="font-statement text-heading-sm font-semibold text-ink">
            Tieout
          </Link>
          <Link
            href="/sign-in"
            className="rounded-md border border-border-interactive px-3 py-1.5 font-ui text-body-sm font-medium text-ink transition-colors duration-fast ease-standard hover:bg-paper-inset"
          >
            Sign in
          </Link>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[75rem] flex-1 px-6">{children}</main>
      <footer className="border-t border-border-hairline">
        <div className="mx-auto w-full max-w-[75rem] px-6 py-6 font-ui text-caption uppercase tracking-caption text-ink-muted">
          Tieout - reconciliation that refuses to fake it
        </div>
      </footer>
    </div>
  );
}
