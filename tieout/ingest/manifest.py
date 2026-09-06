"""SHA256 run manifest and re-verification."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from tieout import __version__
from tieout.ingest.paths import open_allowed, raw_data_dir

FROZEN = ConfigDict(frozen=True, strict=True)

INPUT_FILES = (
    "internal_transactions.csv",
    "processor_transactions.csv",
    "bank_settlements.csv",
    "scenario_manifest.json",
)


class FeePolicy(BaseModel):
    model_config = FROZEN

    percentage_rate: Decimal
    fixed_charge: Decimal
    rounding_mode: str


class FileHashMismatch(BaseModel):
    model_config = FROZEN

    file: str
    expected: str
    actual: str


class VerificationResult(BaseModel):
    model_config = FROZEN

    ok: bool
    mismatches: list[FileHashMismatch]


class RunManifest(BaseModel):
    model_config = FROZEN

    run_id: str
    timestamp: str
    policy_version: str
    tool_version: str
    file_hashes: dict[str, str]
    fee_policy: FeePolicy
    settlement_window: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_percentage(rate: str) -> Decimal:
    text = rate.strip()
    if text.endswith("%"):
        return Decimal(text[:-1]) / Decimal(100)
    return Decimal(text)


def load_scenario_manifest(root: Path | None = None) -> dict[str, Any]:
    base = root or Path.cwd()
    with open_allowed(base / "data" / "raw" / "scenario_manifest.json", root=base) as fh:
        return json.load(fh)


def fee_policy_from_manifest(manifest: dict[str, Any]) -> FeePolicy:
    fp = manifest["fee_policy"]
    return FeePolicy(
        percentage_rate=_parse_percentage(fp["percentage_rate"]),
        fixed_charge=Decimal(str(fp["fixed_charge"])),
        rounding_mode=fp["rounding_mode"],
    )


def build_manifest(
    *,
    root: Path | None = None,
    policy_version: str = "placeholder",
    run_id: str | None = None,
) -> RunManifest:
    base = root or Path.cwd()
    raw = raw_data_dir(base)
    scenario = load_scenario_manifest(base)

    hashes: dict[str, str] = {}
    for name in INPUT_FILES:
        hashes[name] = sha256_file(raw / name)

    return RunManifest(
        run_id=run_id or str(uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        policy_version=policy_version,
        tool_version=f"tieout@{__version__}",
        file_hashes=hashes,
        fee_policy=fee_policy_from_manifest(scenario),
        settlement_window=scenario["settlement_window"],
    )


def verify(manifest: RunManifest, *, root: Path | None = None) -> VerificationResult:
    base = root or Path.cwd()
    raw = raw_data_dir(base)
    mismatches: list[FileHashMismatch] = []

    for name, expected in manifest.file_hashes.items():
        path = raw / name
        if not path.exists():
            mismatches.append(FileHashMismatch(file=name, expected=expected, actual="MISSING"))
            continue
        actual = sha256_file(path)
        if actual != expected:
            mismatches.append(FileHashMismatch(file=name, expected=expected, actual=actual))

    return VerificationResult(ok=not mismatches, mismatches=mismatches)
