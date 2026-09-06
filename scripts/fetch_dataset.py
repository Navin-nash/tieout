"""Fetch the ReconRiver `month-end-close` scenario and split it into raw/holdout.

Dataset: heybadrinath/reconriver-synthetic-reconciliation (CC BY 4.0) on Hugging Face.

Layout produced (both gitignored, never committed):
    data/raw/internal_transactions.csv
    data/raw/processor_transactions.csv
    data/raw/bank_settlements.csv
    data/raw/scenario_manifest.json
    data/holdout/expected_reconciliation.csv   <- ground truth, agent-readable set excludes this

The holdout/raw split is an architectural constraint (SPEC.md section 3): the scorer reads
`expected_reconciliation.csv` out-of-process; the agent's ingest code must never see it.

Idempotent: huggingface_hub caches downloads by content hash, so re-running is cheap and safe.
After every fetch, each file's SHA256 is checked against `scenario_manifest.json`'s own
checksums -- if the upstream dataset changes without our knowledge, this fails loudly instead
of silently ingesting a different schema (SPEC.md section 19: "fail loudly on a schema change,
never coerce").
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import pandas as pd
from huggingface_hub import hf_hub_download
from huggingface_hub.utils import HfHubHTTPError

REPO_ID = "heybadrinath/reconriver-synthetic-reconciliation"
SCENARIO = "month-end-close"
REPO_PREFIX = f"generated/{SCENARIO}"

RAW_DIR = Path("data/raw")
HOLDOUT_DIR = Path("data/holdout")

# filename -> destination directory
FILES = {
    "internal_transactions.csv": RAW_DIR,
    "processor_transactions.csv": RAW_DIR,
    "bank_settlements.csv": RAW_DIR,
    "scenario_manifest.json": RAW_DIR,
    "expected_reconciliation.csv": HOLDOUT_DIR,  # ground truth -- holdout, not raw
}


def fetch_all() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    HOLDOUT_DIR.mkdir(parents=True, exist_ok=True)

    for filename, dest_dir in FILES.items():
        remote_path = f"{REPO_PREFIX}/{filename}"
        try:
            cached_path = hf_hub_download(REPO_ID, remote_path, repo_type="dataset")
        except HfHubHTTPError as exc:
            raise RuntimeError(
                f"Could not fetch '{remote_path}' from '{REPO_ID}'. The dataset or the "
                f"'{SCENARIO}' scenario folder may have moved or been renamed upstream -- "
                f"check https://huggingface.co/datasets/{REPO_ID} before re-running."
            ) from exc
        shutil.copy(cached_path, dest_dir / filename)
        print(f"fetched {remote_path} -> {dest_dir / filename}")


def verify_checksums() -> None:
    import json

    manifest = json.loads((RAW_DIR / "scenario_manifest.json").read_text(encoding="utf-8"))
    claimed = manifest["file_sha256_checksums"]

    checks = {
        "internal_transactions.csv": RAW_DIR / "internal_transactions.csv",
        "processor_transactions.csv": RAW_DIR / "processor_transactions.csv",
        "bank_settlements.csv": RAW_DIR / "bank_settlements.csv",
        "expected_reconciliation.csv": HOLDOUT_DIR / "expected_reconciliation.csv",
    }

    mismatches = []
    for name, path in checks.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = claimed.get(name)
        if expected is None:
            mismatches.append(f"{name}: manifest has no checksum recorded")
        elif actual != expected:
            mismatches.append(f"{name}: expected {expected}, got {actual}")
        else:
            print(f"checksum OK: {name}")

    if mismatches:
        raise RuntimeError(
            "SHA256 mismatch against scenario_manifest.json -- the dataset content has "
            "changed upstream since this pipeline was verified. Do NOT coerce; re-verify "
            "the schema (see docs/DATASET.md) before trusting downstream ingest.\n"
            + "\n".join(mismatches)
        )


def report_actuals() -> None:
    print("\n--- actual row counts ---")
    for name, dest_dir in [
        ("internal_transactions.csv", RAW_DIR),
        ("processor_transactions.csv", RAW_DIR),
        ("bank_settlements.csv", RAW_DIR),
        ("expected_reconciliation.csv", HOLDOUT_DIR),
    ]:
        df = pd.read_csv(dest_dir / name)
        print(f"{name}: {len(df)} rows, columns={list(df.columns)}")


def main() -> int:
    fetch_all()
    verify_checksums()
    report_actuals()
    print(
        "\nOK -- month-end-close fetched, split into data/raw/ and "
        "data/holdout/, checksums verified."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
