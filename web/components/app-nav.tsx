"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { cn } from "@/lib/utils";
import { signOut, useSession } from "@/lib/auth-client";

// SPEC section 12's three screens, plus the assistant surface (ADR-002).
const LINKS = [
  { href: "/close", label: "Close" },
  { href: "/queue", label: "Queue" },
  { href: "/score", label: "Scoreboard" },
  { href: "/assistant", label: "Assistant" },
] as const;

/**
 * Navigation only - no page content. DESIGN.md section 6: a hairline rule, not
 * a shadow. The current item is marked by an ink underline and `aria-current`,
 * so the state is not carried by colour alone (section 11).
 *
 * The signed-in identity is displayed because it is the identity that will be
 * written onto every review decision (SPEC section 8). A controller should
 * always be able to see who the system thinks they are before they act.
 */
export function AppNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = useSession();

  return (
    <header className="border-b border-border-hairline">
      <div className="mx-auto flex h-14 w-full max-w-[90rem] items-center gap-8 px-6">
        <Link
          href="/close"
          className="font-statement text-heading-sm font-semibold text-ink"
        >
          Tieout
        </Link>

        <nav aria-label="Primary" className="flex items-center gap-6">
          {LINKS.map((link) => {
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "-mb-px border-b-2 py-4 font-ui text-body-sm transition-colors duration-instant ease-standard",
                  active
                    ? "border-ink font-medium text-ink"
                    : "border-transparent text-ink-muted hover:text-ink",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-4">
          {session?.user?.email ? (
            <>
              <span className="font-numeral text-numeral-sm text-ink-muted">
                {session.user.email}
              </span>
              <button
                type="button"
                onClick={() =>
                  signOut({ fetchOptions: { onSuccess: () => router.push("/sign-in") } })
                }
                className="rounded-md border border-border-interactive px-3 py-1.5 font-ui text-body-sm font-medium text-ink transition-colors duration-fast ease-standard hover:bg-paper-inset"
              >
                Sign out
              </button>
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}
