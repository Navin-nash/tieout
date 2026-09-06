# ADR-001 — Agent framework: LangGraph `deepagents`, not Vercel `eve`

Status: ACCEPTED (orchestrator decision, 5 Sep 2026 23:30 IST)
Deciders: orchestrator session tieout-1
Context: docs/SPEC.md sections 2 (Stack), 5.5 (LLM adjudication), 7 (Constrained tool surface), 9 (Decision memory)

## Decision

The agent layer is built on **LangGraph `deepagents` (Python)**. Vercel **`eve`** is rejected.

## Evidence

**1. The engine is language-locked to Python, and the lock is load-bearing.**
SPEC section 2 fixes the core in Python 3.11: stdlib `decimal.Decimal` with explicit
`ROUND_HALF_UP` for all money, pandas for blocking, pydantic v2 frozen models at every
boundary. `eve` is a filesystem-first **Node/TypeScript** framework (`npm install eve`,
docs ship in `node_modules/eve/docs/`). Adopting it means one of two things:
port the money and matching core to TypeScript, which has **no stdlib decimal type** and
would put float risk on the exact thing this product must never get wrong; or run a
cross-language RPC bridge between a TS agent and a Python engine. Both are pure overhead
against a 28-hour clock, and the first is a correctness regression.

**2. The thesis needs a tool allowlist, not a channel runtime.**
Tieout's entire differentiator (SPEC section 7) is the constrained tool surface — "the
absence is the feature". `deepagents`' `create_deep_agent()` takes an explicit `tools`
list that **is** the agent's whole capability surface, so the allowlist becomes the literal
implementation of the thesis rather than a convention layered on top. `eve`'s strengths —
durable long-running agents, channels, connections, schedules, sandboxes — describe an
always-on conversational backend. Tieout is a batch reconcile plus a review queue. Those
capabilities are unused surface area, and unused surface area in an agent that must not
fabricate is a liability, not a feature.

**3. Human-in-the-loop is a first-class LangGraph primitive.**
T2 ESCALATE and the review queue (SPEC sections 6, 12) need durable interrupt/resume where
the resume carries a human identity distinct from the initiator. LangGraph `interrupt()`
plus a checkpointer gives this natively and maps directly onto the four-eyes requirement
in SPEC section 8 (`approver_id != initiator_id`).

**4. Decision memory has a home.**
`deepagents` ships pluggable filesystem/memory backends. `PriorDecision` (SPEC section 9)
lands there with a reason-code bucket plus nearest-neighbour scan — no vector store, which
is what the spec explicitly asks for.

**5. Judge signal.**
Maximor's published stack is Python (SPEC section 2, from their job postings). Shipping
Python is a free, deliberate alignment signal to the judge.

## Consequences

- Agent layer is Python. The Next.js frontend talks to FastAPI over JSON, so there is no
  need for a TypeScript agent runtime anywhere in the system.
- `eve` stays the fallback only if the product later needs channel-driven always-on agents,
  which SPEC section 19 puts explicitly out of scope.

## Constraint that survives this decision

**The agent layer stays optional.** SPEC section 2's resilience decision is non-negotiable:
the deterministic cascade plus the refusal gate must run end-to-end with **zero LLM calls**.
`deepagents` wraps adjudication of the residual only. If the LLM path is removed the system
still ingests, classifies, refuses, closes and scores. Any design that makes `deepagents`
a hard dependency of `tieout reconcile` is a violation and must be rejected in review.
