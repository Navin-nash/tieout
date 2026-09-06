# Tieout — web app

Next.js 16 (App Router) · TypeScript · Tailwind CSS v4 · shadcn/ui · GSAP · Better Auth

The frontend half of [Tieout](../README.md) — an audit-grade reconciliation
product. Per ADR-003 the web app leads the demo; the CLI (`tieout close` →
`CLOSE REFUSED`) remains a fully working secondary interface. This app renders
the landing page, the three dashboard screens and the agent UI (see
`docs/PLAN.md` — screens land in Wave 3).

## Stack decisions (ADR-002, ADR-003)

- **Next.js App Router** + shadcn/ui for the three React-shaped surfaces.
- **GSAP + `useGSAP`** for scroll-driven landing motion — register plugins per
  DESIGN.md §7 and clean up in `useGSAP`; transform/opacity only. Duration and
  easing values live in both `app/globals.css` (CSS custom properties) and
  `lib/motion.ts` (the same numbers as TS constants) so a CSS transition and a
  GSAP timeline can never drift apart.
- **Better Auth**, email/password, with the `organization` plugin for
  ADR-003's multi-tenancy. Auth establishes *who the logged-in human is*; it
  does not implement a role or permissions model — SPEC §8's four-eyes
  requirement is enforced server-side in Python by the `audit-chain` layer.
- Design tokens come **verbatim from `DESIGN.md` §12** into `app/globals.css`.
  When DESIGN.md changes, update that file — do not invent local tokens. The
  `/_dev/tokens` proof page renders every token and all five primitives.

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
commit them; `.env.example` documents the shape with empty values). The auth
SQLite database defaults to `web/data/tieout-auth.db` (gitignored); override
with `TIEOUT_AUTH_DB`.

## Environment variables

| Variable | Purpose |
|---|---|
| `BETTER_AUTH_SECRET` | High-entropy signing secret, min 32 chars. Generated, never hardcoded, never committed. |
| `BETTER_AUTH_URL` | Base URL of this app; also the default trusted origin. |
| `BETTER_AUTH_TRUSTED_ORIGINS` | Optional comma-separated list of *additional* trusted origins (e.g. a preview deployment). |
| `TIEOUT_AUTH_DB` | Optional override for the auth SQLite path (default `./data/tieout-auth.db`). |
| `NEXT_PUBLIC_TIEOUT_API_URL` | Base URL of the FastAPI layer. Only read when the API mode below is `live`. |
| `NEXT_PUBLIC_TIEOUT_API_MODE` | `fixture` (default) or `live`. See `lib/api.ts`. |

## Verification

```bash
npm run build       # production build (type-checks routes)
npm run lint        # eslint
npm test            # node --test lib/*.test.ts — money formatting + cn config
npm run db:migrate  # apply/refresh Better Auth schema
```

Smoke-test auth from the shell — sign up via the `/sign-in` page (toggle to
"Create an account"), then confirm the session cookie is set and `/close`
(once dashboard-ui lands) no longer redirects to `/sign-in`.

## Layout

| Path | Purpose |
|---|---|
| `app/(marketing)/` | Landing page shell — **owned by the landing-page worker (Wave 3)** |
| `app/(app)/` | Close status · review queue · scoreboard shell — **dashboard-ui worker (Wave 3)** |
| `app/(app)/assistant/` | Agent UI — **agent-ui worker (Wave 3)** |
| `app/sign-in/` | Email/password sign-in and sign-up |
| `app/%5Fdev/tokens/` | Dev-only token + primitive proof page at `/_dev/tokens`. `%5F` is Next's documented escape for an underscore URL segment — a plain `_dev` folder would be excluded from routing. **Delete before launch.** |
| `app/api/auth/[...all]/` | Better Auth catch-all route handler |
| `proxy.ts` | Optimistic session-cookie redirect for the `(app)` group (Next.js 16 renamed Middleware to Proxy). Not the authorisation boundary — see `lib/session.ts`. |
| `lib/auth.ts` | Better Auth server instance: secret from env, rate limiting, explicit trusted origins, secure httpOnly sameSite cookies, `organization` plugin |
| `lib/auth-client.ts` | Better Auth React client (`useSession`, `signIn`, `signUp`, `signOut`) |
| `lib/session.ts` | The authoritative server-side session read (`getSession`, `getActor`) — call this from pages/routes, not `proxy.ts` |
| `lib/api.ts` + `lib/api-types.ts` | Typed client over SPEC §12's three screens, with a fixture/live switch |
| `lib/fixtures.ts` | Sample data for the fixture mode, labelled ReconRiver per SPEC §12 |
| `lib/money.ts` | Money formatting — a decimal string in, a decimal string out, never a JS number |
| `lib/motion.ts` | GSAP-side copy of the DESIGN.md §7 duration/easing tokens |
| `lib/fonts.ts` | DESIGN.md §3.1 — Source Serif 4, IBM Plex Sans, IBM Plex Mono (next/font) |
| `components/tieout/` | The five DESIGN.md primitives: disposition badge, money cell, stat tile, aging buckets, close banner |
| `components/ui/` | shadcn/ui components |

## Fixture vs. live API

`lib/api.ts` defaults to `NEXT_PUBLIC_TIEOUT_API_MODE=fixture`, which serves
the labelled ReconRiver sample data in `lib/fixtures.ts` so downstream workers
can build screens before the FastAPI layer exists. Every fixture response
carries a `notice` string (`FIXTURE_NOTICE`) — render it wherever fixture data
appears, per SPEC §12's requirement that example data is never presented as a
real company's books. Submitting a review action in fixture mode throws rather
than pretending a decision was recorded. Set the env var to `live` and point
`NEXT_PUBLIC_TIEOUT_API_URL` at FastAPI once `api-layer` lands.

## Notes

- Three font families, exposed as `font-statement`, `font-ui`, `font-numeral`
  utilities; inline money figures in serif prose use the `tabular` utility
  (DESIGN.md §3.3).
- Light is the primary theme (DESIGN.md §4); a small inline script in
  `app/layout.tsx` applies the persisted/OS theme before first paint to avoid a
  flash, and `next-themes` (`storageKey="tieout-theme"`, matching the inline
  script) handles the rest.
- `--destructive` is reserved for the REFUSE stamp (T3) — never generic form
  errors.
- `prefers-reduced-motion` is honoured once, globally, in `app/globals.css`
  (CSS) — GSAP call sites should branch on the same preference via
  `gsap.matchMedia()` (see `lib/motion.ts`), not re-implement the check.
- `cn` (in `lib/utils.ts`) is a configured `tailwind-merge`, not the bare `cn`
  package — it has been taught DESIGN.md's custom `font-size`, `text-color` and
  `tracking` scales. Importing `cn` from anywhere else silently drops tokens
  (a stock merge treats `text-caption` as a text colour and deletes it next to
  `text-sampled`). Always `import { cn } from "@/lib/utils"`.
