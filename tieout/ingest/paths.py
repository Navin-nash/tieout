"""Ground-truth isolation — ingest can only read data/raw/."""

from __future__ import annotations

import os
from pathlib import Path
from typing import IO, Literal

RAW_DIR_NAME = "raw"
ALLOWED_FILENAMES = frozenset(
    {
        "internal_transactions.csv",
        "processor_transactions.csv",
        "bank_settlements.csv",
        "scenario_manifest.json",
    }
)


class ForbiddenPathError(PermissionError):
    """Raised when ingest attempts to read outside the allowed raw set."""


def _repo_root() -> Path:
    return Path.cwd()


def raw_data_dir(root: Path | None = None) -> Path:
    return (root or _repo_root()) / "data" / RAW_DIR_NAME


def resolve_allowed_path(path: str | Path, root: Path | None = None) -> Path:
    """Resolve, normalise, and verify a path is an allowed raw input file."""
    base = (root or _repo_root()).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = (base / candidate).resolve()
    else:
        candidate = candidate.resolve()

    raw_dir = raw_data_dir(base).resolve()
    try:
        candidate.relative_to(raw_dir)
    except ValueError:
        raise ForbiddenPathError(
            f"path {candidate} is outside allowed ingest directory {raw_dir}"
        ) from None

    if candidate.name not in ALLOWED_FILENAMES:
        raise ForbiddenPathError(
            f"file {candidate.name!r} is not in the agent-readable allowlist"
        )

    return candidate


def open_allowed(
    path: str | Path,
    mode: Literal["r", "rb"] = "r",
    *,
    root: Path | None = None,
    encoding: str = "utf-8",
) -> IO[bytes] | IO[str]:
    """Open a file only if it passes the allowed-read guard."""
    resolved = resolve_allowed_path(path, root=root)
    real = Path(os.path.realpath(resolved))
    raw_dir = raw_data_dir(root or _repo_root()).resolve()
    try:
        real.relative_to(raw_dir)
    except ValueError:
        raise ForbiddenPathError(
            f"symlink target {real} escapes allowed ingest directory"
        ) from None
    if real.name not in ALLOWED_FILENAMES:
        raise ForbiddenPathError(f"symlink resolves to disallowed file {real.name!r}")

    if mode == "rb":
        return real.open(mode)
    return real.open(mode, encoding=encoding)
