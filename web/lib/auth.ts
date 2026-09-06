// Better Auth server instance (ADR-002; multi-tenancy per ADR-003).
//
// Scope, deliberately narrow: this establishes **who the logged-in human is**
// and nothing else. There is no role model and no permissions system here.
// SPEC section 8's identity requirement is narrow - a named human reviewer,
// distinct from the initiator - and four-eyes is enforced server-side in
// Python by the audit-chain layer. Adding an authorisation model in the web
// tier would be a second, weaker source of truth for the same rule.
//
// Tables are created with `npm run db:migrate` - run once, and again after any
// plugin change (see web/README.md "Database").
//
// Env (web/.env, gitignored - see .env.example):
//   BETTER_AUTH_SECRET   min 32 chars, high entropy, generated. Never committed.
//   BETTER_AUTH_URL      base URL of this app; also the default trusted origin
//   TIEOUT_AUTH_DB       optional override for the SQLite path
import { betterAuth } from "better-auth";
import { organization } from "better-auth/plugins";
import Database from "better-sqlite3";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";

// SQLite is the local store for the hackathon window (ADR-003 moves the domain
// read model to Postgres; auth is small and separate, so it stays here). The
// file lives under web/data/, which is gitignored. better-sqlite3 will not
// create the directory, so guarantee it exists before opening the database.
const dbPath = process.env.TIEOUT_AUTH_DB ?? "./data/tieout-auth.db";
mkdirSync(dirname(dbPath), { recursive: true });

const baseURL = process.env.BETTER_AUTH_URL ?? "http://localhost:3000";
const isProduction = process.env.NODE_ENV === "production";

/**
 * Explicit allow-list, never a wildcard. Better Auth rejects requests whose
 * Origin is not listed, which is the CSRF boundary for the auth endpoints.
 * Extra origins (a preview deployment, say) go in `BETTER_AUTH_TRUSTED_ORIGINS`
 * as a comma-separated list rather than being hardcoded here.
 */
const trustedOrigins = [
  baseURL,
  ...(process.env.BETTER_AUTH_TRUSTED_ORIGINS ?? "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean),
];

export const auth = betterAuth({
  appName: "Tieout",
  baseURL,
  // Read from the environment, never inlined. Better Auth throws at request
  // time if this is unset, which is the intended fail-loud behaviour: an auth
  // system running on a default secret should not serve a single request.
  secret: process.env.BETTER_AUTH_SECRET,
  database: new Database(dbPath),
  trustedOrigins,

  emailAndPassword: {
    enabled: true,
    // Longer than Better Auth's 8-character default. This is a system of
    // record for financial close decisions; the cost of the extra characters
    // is nil and the identity on an audit event is only as good as the login.
    minPasswordLength: 12,
    // Email verification is intentionally off for the hackathon window - no
    // mail transport is configured, and a sign-up that silently fails to send
    // is worse than one that succeeds. Turn it on before any public deployment.
    requireEmailVerification: false,
  },

  session: {
    expiresIn: 60 * 60 * 24 * 7,
    updateAge: 60 * 60 * 24,
    cookieCache: {
      // Lets `proxy.ts` do an optimistic redirect without a database read.
      // Short-lived on purpose: the authoritative check is still `auth.api
      // .getSession` inside the page or route handler.
      enabled: true,
      maxAge: 60 * 5,
    },
  },

  // Enabled in development too. The default disables rate limiting outside
  // production, which means the limits are never exercised until they matter.
  rateLimit: {
    enabled: true,
    window: 60,
    max: 100,
    customRules: {
      // Credential endpoints get a much tighter budget - these are the ones
      // worth brute-forcing.
      "/sign-in/email": { window: 60, max: 5 },
      "/sign-up/email": { window: 60, max: 5 },
      "/forget-password": { window: 60, max: 3 },
    },
  },

  advanced: {
    // Secure-flag driven by environment: forcing it on over plain http in dev
    // means the browser drops the cookie and nothing works.
    useSecureCookies: isProduction,
    defaultCookieAttributes: {
      httpOnly: true,
      sameSite: "lax",
      secure: isProduction,
      path: "/",
    },
  },

  plugins: [
    // ADR-003: Tieout is multi-tenant. Every domain row carries an org, and the
    // org is derived server-side from the session - never from a request body,
    // path parameter or header the client controls. This plugin supplies the
    // orgs and memberships only; the org-scoping of domain queries is the
    // platform-tenancy worker's, on the Python side.
    organization(),
  ],
});

export type Session = typeof auth.$Infer.Session;
