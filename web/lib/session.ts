import { headers } from "next/headers";

import { auth } from "@/lib/auth";

/**
 * The authoritative server-side session read.
 *
 * `proxy.ts` only does an optimistic cookie check - Next.js and Better Auth
 * both say so explicitly, and a cookie's presence is not a session. Any page or
 * route handler that acts on identity calls this instead.
 */
export async function getSession() {
  return auth.api.getSession({ headers: await headers() });
}

/**
 * The acting human's identity, in the form the API expects for `--as`
 * (SPEC section 12) and the audit event's actor field (SPEC section 8).
 *
 * Returns `null` when there is no session. Callers must treat that as "cannot
 * act" - never substitute a default actor. An audit trail whose actor is a
 * fallback value is worse than no audit trail, because it looks like evidence.
 */
export async function getActor(): Promise<string | null> {
  const session = await getSession();
  return session?.user?.email ?? null;
}
