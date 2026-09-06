"""Content-addressed evidence packs (AS 1105 requirements 2 and 6).

One bundle per decision, holding the six things docs/SPEC.md section 8 lists. The pack id is
a hash of the pack's contents, so an event that references ``ev_sha256:...`` pins exactly one
possible pack: substituting a different pack changes its id and the reference dangles.

"Show your work" is therefore a property of the system, not a report someone assembles later.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from tieout.audit.events import canonical_json
from tieout.audit.identity import DecisionTimestamps, HumanIdentity

#: Lineage field carried by every ingested row (see tieout/ingest/schema.py).
SOURCE_ROW_REF = "source_row_ref"

PACK_ID_PREFIX = "ev_sha256:"

#: Excluded from the pack's own hash input, for the same reason ``hash`` is on an event.
PACK_CANON_EXCLUDED: tuple[str, ...] = ("pack_id",)


class EvidenceTampered(ValueError):
    """A stored pack does not hash to the id it was filed under."""


def _row_ref_text(ref: Any) -> str | None:
    """Render a ``source_row_ref`` as text, or None if it is not usable lineage.

    Accepts both shapes a caller can hold: a plain string, or the dumped
    ``tieout.ingest.schema.SourceRowRef`` -- ``{"file": ..., "row_number": ...}`` -- which is
    what ``LedgerEntry.model_dump()`` produces. Rendered as ``<file>#L<row_number>``.
    """
    if isinstance(ref, str):
        return ref or None
    if isinstance(ref, Mapping):
        file, row_number = ref.get("file"), ref.get("row_number")
        if isinstance(file, str) and file and isinstance(row_number, int):
            return f"{file}#L{row_number}"
    return None


class ReviewAction(BaseModel):
    """The reviewer action, with identity and timestamp (requirement 6, last bullet)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reviewer: HumanIdentity
    action: str
    at: datetime
    note: str = ""


class EvidencePack(BaseModel):
    """The six-part bundle behind one decision.

    Lineage: each row in ``source_rows`` must carry its ``source_row_ref``, which resolves to
    a file plus row number, and the file's SHA256 lives in the run manifest. A pack therefore
    traces back to bytes on disk that were hashed at ingest time.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    work_key: str
    # 1 -- the candidate source rows, verbatim
    source_rows: tuple[dict[str, Any], ...]
    # 2 -- the computed feature vector
    features: dict[str, Any]
    # 3 -- the policy version and the specific thresholds applied
    policy_version: str
    thresholds: dict[str, Any]
    # 4 -- the disposition and rationale
    disposition: str
    rationale: str
    # 5 -- any cited prior human decision
    cited_decision_id: str | None = None
    # 6 -- the reviewer action with identity and timestamp
    review: ReviewAction | None = None
    timestamps: DecisionTimestamps

    @model_validator(mode="after")
    def _lineage_present(self) -> EvidencePack:
        for index, row in enumerate(self.source_rows):
            if _row_ref_text(row.get(SOURCE_ROW_REF)) is None:
                raise ValueError(
                    f"source_rows[{index}] has no usable {SOURCE_ROW_REF}; lineage back to the "
                    "upstream extract is not optional (AS 1105 requirement 2)"
                )
        return self

    @property
    def source_row_refs(self) -> tuple[str, ...]:
        """Every row reference in the pack, in order -- the lineage chain to the manifest."""
        return tuple(str(_row_ref_text(row[SOURCE_ROW_REF])) for row in self.source_rows)

    @property
    def pack_id(self) -> str:
        """``ev_sha256:<hex>`` over the canonical form of the pack contents."""
        payload = {k: v for k, v in self.model_dump().items() if k not in PACK_CANON_EXCLUDED}
        digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return f"{PACK_ID_PREFIX}{digest}"


class EvidenceStore:
    """One file per pack, named by its own content hash. Writes are idempotent, never updates."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path_for(self, pack_id: str) -> Path:
        if not pack_id.startswith(PACK_ID_PREFIX):
            raise ValueError(f"not an evidence pack id: {pack_id!r}")
        return self.root / f"{pack_id.removeprefix(PACK_ID_PREFIX)}.json"

    def put(self, pack: EvidencePack) -> str:
        """Write the pack under its content hash and return the id to cite in the event log."""
        pack_id = pack.pack_id
        path = self.path_for(pack_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v for k, v in pack.model_dump().items() if k not in PACK_CANON_EXCLUDED}
        path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
        return pack_id

    def get(self, pack_id: str) -> EvidencePack:
        """Load a pack and prove it is the one that was filed. Raises on substitution."""
        pack = EvidencePack(**json.loads(self.path_for(pack_id).read_text(encoding="utf-8")))
        if pack.pack_id != pack_id:
            raise EvidenceTampered(
                f"evidence pack substituted: filed as {pack_id}, contents hash to {pack.pack_id}"
            )
        return pack

    def verify(self, pack_id: str) -> bool:
        """True if the stored pack still hashes to its id."""
        try:
            self.get(pack_id)
        except (EvidenceTampered, FileNotFoundError):
            return False
        return True


def build_pack(
    *,
    work_key: str,
    source_rows: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    features: Mapping[str, Any],
    policy_version: str,
    thresholds: Mapping[str, Any],
    disposition: str,
    rationale: str,
    timestamps: DecisionTimestamps,
    cited_decision_id: str | None = None,
    review: ReviewAction | None = None,
) -> EvidencePack:
    """Assemble a pack from loose mappings. Convenience only; the model is the contract."""
    return EvidencePack(
        work_key=work_key,
        source_rows=tuple(dict(row) for row in source_rows),
        features=dict(features),
        policy_version=policy_version,
        thresholds=dict(thresholds),
        disposition=disposition,
        rationale=rationale,
        timestamps=timestamps,
        cited_decision_id=cited_decision_id,
        review=review,
    )
