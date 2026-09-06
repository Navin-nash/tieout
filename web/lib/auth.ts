// Better Auth server instance (ADR-002 §Decision).
//
// Tables are created with `npm run db:migrate` — run once, and again after
// any plugin change (see web/README.md "Database").
//
// Env (web/.env, gitignored — see .env.example):
//   BETTER_AUTH_SECRET   min 32 chars, high entropy
//   BETTER_AUTH_URL      base URL of this app
//   TIEOUT_AUTH_DB       optional override for the SQLite path (default ./data/tieout-auth.db)
import { betterAuth } from "better-auth";
import Database from "better-sqlite3";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";

// The SQLite file lives under web/data/ (gitignored). better-sqlite3 will not
// create the directory, so guarantee it exists before opening the database.
const dbPath = process.env.TIEOUT_AUTH_DB ?? "./data/tieout-auth.db";
mkdirSync(dirname(dbPath), { recursive: true });

export const auth = betterAuth({
  appName: "Tieout",
  database: new Database(dbPath),
  emailAndPassword: {
    enabled: true,
    // Email verification is intentionally disabled for the hackathon window:
    // sendVerificationEmail is not defined, which keeps sign-ups open. Revisit
    // before any public deployment.
  },
});