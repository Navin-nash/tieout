import { NextResponse, type NextRequest } from "next/server";
import { getSessionCookie } from "better-auth/cookies";

// Next.js 16 renamed Middleware to Proxy; the file convention is `proxy.ts` at
// the project root with a named `proxy` export.
//
// This is an **optimistic** check: it looks for the session cookie and nothing
// more, because Next.js and Better Auth both warn against doing session or
// database work here. It exists so an unauthenticated request to a protected
// route redirects instead of rendering a shell and then fetching data.
//
// It is not the authorisation boundary. Pages and route handlers under (app)
// call `getSession()` from lib/session.ts for the authoritative check, and the
// engine's own invariants are enforced in Python regardless of what any web
// request claims.

/** The `(app)` route group's public paths (SPEC section 12's three screens, plus the assistant). */
const PROTECTED = ["/close", "/queue", "/score", "/assistant"];

const SIGN_IN = "/sign-in";

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = Boolean(getSessionCookie(request));

  if (!hasSession && PROTECTED.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    const url = new URL(SIGN_IN, request.url);
    // Preserve where they were going so sign-in can return them to it.
    url.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(url);
  }

  if (hasSession && pathname === SIGN_IN) {
    return NextResponse.redirect(new URL("/close", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/close/:path*",
    "/queue/:path*",
    "/score/:path*",
    "/assistant/:path*",
    "/sign-in",
  ],
};
