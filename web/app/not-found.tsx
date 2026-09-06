import Link from "next/link";

// Branded 404 (root-level). Renders inside the root layout, so tokens and
// fonts apply. Shown at `/` until the landing-page worker lands app/(marketing).
export default function NotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-24 text-center">
      <p className="font-numeral text-numeral-lg tracking-caption text-ink-muted">404</p>
      <h1 className="font-statement text-display-lg tracking-display-lg text-ink">
        Nothing to close here.
      </h1>
      <p className="max-w-md font-ui text-body text-ink-muted">
        This page is not on any ledger. Head back to{" "}
        <Link href="/" className="font-medium text-ink underline underline-offset-4 hover:text-focus">
          Tieout
        </Link>
        .
      </p>
    </div>
  );
}