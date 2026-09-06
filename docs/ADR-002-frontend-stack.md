# ADR-002 — Frontend: Next.js, superseding SPEC section 2's "vanilla, zero toolchain"

Status: ACCEPTED (orchestrator decision, 5 Sep 2026 23:30 IST)
Supersedes: docs/SPEC.md section 2 Stack rows "Frontend" and section 13's `web/` layout

## Decision

`web/` is a **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + GSAP** application
with **Better Auth** for authentication. It consumes the FastAPI JSON described in
SPEC section 12. The original "vanilla HTML/CSS/JS reading JSON, zero build step" is dropped.

## Evidence

The product needs three frontend surfaces, and all three are React-shaped:

1. A **landing page** that has to carry the AccountingBench evidence story — the 15%-of-balance
   divergence, the four documented failure modes, the regulatory citations — with enough craft
   that a judge reads it rather than skims it. This is the surface the user explicitly asked to
   carry "real pain points and the main motive".
2. The **three dashboard screens** (close status, review queue, scoreboard) from SPEC section 12.
3. An **agent/assistant UI** over the adjudication and review loop.

`ai-elements` and `assistant-ui` are React component libraries. Better Auth's client and route
handlers target a JS framework. GSAP's `useGSAP` is the React entry point. Hand-rolling those
three in vanilla is strictly *more* code than adopting them, so the zero-toolchain argument
inverts here.

## Risk accepted, and the mitigation

SPEC section 2 called a build step "a liability in a 30-hour window". That risk is real and is
accepted, mitigated structurally:

- **The CLI demo path stays completely independent of the frontend.** The money shot —
  `tieout close` printing `CLOSE REFUSED` — is terminal-only (SPEC section 12). The scoreboard
  and audit verification are CLI commands. A frontend that slips or breaks **cannot cost the
  submission.**
- The frontend sits in the **"Nice"** cut tier per SPEC section 18, not "Must".
- FastAPI remains the single source of truth; the CLI and the frontend consume identical JSON.

## Consequence for SPEC

Whoever owns docs/SPEC.md edits must update the section 2 Frontend row and the section 13
`web/` tree to match this ADR, with a pointer to this file. Do not leave the spec contradicting
the build.
