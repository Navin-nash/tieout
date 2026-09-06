"""Observability -- Neatlogs tracing, degrading safely to a no-op.

See docs/OBSERVABILITY.md for the span map and the cited API docs.
"""
from tieout.obs.tracing import (
    Tracer,
    disposition_attrs,
    init_tracing,
    redact_attrs,
    trace_span,
    traced,
)

__all__ = [
    "Tracer",
    "disposition_attrs",
    "init_tracing",
    "redact_attrs",
    "traced",
    "trace_span",
]
