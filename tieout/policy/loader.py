"""Load, validate and version-resolve `policy.yaml`. Reject rather than coerce.

Three things happen here that a config loader does not do:

1. YAML scalars that look like numbers are constructed as `Decimal`, never `float`, so a money
   value cannot lose cents on the way in (PLAN standing rule 3).
2. The fee policy is read from the ReconRiver scenario manifest at load time. SPEC section 19
   makes the manifest authoritative and the spec's own literals advisory, so `policy.yaml`
   declares a source, not numbers.
3. Version resolution: several policy versions can coexist, and a period resolves to the one in
   force at the time, so a scoreboard can be recomputed under the policy that actually applied
   (SPEC section 4, closing paragraph).
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from tieout.policy.schema import FeePolicy, Policy, Threshold

DEFAULT_POLICY_PATH = Path("policy.yaml")
DEFAULT_MANIFEST_PATH = Path("data/raw/scenario_manifest.json")


class PolicyError(Exception):
    """A policy file is invalid, inconsistent, or violates AS 2105. Loading fails; nothing is
    coerced into shape."""


class PolicyRefusal(Exception):
    """A policy field required for this action has not been set by a human.

    Distinct from `PolicyError`: the policy is well-formed, but it is deliberately silent on
    this point and the system will not invent a value. See `require_write_off_authority`.
    """


# --- YAML: numbers arrive as Decimal ------------------------------------------------------


class _DecimalSafeLoader(yaml.SafeLoader):
    """SafeLoader that constructs YAML floats as `Decimal`.

    `yaml.safe_load` turns `750000.00` into a Python float, which would put a binary float in
    front of a money field before pydantic ever sees it. Rewriting the constructor is the whole
    fix; the string form of the scalar is preserved exactly.
    """


def _construct_decimal(loader: yaml.SafeLoader, node: yaml.Node) -> Decimal:
    raw = loader.construct_scalar(node)  # type: ignore[arg-type]
    try:
        return Decimal(str(raw))
    except InvalidOperation as exc:  # .inf / .nan and friends
        raise PolicyError(f"'{raw}' is not a usable decimal value in a policy file") from exc


_DecimalSafeLoader.add_constructor("tag:yaml.org,2002:float", _construct_decimal)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyError(f"cannot read policy file '{path}': {exc}") from exc
    try:
        data = yaml.load(text, Loader=_DecimalSafeLoader)
    except yaml.YAMLError as exc:
        raise PolicyError(f"'{path}' is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyError(
            f"'{path}' must contain a mapping at the top level, got {type(data).__name__}"
        )
    return data


# --- fee policy comes from the manifest, not from the spec --------------------------------


def _percent_to_fraction(raw: str) -> Decimal:
    """`"2.90%"` -> `Decimal("0.0290")`. A bare number is taken as already a fraction."""
    text = str(raw).strip()
    if text.endswith("%"):
        return Decimal(text[:-1].strip()) / Decimal(100)
    return Decimal(text)


def load_fee_policy(manifest_path: Path = DEFAULT_MANIFEST_PATH) -> FeePolicy | None:
    """Read `fee_policy` from the scenario manifest. Returns None if the manifest is absent.

    Absent means the dataset has not been fetched (`python scripts/fetch_dataset.py`). We return
    None rather than falling back to SPEC section 4's literals, because a silent fallback to a
    number nobody verified is exactly the failure this indirection exists to prevent.
    """
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"scenario manifest '{manifest_path}' is unreadable: {exc}") from exc

    try:
        fee = manifest["fee_policy"]
        version = manifest.get("generator_version", "unknown")
        return FeePolicy(
            pct=_percent_to_fraction(fee["percentage_rate"]),
            fixed=Decimal(str(fee["fixed_charge"])),
            rounding=fee["rounding_mode"],
            source=f"{manifest_path} (generator_version {version})",
        )
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise PolicyError(
            f"scenario manifest '{manifest_path}' has no usable fee_policy block: {exc}. "
            "The manifest is authoritative (SPEC section 19); this is not recoverable by "
            "falling back to the spec's literals."
        ) from exc
    except ValidationError as exc:
        raise PolicyError(f"fee_policy in '{manifest_path}' failed validation: {exc}") from exc


# --- loading ------------------------------------------------------------------------------


def build_policy(data: dict[str, Any], fee_policy: FeePolicy | None) -> Policy:
    """Validate one already-parsed policy mapping. Kept separate so tests need no files."""
    payload = dict(data)
    declared = payload.pop("fee_policy", None)
    if declared is not None and declared != {"source": "scenario_manifest"}:
        raise PolicyError(
            "policy.yaml must not carry fee_policy literals. Declare "
            "`fee_policy: {source: scenario_manifest}` -- SPEC section 19 makes the scenario "
            "manifest authoritative for these values."
        )
    try:
        return Policy(**payload, fee_policy=fee_policy)
    except ValidationError as exc:
        raise PolicyError(f"policy failed validation:\n{exc}") from exc


def load_policy(
    path: Path = DEFAULT_POLICY_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> Policy:
    """Load and fully validate a single policy version."""
    return build_policy(_read_yaml(path), load_fee_policy(manifest_path))


def load_policies(
    paths: list[Path],
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> tuple[Policy, ...]:
    """Load several versions at once. The fee policy is resolved once and shared."""
    fee = load_fee_policy(manifest_path)
    return tuple(build_policy(_read_yaml(p), fee) for p in paths)


# --- required-but-unset fields refuse -----------------------------------------------------


def require_fee_policy(policy: Policy) -> FeePolicy:
    """Fee terms or a refusal -- never an assumed 2.90% + 0.30."""
    if policy.fee_policy is None:
        raise PolicyRefusal(
            "fee policy is unresolved: the scenario manifest was not found, and the spec's "
            "literals are advisory only (SPEC section 19). Run `python scripts/fetch_dataset.py` "
            "so the manifest can be read at load time."
        )
    return policy.fee_policy


def require_write_off_authority(policy: Policy) -> Threshold:
    """Refuse until a human sets it. There is no default and there will not be one.

    SPEC section 10: no public policy publishes a dollar write-off authority threshold -- they
    live in internal delegation-of-authority manuals. Inventing a number here would be the
    system asserting an authority nobody granted it.
    """
    if policy.write_off_authority is None:
        raise PolicyRefusal(
            f"policy '{policy.version}' sets no write-off authority, and this system ships no "
            "default for it. A write-off delegation is an internal authority a human must grant, "
            "with a basis, an attributed setter and a rationale, before any item can be written "
            "off under it."
        )
    return policy.write_off_authority


# --- version resolution -------------------------------------------------------------------


def _check_chain(policies: tuple[Policy, ...]) -> None:
    by_version = {p.version: p for p in policies}
    if len(by_version) != len(policies):
        raise PolicyError(f"duplicate policy versions: {[p.version for p in policies]}")

    by_date: dict[date, str] = {}
    for p in policies:
        if p.effective_from in by_date:
            raise PolicyError(
                f"policies '{by_date[p.effective_from]}' and '{p.version}' share "
                f"effective_from {p.effective_from}; which one is in force is undecidable."
            )
        by_date[p.effective_from] = p.version

    entities = {p.entity for p in policies}
    if len(entities) > 1:
        raise PolicyError(f"cannot resolve across entities in one set: {sorted(entities)}")

    for p in policies:
        if p.supersedes is None:
            continue
        prior = by_version.get(p.supersedes)
        if prior is None:
            raise PolicyError(
                f"policy '{p.version}' supersedes '{p.supersedes}', which is not in this set. "
                "A broken supersession chain cannot be resolved against a historical period."
            )
        if prior.effective_from >= p.effective_from:
            raise PolicyError(
                f"policy '{p.version}' (effective {p.effective_from}) supersedes "
                f"'{prior.version}' (effective {prior.effective_from}) but does not follow it."
            )


def resolve_for_date(policies: tuple[Policy, ...], on: date) -> Policy:
    """The policy in force on a given date: the latest one effective on or before it."""
    if not policies:
        raise PolicyError("no policies supplied to resolve against")
    _check_chain(policies)
    in_force = [p for p in policies if p.effective_from <= on]
    if not in_force:
        earliest = min(p.effective_from for p in policies)
        raise PolicyError(
            f"no policy was in force on {on}; the earliest available takes effect {earliest}. "
            "A decision cannot be governed by a policy that did not exist yet."
        )
    return max(in_force, key=lambda p: p.effective_from)


def resolve_for_period(policies: tuple[Policy, ...], period: str) -> Policy:
    """The policy in force for an accounting period given as `YYYY-MM`.

    Resolved at the *first* day of the period. A threshold changed mid-period does not
    retroactively regovern items already decided under the previous version; the new version
    governs from the next period. Every decision also records its own `policy_version`, so a
    recomputation can pin the exact version rather than re-deriving it.
    """
    try:
        year, month = (int(part) for part in period.split("-", 1))
        start = date(year, month, 1)
    except (ValueError, TypeError) as exc:
        raise PolicyError(f"period '{period}' is not in YYYY-MM form") from exc
    return resolve_for_date(policies, start)
