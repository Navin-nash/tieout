"""Per-organisation filesystem storage, with the holdout constraint enforced.

Two constraints, from ADR-003 and SPEC section 3, and neither is a string comparison:

1. **An org's files stay inside that org's root.** ``../`` in a filename, an absolute path, and
   a symlink pointing out of the tree are all rejected. The check is on the *real* path after
   ``os.path.realpath``, because a prefix test on the un-resolved string passes happily for
   ``orgs/a/uploads/x -> ../../holdout/expected_reconciliation.csv``.

2. **No upload path or storage location may make the holdout labels reachable.**
   ``expected_reconciliation.csv`` and everything under ``data/holdout/`` are outside the
   agent's allowed-read set, enforced for raw inputs by ``tieout/ingest/paths.py``. This module
   is the second half of that guarantee: the write side. Storage roots are siblings of the
   holdout directory, never ancestors, and any resolved path that lands inside the holdout tree
   raises regardless of how it got there.

``tieout/ingest/paths.py`` is reused rather than reimplemented -- its
:class:`~tieout.ingest.paths.ForbiddenPathError` is the exception type raised here too, so a
caller catches one error type for "the path guard said no" whichever guard said it.
"""

from __future__ import annotations

import os
import re
import unicodedata
import uuid
from pathlib import Path

from tieout.ingest.paths import ALLOWED_FILENAMES, ForbiddenPathError

#: Ground truth. Never readable by the reconcile path, never writable by an upload.
HOLDOUT_DIR_NAME = "holdout"
HOLDOUT_FILENAMES = frozenset({"expected_reconciliation.csv"})

#: Everything tenant-owned lives under ``<data_root>/orgs/<org_id>/``.
ORGS_DIR_NAME = "orgs"
UPLOADS_SUBDIR = "uploads"
RUNS_SUBDIR = "runs"
EVENT_LOG_NAME = "events.jsonl"

#: An org id is a Better Auth string. It becomes a directory name, so it is constrained to
#: characters that cannot traverse, cannot be a device name and cannot differ only by case.
_SAFE_ORG_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

#: Reserved device names on Windows. A directory called ``con`` is not a directory.
_WINDOWS_RESERVED = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
)


class UnsafeOrgIdError(ForbiddenPathError):
    """An org id that cannot safely become a directory name."""


def _check_org_id(org_id: str) -> str:
    if not _SAFE_ORG_ID.match(org_id):
        raise UnsafeOrgIdError(
            f"org id {org_id!r} is not usable as a storage directory name; expected "
            "1-64 characters of [A-Za-z0-9_-] starting alphanumeric"
        )
    if org_id.lower() in _WINDOWS_RESERVED:
        raise UnsafeOrgIdError(f"org id {org_id!r} is a reserved device name")
    return org_id


def data_root(root: Path | None = None) -> Path:
    """The configured data root. Falls back to settings when not given explicitly."""
    if root is not None:
        return root
    from tieout.platform.settings import get_settings

    return get_settings().data_root


def holdout_dir(root: Path | None = None) -> Path:
    """Where ground truth lives. Nothing in this module may ever resolve inside it."""
    return (data_root(root) / HOLDOUT_DIR_NAME).resolve()


def org_root(org_id: str, root: Path | None = None) -> Path:
    """``<data_root>/orgs/<org_id>``. A sibling of the holdout directory, never its parent."""
    return (data_root(root) / ORGS_DIR_NAME / _check_org_id(org_id)).resolve()


def _assert_not_holdout(real: Path, root: Path | None) -> None:
    """Reject anything that resolves into the holdout tree or names a holdout file."""
    if real.name in HOLDOUT_FILENAMES:
        raise ForbiddenPathError(
            f"{real.name!r} is held-out ground truth and is not reachable from tenant storage"
        )
    holdout = holdout_dir(root)
    if real == holdout or holdout in real.parents:
        raise ForbiddenPathError(
            f"path {real} resolves inside the holdout directory {holdout}; ground-truth "
            "isolation is an architectural constraint (SPEC section 3), not a convention"
        )


def resolve_within_org(org_id: str, candidate: str | Path, *, root: Path | None = None) -> Path:
    """Resolve ``candidate`` against the org's root and prove it stayed inside.

    ``candidate`` may be relative to the org root or absolute. Either way the answer is the
    fully resolved real path, or :class:`~tieout.ingest.paths.ForbiddenPathError`.

    The containment test runs against ``os.path.realpath``, so a symlink whose target escapes
    the tree is caught even though the lexical path looks fine. It runs on the deepest existing
    ancestor when the file itself does not exist yet, which is the case on the write path --
    otherwise a symlinked *parent* directory would slip through unchecked.
    """
    base = org_root(org_id, root)
    path = Path(candidate)
    joined = path if path.is_absolute() else base / path

    real = Path(os.path.realpath(joined))
    real_base = Path(os.path.realpath(base))

    # realpath resolves symlinks in existing components and leaves the rest lexically
    # normalised, so this covers both "file exists behind a symlink" and "parent is a symlink".
    if real != real_base and real_base not in real.parents:
        raise ForbiddenPathError(
            f"path {real} escapes the storage root for org {org_id!r} ({real_base})"
        )
    _assert_not_holdout(real, root)
    return real


def safe_stored_name(upload_id: uuid.UUID, original_filename: str) -> str:
    """The on-disk name for an upload. **The client's filename is never used as a path.**

    ADR-003: *"Never trust a filename."* The stored name is the upload's own UUID plus a
    whitelisted extension. A filename of ``../../holdout/expected_reconciliation.csv`` becomes
    ``<uuid>.csv`` and lands exactly where every other upload lands.
    """
    suffix = Path(unicodedata.normalize("NFC", original_filename)).suffix.lower()
    if suffix not in {".csv", ".json"}:
        suffix = ".bin"
    return f"{upload_id.hex}{suffix}"


def upload_path(
    org_id: str, upload_id: uuid.UUID, original_filename: str, *, root: Path | None = None
) -> Path:
    """Where an uploaded file is written. Guaranteed inside the org root, outside the holdout."""
    relative = Path(UPLOADS_SUBDIR) / safe_stored_name(upload_id, original_filename)
    return resolve_within_org(org_id, relative, root=root)


def event_log_path(org_id: str, run_id: uuid.UUID, *, root: Path | None = None) -> Path:
    """The on-disk hash-chained audit log for one run (ADR-003: it stays on disk)."""
    relative = Path(RUNS_SUBDIR) / str(run_id) / EVENT_LOG_NAME
    return resolve_within_org(org_id, relative, root=root)


def ensure_org_storage(org_id: str, *, root: Path | None = None) -> Path:
    """Create the org's directory tree. Returns the root."""
    base = org_root(org_id, root)
    (base / UPLOADS_SUBDIR).mkdir(parents=True, exist_ok=True)
    (base / RUNS_SUBDIR).mkdir(parents=True, exist_ok=True)
    return base


def relative_to_org(org_id: str, path: Path, *, root: Path | None = None) -> str:
    """The org-root-relative form stored in ``upload.stored_path`` / ``run.event_log_path``.

    Storing the relative form means moving the data root does not invalidate every row, and a
    database dump does not leak the server's directory layout.
    """
    real = resolve_within_org(org_id, path, root=root)
    return real.relative_to(Path(os.path.realpath(org_root(org_id, root)))).as_posix()


def assert_reconcile_inputs_are_not_ground_truth(filenames: list[str]) -> None:
    """Guard the reconcile path's input list against the holdout labels.

    ``tieout/ingest/paths.py`` already restricts what ingest may *open*; this catches the
    mistake one step earlier, where an upload set is assembled for a run, and gives a message
    that names the constraint instead of a generic permission error.
    """
    for name in filenames:
        base = Path(name).name
        if base in HOLDOUT_FILENAMES:
            raise ForbiddenPathError(
                f"{base!r} is held-out ground truth and can never be a reconcile input; "
                "scoring runs out-of-process (SPEC section 3)"
            )
        if base not in ALLOWED_FILENAMES:
            raise ForbiddenPathError(
                f"{base!r} is not a recognised ReconRiver input; expected one of "
                f"{sorted(ALLOWED_FILENAMES)}"
            )
