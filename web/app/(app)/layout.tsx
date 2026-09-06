import { AppNav } from "@/components/app-nav";

/**
 * Authenticated shell for the (app) route group - layout and navigation only.
 * The three screens (close, queue, score) belong to the dashboard-ui worker and
 * the assistant to agent-ui; nothing in here renders page content.
 *
 * DESIGN.md section 5: app surfaces are fluid to max-width 90rem with no narrow
 * reading column - these are data surfaces, not prose surfaces.
 *
 * proxy.ts redirects unauthenticated requests before this renders. Pages that
 * act on identity still read the session authoritatively via lib/session.ts.
 */
export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-full flex-1 flex-col">
      <AppNav />
      <main className="mx-auto w-full max-w-[90rem] flex-1 px-6 py-8">{children}</main>
    </div>
  );
}
