# Tieout — web app

Next.js 16 (App Router) · TypeScript · Tailwind CSS v4 · shadcn/ui · GSAP · Better Auth

The frontend half of [Tieout](../README.md) — an audit-grade reconciliation
product whose money shot (`tieout close` → `CLOSE REFUSED`) lives entirely in
the CLI; this app renders the landing page, the three dashboard screens and the
agent UI (see `docs/PLAN.md` — screens land in later waves).

## Stack decisions (ADR-002)

- **Next.js App Router** + shadcn/ui for the three React-shaped surfaces.
- **GSAP + `useGSAP`** for scroll-driven landing motion — register plugins per
  DESIGN.md §7 and clean up in `useGSAP`; transform/opacity only.
- **Better Auth** for authentication (email/password).
- Design tokens come **verbatim from `DESIGN.md` §12** into `app/globals.css`.
  When DESIGN.md changes, update that file — do not invent local tokens.
  The `/tokens` proof page (`/_dev/tokens`) renders every token.

## Getting started

```bash
npm install
cp .env.example .env        # then fill in BETTER_AUTH_SECRET (see below)
npm run db:migrate          # create the auth tables (run once; re-run after plugin changes)
npm run dev                 # http://localhost:3000
```

Generate the auth secret:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

`BETTER_AUTH_SECRET` and `BETTER_AUTH_URL` go in `web/.env` (gitignored — never
commit them). The auth SQLite database defaults to `web/data/tieout-auth.db`
(gitignored); override with `TIEOUT_AUTH_DB`.

## Verification

```bash
npm run build       # production build (type-checks routes)
npm run lint        # eslint
npm run db:migrate  # apply/refresh Better Auth schema
```

Smoke-test auth from the shell — `GET /api/auth/ok` returns `{"status":"ok"}`
and a sign-up round-trip works via `POST /api/auth/sign-up/email`.

## Layout

| Path | Purpose |
|---|---|
| `app/(marketing)/` | Landing page — **owned by the landing-page worker (Wave 3)** |
| `app/(app)/` | Close status · review queue · scoreboard — **dashboard-ui worker (Wave 3)** |
| `app/(app)/assistant/` | Agent UI — **agent-ui worker (Wave 3)** |
| `app/%5Fdev/tokens/` | Dev-only token palette at `/_dev/tokens`. `%5F` is Next's documented escape for an underscore URL segment — a plain `_dev` folder would be excluded from routing. **Delete before launch.** |
| `app/api/auth/[...all]/` | Better Auth catch-all route handler |
| `lib/auth.ts` | Better Auth server instance (better-sqlite3) |
| `lib/auth-client.ts` | Better Auth React client (`useSession`, `signIn`, `signUp`, `signOut`) |
| `lib/fonts.ts` | DESIGN.md §3.1 — Source Serif 4, IBM Plex Sans, IBM Plex Mono (next/font) |
| `components/ui/` | shadcn/ui components |

## Notes

- Three font families, exposed as `font-statement`, `font-ui`, `font-numeral`
  utilities; inline money figures in serif prose use the `tabular` utility
  (DESIGN.md §3.3).
- Light is the primary theme (DESIGN.md §4); a small inline script in
  `app/layout.tsx` applies the persisted/OS theme before first paint to avoid a
  flash, and `next-themes` handles the rest.
- `--destructive` is reserved for the REFUSE stamp (T3) — never generic form
  errors.