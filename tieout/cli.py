"""Tieout CLI — the primary demo surface (docs/SPEC.md section 12).

Every command below is a stub: it registers the exact signature the spec
promises and raises NotImplementedError naming the wave/worker that owns the
real implementation (see docs/PLAN.md). This file is the integration seam
later workers plug into — do not change a signature without updating PLAN.md.
"""

from __future__ import annotations

import typer

app = typer.Typer(help="Tieout — the close agent that refuses to plug.")
policy_app = typer.Typer(help="Policy layer: materiality, tolerances, versions.")
audit_app = typer.Typer(help="Audit trail: hash-chain verification and evidence.")
app.add_typer(policy_app, name="policy")
app.add_typer(audit_app, name="audit")


def _todo(command: str, wave: str, owner: str) -> None:
    raise NotImplementedError(
        f"`tieout {command}` is not implemented yet — owned by {wave} worker "
        f"'{owner}' (see docs/PLAN.md)."
    )


@app.callback()
def main_options(
    ctx: typer.Context,
    json_out: bool = typer.Option(False, "--json", help="Emit structured JSON instead of text."),
) -> None:
    """Global options shared by every command."""
    ctx.obj = {"json": json_out}


@app.command()
def ingest(
    scenario: str = typer.Option("month-end-close", "--scenario", help="ReconRiver scenario name."),
) -> None:
    """Hash the three source files and load them into the canonical model."""
    _todo("ingest", "Wave 1", "ingest-money")


@policy_app.command("validate")
def policy_validate() -> None:
    """Schema check plus AS 2105 sanity check of policy.yaml."""
    _todo("policy validate", "Wave 1", "policy-layer")


@policy_app.command("show")
def policy_show(
    version: str = typer.Option(..., "--version", help="Policy version, e.g. 2026.01-r3"),
) -> None:
    """Print a policy version's thresholds and provenance."""
    _todo("policy show", "Wave 1", "policy-layer")


@app.command()
def reconcile(
    period: str = typer.Option(..., "--period", help="Period to reconcile, e.g. 2026-01"),
) -> None:
    """Run ingest -> blocking -> classify -> gate for a period."""
    _todo("reconcile", "Wave 2", "refusal-gate")


@app.command()
def queue(
    blocking: bool = typer.Option(False, "--blocking", help="Show only items blocking the close."),
    aging: bool = typer.Option(False, "--aging", help="Show items grouped into aging buckets."),
) -> None:
    """List the exception queue, sorted by materiality x age."""
    _todo("queue", "Wave 2", "refusal-gate")


@app.command()
def review(
    work_key: str = typer.Argument(..., help="The work item to review."),
    approve: bool = typer.Option(False, "--approve"),
    reject: bool = typer.Option(False, "--reject"),
    reclassify: str | None = typer.Option(None, "--reclassify", help="New outcome class."),
    as_: str = typer.Option(..., "--as", help="Reviewer identity, e.g. controller@acme."),
    note: str | None = typer.Option(None, "--note"),
) -> None:
    """Approve, reject or reclassify a queue item under a named identity (four-eyes enforced)."""
    _todo("review", "Wave 2", "decision-memory")


@app.command()
def close(
    period: str = typer.Option(..., "--period", help="Period to close, e.g. 2026-01"),
) -> None:
    """The close gate: refuses while any REFUSE item is open. No override exists (I4)."""
    _todo("close", "Wave 2", "close-gate")


@app.command()
def score(
    against: str | None = typer.Option(None, "--against", help="Ground-truth source"),
    baseline: str | None = typer.Option(None, "--baseline", help="naive-llm | deterministic"),
    passk: int | None = typer.Option(None, "--passk", help="Repeat k times for pass^k reliability"),
) -> None:
    """Out-of-process scoring against held-out labels."""
    _todo("score", "Wave 2", "scoreboard")


@audit_app.command("verify")
def audit_verify() -> None:
    """Hash-chain integrity check over the event log."""
    _todo("audit verify", "Wave 1", "audit-chain")


@audit_app.command("evidence")
def audit_evidence(
    work_key: str = typer.Argument(..., help="The work item whose evidence pack to print."),
) -> None:
    """Print the evidence pack for a work item."""
    _todo("audit evidence", "Wave 1", "audit-chain")


@app.command()
def serve(
    port: int = typer.Option(8000, "--port", help="Port for the FastAPI dashboard server."),
) -> None:
    """Run the FastAPI server that serves the dashboard's JSON."""
    _todo("serve", "Wave 2", "api-layer")


def main() -> None:
    """Console-script entry point (`tieout = tieout.cli:main`)."""
    app()


if __name__ == "__main__":
    main()
