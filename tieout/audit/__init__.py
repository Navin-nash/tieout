"""Hash-chained append-only event log, evidence packs and four-eyes identity (SPEC section 8).

Public API -- see docs/AUDIT.md. There is no update path and no delete path, by design.
"""

from tieout.audit.events import (
    ChainBreak,
    ChainStatus,
    Event,
    EventLog,
    canonical,
    canonical_json,
    chain_hash,
)
from tieout.audit.evidence import (
    EvidencePack,
    EvidenceStore,
    EvidenceTampered,
    ReviewAction,
    build_pack,
)
from tieout.audit.identity import (
    Approval,
    DecisionTimestamps,
    FourEyesViolation,
    HumanIdentity,
    Identity,
    ServiceIdentity,
    to_utc_iso,
    utc_now,
)

__all__ = [
    "Approval",
    "ChainBreak",
    "ChainStatus",
    "DecisionTimestamps",
    "Event",
    "EventLog",
    "EvidencePack",
    "EvidenceStore",
    "EvidenceTampered",
    "FourEyesViolation",
    "HumanIdentity",
    "Identity",
    "ReviewAction",
    "ServiceIdentity",
    "build_pack",
    "canonical",
    "canonical_json",
    "chain_hash",
    "to_utc_iso",
    "utc_now",
]
