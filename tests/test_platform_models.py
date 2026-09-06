"""Schema-shape and storage-guard tests. None of these need a database.

The money assertions are the important ones. ADR-003 and SPEC section 1 rest on exact
arithmetic; a ``DOUBLE PRECISION`` money column would undo it silently, at some scale, in
production, and nowhere in a test suite that only checked behaviour on small numbers. So the
check is on the metadata itself: walk every column of every table and fail if a binary float
type appears anywhere at all.
"""

# ruff: noqa: E402
# The pytest.importorskip guard below must run before the tieout.platform imports.

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

# The platform layer needs sqlalchemy, psycopg and pydantic-settings. Those are not in
# pyproject.toml yet -- that file is owned by another worker and this one only reports the
# requirement (see docs/PLATFORM.md, "Dependencies"). Until they land, skip this module loudly
# instead of failing collection and turning the whole suite red.
pytest.importorskip("sqlalchemy", reason="sqlalchemy is not installed; see docs/PLATFORM.md")
pytest.importorskip(
    "pydantic_settings", reason="pydantic-settings is not installed; see docs/PLATFORM.md"
)

from sqlalchemy import Double, Float, Numeric

from tieout.ingest.paths import ForbiddenPathError
from tieout.platform import storage
from tieout.platform.models import (
    TENANT_MODELS,
    Base,
    DispositionAction,
    MoneyColumn,
    OrgScoped,
)
from tieout.platform.settings import PlatformSettings, normalise_database_url

# ── Money is NUMERIC, everywhere, with no exceptions ──────────────────────────

#: Every column that holds an amount of money. Kept explicit rather than derived from a name
#: pattern: the list is the specification, and a new money column has to be added here.
MONEY_COLUMNS = {
    ("work_item", "amount"),
    ("verdict", "amount_delta"),
    ("verdict", "fee_explained_delta"),
    ("disposition", "amount"),
    ("prior_decision", "amount_delta"),
}


def test_no_binary_float_column_exists_anywhere() -> None:
    """A float column in this schema is a defect, money or not.

    Stated as "nowhere" rather than "nowhere in the money columns" on purpose. A blanket ban is
    checkable; a per-column judgement about whether something counts as money is the kind of
    rule that erodes. ``confidence`` is NUMERIC for the same reason -- it is compared against
    the tier boundaries in SPEC section 6.
    """
    offenders = [
        f"{table.name}.{column.name} is {type(column.type).__name__}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, (Float, Double))
    ]
    assert offenders == [], "binary float columns found: " + "; ".join(offenders)


@pytest.mark.parametrize(("table_name", "column_name"), sorted(MONEY_COLUMNS))
def test_money_column_is_numeric_18_2(table_name: str, column_name: str) -> None:
    column = Base.metadata.tables[table_name].columns[column_name]
    assert isinstance(column.type, Numeric), f"{table_name}.{column_name} is not NUMERIC"
    assert not isinstance(column.type, (Float, Double))
    assert column.type.asdecimal is True, "money must round-trip as Decimal, not float"
    assert (column.type.precision, column.type.scale) == (18, 2)


def test_money_column_type_object_is_shared_and_exact() -> None:
    assert isinstance(MoneyColumn, Numeric)
    assert (MoneyColumn.precision, MoneyColumn.scale, MoneyColumn.asdecimal) == (18, 2, True)


def test_confidence_is_exact_not_float() -> None:
    """Tier boundaries are 0.95 / 0.90 / 0.60. Comparing those against a binary float is a bug."""
    column = Base.metadata.tables["verdict"].columns["confidence"]
    assert isinstance(column.type, Numeric) and not isinstance(column.type, (Float, Double))
    assert (column.type.precision, column.type.scale) == (5, 4)
    # The value that motivates the choice: 0.95 is not representable in binary floating point.
    assert Decimal("0.95") != Decimal(0.95)


# ── Tenancy is declared in the type, not remembered ───────────────────────────


@pytest.mark.parametrize("model", TENANT_MODELS, ids=lambda m: m.__tablename__)
def test_every_tenant_model_carries_the_scope_marker_and_the_column(model: type) -> None:
    """The mixin is the isolation hook; the column is what the filter uses. Both, or neither."""
    assert issubclass(model, OrgScoped)
    column = model.__table__.columns["org_id"]
    assert not column.nullable
    targets = {fk.column.table.name for fk in column.foreign_keys}
    assert targets == {"organisation"}


def test_tenant_models_list_matches_the_mixin() -> None:
    """The declared list and the actual subclasses cannot drift apart."""
    from tieout.platform.tenancy import tenant_scoped_models

    assert set(tenant_scoped_models()) == set(TENANT_MODELS)


def test_organisation_itself_is_not_tenant_scoped() -> None:
    """The tenant table cannot be filtered by tenant; that would make provisioning impossible."""
    from tieout.platform.models import Organisation

    assert not issubclass(Organisation, OrgScoped)


# ── The four dispositions, and there is no fifth ──────────────────────────────


def test_disposition_action_has_exactly_four_values_and_no_override() -> None:
    """SPEC section 6 and invariant I4: no force, no override, no plug -- not even as a value."""
    assert {a.value for a in DispositionAction} == {
        "AUTO_POST",
        "AUTO_SAMPLED",
        "ESCALATE",
        "REFUSE",
    }
    forbidden = {"FORCE", "OVERRIDE", "PLUG", "FORCE_POST", "IGNORE"}
    assert forbidden.isdisjoint({a.name for a in DispositionAction})


def test_refuse_is_blocking_at_the_database() -> None:
    """I4 restated as a CHECK, so a direct SQL write cannot mark a REFUSE non-blocking."""
    names = {c.name for c in Base.metadata.tables["disposition"].constraints}
    assert "ck_disposition_refuse_is_blocking" in names
    assert "ck_disposition_four_eyes" in names


def test_prior_decision_cannot_be_written_by_a_service_identity() -> None:
    """SPEC section 9: the memory only ever replays a *human's* judgment."""
    names = {c.name for c in Base.metadata.tables["prior_decision"].constraints}
    assert "ck_prior_decision_human_only" in names
    columns = set(Base.metadata.tables["prior_decision"].columns.keys())
    # No tier, no action: a prior decision is evidence to cite, never a permission to post.
    assert {"tier", "action", "overrides"}.isdisjoint(columns)


def test_run_references_the_event_log_rather_than_storing_it() -> None:
    """ADR-003: the hash-chained log stays on disk and stays the source of truth."""
    columns = set(Base.metadata.tables["run"].columns.keys())
    assert "event_log_path" in columns
    assert "event_log_head_hash" in columns
    assert "events" not in columns and "event_log" not in columns
    assert "event" not in Base.metadata.tables, "the audit chain must not be ported into tables"


# ── Storage: containment, traversal, symlink escape, holdout ──────────────────


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    (tmp_path / "holdout").mkdir()
    (tmp_path / "holdout" / "expected_reconciliation.csv").write_text("expected_outcome\n")
    storage.ensure_org_storage("acme", root=tmp_path)
    return tmp_path


def test_upload_path_lands_inside_the_org_root(data_root: Path) -> None:
    upload_id = uuid.uuid4()
    path = storage.upload_path("acme", upload_id, "internal_transactions.csv", root=data_root)
    assert path.parent == (data_root / "orgs" / "acme" / "uploads").resolve()
    assert path.name == f"{upload_id.hex}.csv"


def test_client_filename_is_never_used_as_a_path(data_root: Path) -> None:
    """ADR-003: never trust a filename. Traversal in the name resolves to an ordinary upload."""
    upload_id = uuid.uuid4()
    hostile = "../../holdout/expected_reconciliation.csv"
    path = storage.upload_path("acme", upload_id, hostile, root=data_root)
    assert path.parent == (data_root / "orgs" / "acme" / "uploads").resolve()
    assert "holdout" not in str(path)
    assert path.name == f"{upload_id.hex}.csv"


@pytest.mark.parametrize(
    "hostile",
    [
        "../../../etc/passwd",
        "../orgb/uploads/stolen.csv",
        "uploads/../../orgb/secret.csv",
        "..",
    ],
)
def test_traversal_out_of_the_org_root_is_refused(data_root: Path, hostile: str) -> None:
    with pytest.raises(ForbiddenPathError):
        storage.resolve_within_org("acme", hostile, root=data_root)


def test_absolute_path_outside_the_org_root_is_refused(data_root: Path) -> None:
    with pytest.raises(ForbiddenPathError):
        storage.resolve_within_org("acme", data_root / "holdout", root=data_root)


def test_another_orgs_root_is_refused(data_root: Path) -> None:
    storage.ensure_org_storage("beta", root=data_root)
    with pytest.raises(ForbiddenPathError):
        storage.resolve_within_org(
            "acme", data_root / "orgs" / "beta" / "uploads" / "x.csv", root=data_root
        )


@pytest.mark.parametrize("bad_org", ["../evil", "a/b", "", "con", "x" * 65, ".hidden"])
def test_an_org_id_that_could_traverse_is_refused(data_root: Path, bad_org: str) -> None:
    with pytest.raises(ForbiddenPathError):
        storage.org_root(bad_org, root=data_root)


@pytest.mark.skipif(
    os.name == "nt" and not os.environ.get("TIEOUT_TEST_SYMLINKS"),
    reason="symlink creation on Windows needs Developer Mode; set TIEOUT_TEST_SYMLINKS=1",
)
def test_symlink_escape_is_caught_not_just_the_string_prefix(data_root: Path) -> None:
    """A prefix check on the un-resolved string passes here. The realpath check does not."""
    link = data_root / "orgs" / "acme" / "uploads" / "innocent.csv"
    link.symlink_to(data_root / "holdout" / "expected_reconciliation.csv")
    # The lexical path is squarely inside the org root -- this is exactly the case a naive
    # startswith() guard waves through.
    assert str(link).startswith(str(data_root / "orgs" / "acme"))
    with pytest.raises(ForbiddenPathError):
        storage.resolve_within_org("acme", link, root=data_root)


def _link_dir(link: Path, target: Path) -> None:
    """Point ``link`` at directory ``target``, however this platform can.

    Windows refuses ``symlink_to`` without Developer Mode, but allows a directory *junction*
    unprivileged -- and ``os.path.realpath`` resolves both. Using the junction means the
    write-path escape, which is the one an upload endpoint is actually exposed to, is exercised
    on a developer's Windows box and not only in Linux CI.
    """
    if os.name == "nt":
        import subprocess

        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def test_symlinked_parent_directory_is_caught(data_root: Path) -> None:
    """The file need not exist: a linked *parent* is the write-path version of the attack.

    This is the case a ``str.startswith`` containment check waves straight through, because
    the lexical path never leaves the org root.
    """
    link_dir = data_root / "orgs" / "acme" / "uploads" / "sneaky"
    _link_dir(link_dir, data_root / "holdout")
    assert str(link_dir).startswith(str(data_root / "orgs" / "acme"))
    with pytest.raises(ForbiddenPathError):
        storage.resolve_within_org("acme", "uploads/sneaky/anything.csv", root=data_root)


def test_the_holdout_file_can_never_be_a_storage_target(data_root: Path) -> None:
    """SPEC section 3: ground-truth isolation is architectural, not a convention."""
    with pytest.raises(ForbiddenPathError, match="ground truth"):
        storage.resolve_within_org("acme", "uploads/expected_reconciliation.csv", root=data_root)


def test_the_holdout_file_can_never_be_a_reconcile_input() -> None:
    with pytest.raises(ForbiddenPathError, match="ground truth"):
        storage.assert_reconcile_inputs_are_not_ground_truth(
            ["internal_transactions.csv", "expected_reconciliation.csv"]
        )


def test_reconcile_inputs_must_be_recognised_reconriver_files() -> None:
    with pytest.raises(ForbiddenPathError):
        storage.assert_reconcile_inputs_are_not_ground_truth(["something_else.csv"])
    # The real set passes.
    storage.assert_reconcile_inputs_are_not_ground_truth(
        ["internal_transactions.csv", "processor_transactions.csv", "bank_settlements.csv"]
    )


def test_ingest_allowed_read_set_still_excludes_ground_truth() -> None:
    """Reuse, not reimplementation: the write guard here and the read guard there must agree."""
    from tieout.ingest.paths import ALLOWED_FILENAMES

    assert storage.HOLDOUT_FILENAMES.isdisjoint(ALLOWED_FILENAMES)


def test_stored_path_is_recorded_relative_to_the_org_root(data_root: Path) -> None:
    """A database dump must not leak the server's directory layout."""
    upload_id = uuid.uuid4()
    path = storage.upload_path("acme", upload_id, "bank_settlements.csv", root=data_root)
    assert storage.relative_to_org("acme", path, root=data_root) == f"uploads/{upload_id.hex}.csv"


def test_event_log_lives_under_the_org_root(data_root: Path) -> None:
    run_id = uuid.uuid4()
    path = storage.event_log_path("acme", run_id, root=data_root)
    assert path == (data_root / "orgs" / "acme" / "runs" / str(run_id) / "events.jsonl").resolve()


# ── Settings ──────────────────────────────────────────────────────────────────


def test_database_url_is_required_with_no_silent_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(Exception, match="database_url|DATABASE_URL"):
        PlatformSettings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgresql://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("postgres://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("postgresql+psycopg://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
    ],
)
def test_provider_urls_are_normalised_onto_psycopg3_async(given: str, expected: str) -> None:
    assert normalise_database_url(given) == expected


@pytest.mark.parametrize(
    "url", ["postgresql+psycopg2://u:p@h/d", "postgresql+asyncpg://u:p@h/d", "mysql://u:p@h/d"]
)
def test_a_wrong_driver_fails_at_startup_not_at_first_query(url: str) -> None:
    with pytest.raises(ValueError):
        normalise_database_url(url)
