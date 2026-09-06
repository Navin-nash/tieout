# Observability — Neatlogs tracing

Owner: `neatlogs-obs` worker. Code: `tieout/obs/`. Tests: `tests/test_obs.py`.

## 1. Sources (pulled live before writing any code)

- https://pypi.org/project/neatlogs/ — package name `neatlogs`, version 1.4.21, MIT
  license, `requires-python >=3.10,<3.14`, install extras (`neatlogs[langchain,langgraph]`
  etc.), env vars.
- https://docs.neatlogs.com/docs — quickstart: `import neatlogs; neatlogs.init()`.
- https://docs.neatlogs.com/sdk/python — `neatlogs.init()` parameters (`api_key`,
  `workflow_name`, `instrumentations`, `capture_logs`, `sample_rate`, `user_id`, `debug`),
  the `@neatlogs.span(kind=...)` decorator, the `neatlogs.trace(name, kind=...)` context
  manager with `span.set_attribute(...)`, `neatlogs.flush()` / `neatlogs.shutdown()`, and
  the note that LangChain needs `neatlogs.langchain_handler()` rather than
  `instrumentations=["langchain"]`.
- https://docs.neatlogs.com/sdk/concepts/sessions — `trace(name, session_id=...)` groups
  multiple traces (turns) into one conversation timeline: **end-user → session → trace →
  span**.
- https://docs.neatlogs.com/sdk/pii-redaction — `init(mask=callable)` for client-side
  redaction, and `init(pii_enabled=..., pii_entities=..., pii_span_types=...)` for
  project-level (server-side) PII stripping.
- https://github.com/NeatLogs/neatlogs — source, MIT license.

## 2. Reality check against SPEC section 2

SPEC section 2 describes Neatlogs as `pip install neatlogs`, "~2 lines." That's roughly
true for the happy path — `neatlogs.init()` then `@neatlogs.span` — but two things the
spec doesn't call out:

1. **It is a live network client.** `init()` opens a connection to
   `https://ingest.neatlogs.com` (overridable via `NEATLOGS_ENDPOINT`) and ships traces
   there. Anything that can fail on a flaky hackathon Wi-Fi must not be allowed to fail
   `tieout reconcile`.
2. **LangChain/LangGraph auto-instrumentation is not automatic-automatic.** It needs the
   `neatlogs[langchain,langgraph]` extra installed and `neatlogs.langchain_handler()`
   wired into the chain/graph explicitly — it isn't picked up by `instrumentations=[...]`
   the way single-SDK wrapping (OpenAI, Anthropic) is. `agent-adjudicator` (deepagents /
   LangGraph, see ADR-001) should attach that handler itself rather than assume this
   module does it — this module has no LangGraph import, by design (see §3).

Given that, `tieout/obs/tracing.py` does **not** call the Neatlogs SDK directly from
business logic. It wraps it behind a tiny interface (`init_tracing`, `traced`,
`trace_span`) that degrades to a no-op the moment anything about the live path is
missing or wrong.

## 3. The API (`tieout.obs`)

```python
from tieout.obs import init_tracing, traced, trace_span, disposition_attrs

# once, at process start (e.g. tieout/cli.py) -- never required for correctness
init_tracing()


# decorator form
@traced("classify")
def classify(work_item: WorkItem) -> Verdict: ...


# context-manager form, for attaching attributes
def adjudicate(work_item: WorkItem) -> Verdict:
    with trace_span(
        "adjudicate",
        **disposition_attrs(
            work_key=work_item.work_key,
            outcome_class=verdict.outcome_class.value,
            reason_code=verdict.reason_code,
            disposition=disposition.action.value,
            policy_version=policy.version,
            adjudicator=verdict.adjudicator.value,
            tokens_in=usage.input_tokens,
            tokens_out=usage.output_tokens,
            cost_usd=str(usage.cost_usd),
        ),
    ):
        ...
```

That's the whole surface: `init_tracing()`, `traced(name)`, `trace_span(name, **attrs)`,
`disposition_attrs(...)`, `redact_attrs(...)`. `Tracer` is exported for type hints only —
nobody outside `tieout.obs` should construct one.

**Zero-config guarantee (ADR-001):** if `NEATLOGS_API_KEY` is unset, the `neatlogs`
package isn't installed, or `neatlogs.init()`/`neatlogs.trace()` throws for any reason,
every call above becomes a no-op — `trace_span` yields an object whose `set_attribute` is
a no-op, `traced` still calls the wrapped function and returns its value unchanged, and
nothing raises. `tests/test_obs.py` asserts this path explicitly with no
`NEATLOGS_API_KEY` set and no network access.

`disposition_attrs` takes plain strings for the domain enums (`outcome_class`,
`disposition`, `adjudicator`), not the enum objects themselves — `tieout.obs` has no
import of `tieout.gate`/`tieout.match`, so any module can adopt this without a dependency
cycle. Callers pass `.value`.

## 4. Redaction

`redact_attrs` (called automatically by `trace_span`/`disposition_attrs`) strips two
categories of value before anything reaches a span, live or not:

- **Secrets** — any attribute key containing `key`, `secret`, `token`, `password`,
  `authorization`, or `credential`, *except* the domain fields SPEC requires to stay
  visible: `work_key` and the token-count fields `tokens_in`/`tokens_out` (an explicit
  allowlist, since "work_**key**" and "**token**s_in" would otherwise collide with the
  secret markers).
- **Ground truth** — any attribute key matching the `expected_reconciliation.csv` column
  names (`expected_outcome`, `expected_reason_code`, `expected_difference`,
  `ground_truth`). SPEC section 3's ground-truth isolation is architectural: the agent's
  ingest module cannot open that file, and this guard means even a bug that put one of
  those values into a Python dict can't leak it into a trace either.

This is a **client-side** guard on top of whatever Neatlogs' own `pii_enabled`/`mask=`
options do server-side — see §1. Belt and suspenders; the client-side guard runs even in
no-op mode, before any network call would happen.

## 5. Span map — where the scoreboard numbers come from

SPEC section 11 scores cost & latency per 1,000 work items and pass^k reliability. Those
numbers are read off these spans (each module wraps its own function with `@traced` or
`trace_span` from this API — `tieout.obs` does not instrument other modules itself):

| Span name | Owning module | Kind | Key attributes |
|---|---|---|---|
| `ingest` | `tieout/ingest/*` | one per file processed | `work_key` n/a (file-level); row counts, SHA256 |
| `blocking` | `tieout/match/blocking.py` | one per run | candidate group count |
| `features` | `tieout/match/features.py` | one per `WorkItem` | `work_key` |
| `classify` | `tieout/match/classify.py` | one per `WorkItem` | `work_key`, `outcome_class`, `reason_code`, `policy_version`, `adjudicator=DETERMINISTIC` |
| `adjudicate` | `tieout/match/adjudicate.py` | one per residual `WorkItem`, LLM path only | `work_key`, `outcome_class`, `reason_code`, `adjudicator=LLM`, `tokens_in`, `tokens_out`, `cost_usd` |
| `gate` | `tieout/gate/decide.py` | one per `WorkItem` | `work_key`, `disposition`, `policy_version` |
| `post` | `tieout/post/tools.py` | one per posted entry | `work_key`, `disposition=AUTO_POST`/`AUTO_SAMPLED` |
| `close` | `tieout/close/period.py` | one per close attempt | open `REFUSE` count |
| `score` | `tieout/score/metrics.py` | one per scoreboard run (out-of-process) | run id |

**Reading the traces into the scoreboard:**

- **Cost & latency per 1,000 work items** — sum `cost_usd` and wall-clock duration across
  all `classify`+`adjudicate` spans for a run, divide by `run_size / 1000`. Neatlogs
  records per-span duration and (for LLM spans) token/cost automatically once wired to a
  provider SDK; `disposition_attrs` mirrors the same numbers into the attribute set so
  they're readable even in no-op/offline mode (e.g. from application logs) without a
  Neatlogs dashboard.
- **pass^k reliability** — run the same input `k` times (e.g. `k=5`), group spans by
  `work_key`, compare `outcome_class`+`disposition` across runs. Identical every time →
  pass^k = 1.0 for that item. This module doesn't compute the metric (that's
  `tieout/score/metrics.py`); it only guarantees `work_key` is a stable, present
  attribute on every `classify`/`adjudicate`/`gate` span to key the comparison on.
- **Fabrication / STP / escalation precision** — all read off `disposition` +
  `outcome_class` across `gate` spans, joined against the out-of-process scorer's
  ground-truth comparison. No ground-truth value is ever itself an attribute (§4).

## 6. Viewing traces

With a real `NEATLOGS_API_KEY` set, traces appear on the Neatlogs dashboard
(app.neatlogs.com) grouped by `workflow_name="tieout"`. Without a key, or with the
`neatlogs` package absent, nothing is sent anywhere — the attribute values above are
still computable from whatever the calling module logs locally (e.g. via the scoreboard
JSON), since `disposition_attrs` builds the same dict regardless of whether a live
tracer exists.

## 7. What was *not* built here

- No dependency on `pyproject.toml` — that's `scaffold-repo`'s file. `neatlogs` needs to
  land there under an optional `obs` extras group (e.g. `pip install tieout[obs]`); this
  worker did not add it. `tieout/obs/tracing.py` imports `neatlogs` lazily inside
  `init_tracing()` specifically so the rest of the codebase works with the package
  absent.
- No LangGraph/deepagents wiring. `agent-adjudicator` should call
  `neatlogs.langchain_handler()` itself if it wants Neatlogs' native LangGraph
  auto-instrumentation in addition to (or instead of) the `@traced`/`trace_span` calls
  documented above — see the reality check in §2.
