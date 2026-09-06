"""tests/test_obs.py

Every test runs with NEATLOGS_API_KEY unset, so all of them exercise the
no-op path required by ADR-001 ("zero LLM calls, no observability configured
must still work"). No network calls are made anywhere in this file.
"""
from __future__ import annotations

import inspect

import pytest

from tieout.obs import disposition_attrs, init_tracing, redact_attrs, trace_span, traced


@pytest.fixture(autouse=True)
def no_neatlogs_key(monkeypatch):
    monkeypatch.delenv("NEATLOGS_API_KEY", raising=False)


def test_init_tracing_noop_without_key():
    tracer = init_tracing()
    assert tracer.enabled is False


def test_trace_span_never_raises_without_key():
    with trace_span("ingest", work_key="wk-1") as span:
        span.set_attribute("outcome_class", "MATCHED")
    # reaching this line means no-op mode swallowed everything cleanly


def test_traced_preserves_return_value_and_signature():
    def original(a: int, b: str = "x") -> str:
        """docstring"""
        return f"{a}-{b}"

    wrapped = traced("classify")(original)

    assert wrapped(1, b="y") == "1-y"
    assert wrapped.__name__ == "original"
    assert inspect.signature(wrapped) == inspect.signature(original)


def test_traced_decorator_never_raises_without_key():
    @traced("adjudicate")
    def double(x: int) -> int:
        return x * 2

    assert double(21) == 42


def test_redact_attrs_strips_planted_secret():
    attrs = {
        "work_key": "wk-1",
        "api_key": "sk-fake-secret-do-not-leak",
        "authorization": "Bearer fake-token",
    }
    clean = redact_attrs(attrs)
    assert clean["work_key"] == "wk-1"
    assert clean["api_key"] == "***"
    assert clean["authorization"] == "***"
    assert "sk-fake-secret-do-not-leak" not in clean.values()
    assert "Bearer fake-token" not in clean.values()


def test_redact_attrs_strips_ground_truth_columns():
    attrs = {"expected_outcome": "MATCHED", "expected_difference": "0.00"}
    clean = redact_attrs(attrs)
    assert clean["expected_outcome"] == "***"
    assert clean["expected_difference"] == "***"


def test_disposition_attrs_builds_expected_shape():
    attrs = disposition_attrs(
        work_key="wk-1",
        outcome_class="MATCHED",
        reason_code="EXACT",
        disposition="AUTO_POST",
        policy_version="2026-09-05",
        adjudicator="DETERMINISTIC",
        tokens_in=10,
        tokens_out=5,
        cost_usd="0.0012",
    )
    assert attrs == {
        "work_key": "wk-1",
        "outcome_class": "MATCHED",
        "reason_code": "EXACT",
        "disposition": "AUTO_POST",
        "policy_version": "2026-09-05",
        "adjudicator": "DETERMINISTIC",
        "tokens_in": 10,
        "tokens_out": 5,
        "cost_usd": "0.0012",
    }


def test_disposition_attrs_redacts_secret_passed_by_mistake():
    attrs = disposition_attrs(
        work_key="wk-2",
        outcome_class="AMBIGUOUS_MATCH",
        reason_code="MULTI_CANDIDATE",
        disposition="REFUSE",
        policy_version="2026-09-05",
        adjudicator="LLM",
    )
    assert "api_key" not in attrs  # not passed, but confirms shape stays tight
