"""Neatlogs tracing wrapper for tieout.

Docs pulled live before writing this (2026-09-05), cited per PLAN.md rule 7:
- https://pypi.org/project/neatlogs/            package name, version 1.4.21,
  license MIT, requires-python >=3.10,<3.14, install extras
- https://docs.neatlogs.com/docs                 quickstart: `import neatlogs;
  neatlogs.init()`
- https://docs.neatlogs.com/sdk/python            init() params (api_key,
  workflow_name, instrumentations, capture_logs, sample_rate, user_id,
  debug), @neatlogs.span(kind=...), neatlogs.trace(name, kind=...) context
  manager with span.set_attribute(), neatlogs.flush()/shutdown(), LangChain
  needs neatlogs.langchain_handler() not instrumentations=
- https://docs.neatlogs.com/sdk/concepts/sessions  trace(name, session_id=...)
  groups traces into one conversation timeline
- https://docs.neatlogs.com/sdk/pii-redaction      init(mask=callable) and
  init(pii_enabled=..., pii_entities=..., pii_span_types=...) for
  project-level PII stripping
- https://github.com/NeatLogs/neatlogs             source, MIT
Env var: NEATLOGS_API_KEY (optional NEATLOGS_ENDPOINT, NEATLOGS_UPLOADS_ENABLED).

SPEC section 2 says Neatlogs is "~2 lines". The real SDK is closer to that for
the happy path (`neatlogs.init()` + `@neatlogs.span`), but it is a live network
client with 40+ optional instrumentations -- worth knowing before depending on
exact call shapes, since none of that surface is pinned by a lockfile yet.

Hard requirement (ADR-001, SPEC section 2): `tieout reconcile` runs end-to-end
with zero LLM calls and with no observability configured. Every function here
degrades to a no-op that never raises and never blocks the caller -- missing
key, missing package, and a failed network call all take the same fallback
path.
"""
from __future__ import annotations

import contextlib
import functools
import logging
import os
from typing import Any, Callable, Iterator, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

_API_KEY_ENV = "NEATLOGS_API_KEY"
_WORKFLOW_NAME = "tieout"

# Keys that must never reach a trace attribute, wherever they appear.
_SECRET_KEY_MARKERS = ("key", "secret", "token", "password", "authorization", "credential")
# Domain fields that legitimately contain "key"/"token" as a substring but are
# not secrets -- SPEC calls these out by name as attributes that must stay
# visible (work_key identifies the item; token counts feed the cost metric).
_ALWAYS_SAFE_KEYS = ("work_key", "tokens_in", "tokens_out")
# Ground-truth columns the agent must never see or emit (SPEC section 3:
# `expected_reconciliation.csv` is held out and loaded only by the scorer).
_GROUND_TRUTH_MARKERS = (
    "expected_outcome",
    "expected_reason_code",
    "expected_difference",
    "ground_truth",
)

REDACTED = "***"


class _NullSpan:
    """What `set_attribute` lands on when there is no live tracer."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: D401
        pass


@contextlib.contextmanager
def _noop_span() -> Iterator[_NullSpan]:
    yield _NullSpan()


@contextlib.contextmanager
def _live_span(ctx: Any, attrs: dict[str, Any]) -> Iterator[Any]:
    try:
        with ctx as span:
            for key, value in attrs.items():
                _safe_set_attribute(span, key, value)
            yield span
    except Exception:
        # A live backend misbehaving (network, SDK bug) must never take down
        # the caller -- degrade to a null span for the remainder of the block.
        logger.debug("neatlogs span failed, continuing without tracing", exc_info=True)
        yield _NullSpan()


def _safe_set_attribute(span: Any, key: str, value: Any) -> None:
    try:
        span.set_attribute(key, value)
    except Exception:
        logger.debug("neatlogs set_attribute failed for %s", key, exc_info=True)


class Tracer:
    """Live or no-op tracer behind one interface."""

    def __init__(self, backend: Any | None) -> None:
        self._backend = backend  # the imported `neatlogs` module, or None

    @property
    def enabled(self) -> bool:
        return self._backend is not None

    def span(self, name: str, **attrs: Any):
        if self._backend is None:
            return _noop_span()
        try:
            ctx = self._backend.trace(name)
        except Exception:  # pragma: no cover - defensive, only hit with a live backend
            logger.debug("neatlogs trace() failed, degrading to no-op", exc_info=True)
            return _noop_span()
        return _live_span(ctx, redact_attrs(attrs))


_tracer: Tracer = Tracer(None)


def init_tracing() -> Tracer:
    """Read NEATLOGS_API_KEY and try to start a live tracer.

    Never raises. A missing key, a missing `neatlogs` package (it is an
    optional `obs` extra -- see pyproject.toml), or a failed init call all
    degrade to a no-op tracer. `tieout reconcile` must work with zero setup.
    """
    global _tracer
    api_key = os.environ.get(_API_KEY_ENV)
    if not api_key:
        _tracer = Tracer(None)
        return _tracer
    try:
        import neatlogs  # local import: optional dependency, `obs` extras group

        neatlogs.init(api_key=api_key, workflow_name=_WORKFLOW_NAME)
        _tracer = Tracer(neatlogs)
    except Exception:
        logger.debug("neatlogs init failed, degrading to no-op", exc_info=True)
        _tracer = Tracer(None)
    return _tracer


def trace_span(name: str, **attrs: Any):
    """Context manager. Live span if tracing is configured, no-op otherwise.

        with trace_span("classify", work_key=wk, outcome_class="MATCHED"):
            ...
    """
    return _tracer.span(name, **attrs)


def traced(name: str) -> Callable[[F], F]:
    """Decorator version of `trace_span`, for wrapping a whole function.

        @traced("ingest")
        def ingest(path: str) -> Manifest:
            ...
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with trace_span(name):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def redact_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    """Strip secrets and ground-truth values before they ever reach a span."""
    clean: dict[str, Any] = {}
    for key, value in attrs.items():
        lowered = key.lower()
        is_secret = lowered not in _ALWAYS_SAFE_KEYS and any(
            marker in lowered for marker in _SECRET_KEY_MARKERS
        )
        is_ground_truth = any(marker in lowered for marker in _GROUND_TRUTH_MARKERS)
        clean[key] = REDACTED if (is_secret or is_ground_truth) else value
    return clean


def disposition_attrs(
    *,
    work_key: str,
    outcome_class: str,
    reason_code: str,
    disposition: str,
    policy_version: str,
    adjudicator: str,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_usd: str | None = None,
) -> dict[str, Any]:
    """Build the standard attribute set for gate/classify/adjudicate spans.

    Enum members from `tieout.gate`/`tieout.match` are not imported here --
    pass `.value` (a plain string) so `obs` stays free of a dependency on
    modules owned by other workers.
    """
    attrs: dict[str, Any] = {
        "work_key": work_key,
        "outcome_class": outcome_class,
        "reason_code": reason_code,
        "disposition": disposition,
        "policy_version": policy_version,
        "adjudicator": adjudicator,
    }
    if tokens_in is not None:
        attrs["tokens_in"] = tokens_in
    if tokens_out is not None:
        attrs["tokens_out"] = tokens_out
    if cost_usd is not None:
        attrs["cost_usd"] = cost_usd
    return redact_attrs(attrs)
