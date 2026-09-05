"""Foundation smoke test: every package imports, every CLI command is registered.

Not domain logic — this file just asserts the scaffold other workers plug
into is intact. If this fails, the wave 0 foundation is broken.
"""

import importlib

import typer.main
import typer.testing

from tieout.cli import app

PACKAGES = [
    "tieout",
    "tieout.policy",
    "tieout.ingest",
    "tieout.match",
    "tieout.gate",
    "tieout.post",
    "tieout.audit",
    "tieout.memory",
    "tieout.score",
    "tieout.close",
    "tieout.api",
    "tieout.agent",
    "tieout.obs",
]

# docs/SPEC.md section 12 command list (top-level + subcommands).
EXPECTED_COMMANDS = {
    "ingest",
    "policy",
    "reconcile",
    "queue",
    "review",
    "close",
    "score",
    "audit",
    "serve",
}


def test_all_packages_import_cleanly() -> None:
    for name in PACKAGES:
        importlib.import_module(name)


def test_cli_imports() -> None:
    assert app is not None


def test_every_spec_command_is_registered() -> None:
    click_app = typer.main.get_command(app)
    registered = set(click_app.commands)
    missing = EXPECTED_COMMANDS - registered
    assert not missing, f"missing CLI commands: {missing}"


def test_stub_commands_raise_not_implemented() -> None:
    runner = typer.testing.CliRunner()
    result = runner.invoke(app, ["reconcile", "--period", "2026-01"])
    assert result.exit_code != 0
    assert isinstance(result.exception, NotImplementedError)
