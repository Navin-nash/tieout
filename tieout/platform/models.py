"""The relational model -- SPEC section 3's canonical shape, made queryable.

Two rules govern this module and neither is negotiable.

**Money is NUMERIC.** :data:`MoneyColumn` is ``NUMERIC(18, 2)`` and there is no float or double
precision column anywhere in this metadata -- ``tests/test_platform_models.py`` walks
``Base.metadata`` and fails if one appears. The product thesis is exact arithmetic; a binary
float money column would quietly undo it. ``confidence`` is ``NUMERIC(5, 4)`` for the same
reason: it is compared against the 0.95 / 0.90 / 0.60 tier boundaries in SPEC section 6, and a
boundary comparison against a binary float is a defect waiting for the wrong input.

**Postgres is derived, not authoritative.** Per ADR-003 the hash-chained event log in
``tieout/audit/events.py`` stays on disk and stays the source of truth. :class:`Run` holds a
*path* to its log, never its contents. Nothing here re-implements the chain.

The auth boundary: :class:`Organisation` and :class:`Membership` **mirror** rows that Better
Auth's organization plugin owns in the Next.js app (ADR-002). Their ids are Better Auth's
strings, not UUIDs we mint. This service never writes a credential and never authenticates a
user -- it consumes an already-authenticated org id. See ``docs/PLATFORM.md``.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ── Column vocabularies ───────────────────────────────────────────────────────

#: Every money amount. 18 digits with 2 decimal places holds a quadrillion to the cent.
#: NUMERIC, never DOUBLE PRECISION -- see the module docstring.
MoneyColumn = Numeric(18, 2, asdecimal=True)

#: Confidence in [0, 1] at four decimal places. Exact, so tier boundaries compare exactly.
ConfidenceColumn = Numeric(5, 4, asdecimal=True)

#: ISO 4217. Stored beside every amount; Money is currency-tagged in the domain layer too.
CurrencyColumn = String(3)

#: Better Auth ids are opaque provider-generated strings, not UUIDs we control.
AuthIdColumn = String(64)

TimestampColumn = DateTime(timezone=True)


def _enum(py_enum: type[enum.Enum], name: str) -> Enum:
    """A VARCHAR + CHECK constraint rather than a native PG enum type.

    Same guarantee at the database, but adding a value later is one ALTER rather than the
    native-enum dance Alembic cannot autogenerate. ``# ponytail: VARCHAR+CHECK over native
    enum; switch if a column ever needs ordering.``
    """
    return Enum(
        py_enum,
        name=name,
        native_enum=False,
        # Not the default. Without it native_enum=False is a bare VARCHAR and the database
        # accepts any string, which would make the enum a Python-side convention only.
        create_constraint=True,
        values_callable=lambda e: [m.value for m in e],
    )


def _uuid_pk() -> Any:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def _created_at() -> Any:
    return mapped_column(TimestampColumn, server_default=func.now(), nullable=False)


class Base(DeclarativeBase):
    """Declarative base. ``type_annotation_map`` pins the types that matter.

    Note what is absent: ``float``. There is no mapping from a Python float to a column type,
    so annotating a column ``Mapped[float]`` is a hard error at class definition rather than a
    silently created DOUBLE PRECISION column.
    """

    type_annotation_map = {
        Decimal: MoneyColumn,
        datetime: TimestampColumn,
        uuid.UUID: Uuid(as_uuid=True),
        dict[str, Any]: JSONB,
        list[str]: JSONB,
        str: String(255),
    }


class OrgScoped:
    """Mixin that both *declares* a table as tenant data and *gives* it the tenant column.

    This class is the hook the entire isolation mechanism hangs off. ``tieout/platform/tenancy.py``
    registers ``with_loader_criteria(OrgScoped, ...)`` against every ORM statement a scoped
    session executes, so inheriting this mixin is what makes a model impossible to read, update
    or delete across tenants.

    ``org_id`` lives here rather than on each model deliberately: a table cannot end up marked
    as tenant data while missing the column the filter needs, and it cannot end up with the
    column while missing the marker. One declaration, one place to get it wrong, and it is in
    the class signature rather than in a WHERE clause three files away.
    """

    org_id: Mapped[str] = mapped_column(
        AuthIdColumn,
        ForeignKey("organisation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


# ── Enumerations (SPEC sections 3 and 6) ──────────────────────────────────────


class RunStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class OutcomeClass(enum.StrEnum):
    """SPEC section 3's outcome taxonomy, mirrored from ReconRiver's own."""

    MATCHED = "MATCHED"
    REFUND_MATCHED = "REFUND_MATCHED"
    PARTIAL_REFUND = "PARTIAL_REFUND"
    LATE_SETTLEMENT = "LATE_SETTLEMENT"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    FEE_MISMATCH = "FEE_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    MISSING_PROCESSOR = "MISSING_PROCESSOR"
    MISSING_INTERNAL = "MISSING_INTERNAL"
    MISSING_BANK_SETTLEMENT = "MISSING_BANK_SETTLEMENT"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"


class Adjudicator(enum.StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"
    HUMAN = "HUMAN"


class Tier(enum.StrEnum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class DispositionAction(enum.StrEnum):
    """Four dispositions, and there is no fifth (SPEC section 6).

    There is deliberately no ``FORCE_POST``, no ``OVERRIDE`` and no ``PLUG``. Invariant I4 is
    partly upheld here: a value that does not exist in this enum cannot be written to the
    column, because the CHECK constraint rejects it.
    """

    AUTO_POST = "AUTO_POST"
    AUTO_SAMPLED = "AUTO_SAMPLED"
    ESCALATE = "ESCALATE"
    REFUSE = "REFUSE"


class ReviewState(enum.StrEnum):
    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"
    RECLASSIFIED = "reclassified"


class HumanVerdict(enum.StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    RECLASSIFIED = "reclassified"


# ── Auth mirror (Better Auth owns the truth) ──────────────────────────────────


class Organisation(Base):
    """A tenant. The id is Better Auth's organisation id, mirrored, never minted here."""

    __tablename__ = "organisation"

    id: Mapped[str] = mapped_column(AuthIdColumn, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    #: ADR-003 demo-data honesty: a seeded org must be visibly labelled sample data in the UI.
    is_demo: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = _created_at()


class Membership(Base, OrgScoped):
    """A user's membership of an organisation, mirrored from Better Auth.

    Present so domain queries can answer "who reviewed this" and "who may act here" without a
    round trip to the Next.js app. Authorisation decisions still belong to Better Auth; this is
    a read-side mirror, and nothing in this package treats it as a credential.
    """

    __tablename__ = "membership"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_membership_org_user"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(AuthIdColumn, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    created_at: Mapped[datetime] = _created_at()


# ── Reporting entity ──────────────────────────────────────────────────────────


class Entity(Base, OrgScoped):
    """A reporting entity within an organisation.

    SPEC section 4's ``policy.yaml`` carries an ``entity`` field. Multi-entity consolidation is
    out of scope, but the column exists now so adding a second entity later is data, not a
    migration of every downstream table.
    """

    __tablename__ = "entity"
    __table_args__ = (UniqueConstraint("org_id", "code", name="uq_entity_org_code"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    functional_currency: Mapped[str] = mapped_column(CurrencyColumn, nullable=False, default="USD")
    created_at: Mapped[datetime] = _created_at()


# ── Policy provenance (SPEC section 4) ────────────────────────────────────────


class PolicyVersion(Base, OrgScoped):
    """A versioned policy document with provenance.

    SPEC section 4 requires "who set it, when, on what rationale" to survive into the product.
    Storing the whole document means a scoreboard can be recomputed against the policy that was
    actually in force at the time rather than today's.

    Policy is read-only to the agent (ADR-003). Nothing in this package writes a row here on
    behalf of a service identity; ``set_by`` is a human principal string.
    """

    __tablename__ = "policy_version"
    __table_args__ = (
        UniqueConstraint("org_id", "version", name="uq_policy_version_org_version"),
        CheckConstraint("set_by LIKE 'human:%'", name="ck_policy_version_set_by_is_human"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entity.id", ondelete="SET NULL")
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The full policy.yaml as parsed. Decimals are stored as strings inside the JSON document
    #: so a materiality threshold never round-trips through a JSON float.
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    #: Human principal, e.g. ``human:controller@acme``. Enforced by CHECK above.
    set_by: Mapped[str] = mapped_column(String(255), nullable=False)
    set_at: Mapped[datetime] = _created_at()
    superseded_at: Mapped[datetime | None] = mapped_column(TimestampColumn)


# ── Upload ────────────────────────────────────────────────────────────────────


class Upload(Base, OrgScoped):
    """One uploaded file.

    ``stored_path`` is always resolved through ``tieout/platform/storage.py``, which guarantees
    it sits inside this org's root and cannot reach ``data/holdout/``. The original filename is
    recorded for display only and is never used to build a path.
    """

    __tablename__ = "upload"
    __table_args__ = (
        Index("ix_upload_org_sha256", "org_id", "sha256"),
        CheckConstraint("byte_size >= 0", name="ck_upload_byte_size_nonneg"),
        CheckConstraint("row_count >= 0", name="ck_upload_row_count_nonneg"),
        CheckConstraint("quarantined_row_count >= 0", name="ck_upload_quarantined_nonneg"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entity.id", ondelete="SET NULL")
    )
    #: As supplied by the client. Display only -- never trusted, never joined into a path.
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    #: Path relative to the org storage root.
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    #: Rows ``tieout/ingest/reconriver.py`` rejected. Surfaced to the user with reasons.
    quarantined_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quarantine_reasons: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    uploaded_by: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_at: Mapped[datetime] = _created_at()


# ── Run ───────────────────────────────────────────────────────────────────────


class Run(Base, OrgScoped):
    """One reconcile run.

    ``event_log_path`` points at the on-disk hash-chained log for this run. ADR-003 is explicit
    that the log is not ported into tables: its canonicalisation rules and literal-digest
    regression test are the audit guarantee. This row references it; it does not replace it.
    """

    __tablename__ = "run"
    __table_args__ = (
        Index("ix_run_org_status", "org_id", "status"),
        Index("ix_run_org_period", "org_id", "period"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_run_progress_range"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entity.id", ondelete="SET NULL")
    )
    #: Accounting period, ``YYYY-MM``.
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    policy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_version.id", ondelete="RESTRICT")
    )
    #: Denormalised so a run's policy label survives even if the row is later cleaned up.
    policy_version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        _enum(RunStatus, "run_status"), nullable=False, default=RunStatus.QUEUED
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: ``run_id`` of the SHA256 manifest produced by ``tieout/ingest/manifest.py``.
    manifest_ref: Mapped[str | None] = mapped_column(String(255))
    #: Path, relative to the org storage root, of the append-only event log for this run.
    event_log_path: Mapped[str | None] = mapped_column(String(1024))
    #: External anchor for the chain tail. Without it a truncated log is a valid prefix of
    #: itself -- see ``EventLog.verify(expected_head_hash=...)``.
    event_log_head_hash: Mapped[str | None] = mapped_column(String(64))
    #: User-safe. Never a traceback, never a filesystem path. See ``jobs.safe_error_message``.
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    started_at: Mapped[datetime | None] = mapped_column(TimestampColumn)
    finished_at: Mapped[datetime | None] = mapped_column(TimestampColumn)

    work_items: Mapped[list[WorkItem]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


# ── The read model the three screens query (SPEC sections 3, 6 and 12) ────────


class WorkItem(Base, OrgScoped):
    """The unit of reconciliation, flattened for query.

    The full source rows live in the run's evidence pack, addressed by content hash. What is
    here is what screens 1 and 2 sort, filter and total by: amount for materiality ordering,
    side counts for the many-to-one shape, and the source refs for lineage.
    """

    __tablename__ = "work_item"
    __table_args__ = (
        UniqueConstraint("run_id", "work_key", name="uq_work_item_run_key"),
        Index("ix_work_item_org_run", "org_id", "run_id"),
        #: Screen 2 sorts by materiality; a descending amount index makes that a range scan.
        Index("ix_work_item_org_amount", "org_id", "amount"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("run.id", ondelete="CASCADE"), nullable=False
    )
    work_key: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Absolute size of the item, for materiality ordering. NUMERIC.
    amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(CurrencyColumn, nullable=False, default="USD")
    ledger_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bank_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Lineage back to the upstream extract (AS 1105 requirement 2): list of
    #: ``{"file": ..., "row_number": ...}`` mirroring ``ingest.schema.SourceRowRef``.
    source_row_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created_at()

    run: Mapped[Run] = relationship(back_populates="work_items")
    verdict: Mapped[Verdict | None] = relationship(
        back_populates="work_item", cascade="all, delete-orphan", uselist=False
    )


class Verdict(Base, OrgScoped):
    """SPEC section 3's ``Verdict``, persisted.

    ``features`` holds the whole :class:`FeatureVector` as JSONB with Decimal fields rendered as
    strings, matching the audit log's canonicalisation. ``amount_delta`` is additionally a real
    NUMERIC column because screens filter and total on it, and a JSONB string will not index.
    """

    __tablename__ = "verdict"
    __table_args__ = (
        UniqueConstraint("work_item_id", name="uq_verdict_work_item"),
        Index("ix_verdict_org_outcome", "org_id", "outcome_class"),
        Index("ix_verdict_org_reason", "org_id", "reason_code"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_verdict_confidence_range"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_item.id", ondelete="CASCADE"), nullable=False
    )
    work_key: Mapped[str] = mapped_column(String(255), nullable=False)
    outcome_class: Mapped[OutcomeClass] = mapped_column(
        _enum(OutcomeClass, "outcome_class"), nullable=False
    )
    reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    #: NUMERIC, not float -- compared against the T0/T1/T2 boundaries in SPEC section 6.
    confidence: Mapped[Decimal] = mapped_column(ConfidenceColumn, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    amount_delta: Mapped[Decimal] = mapped_column(
        MoneyColumn, nullable=False, default=Decimal("0.00")
    )
    fee_explained_delta: Mapped[Decimal] = mapped_column(
        MoneyColumn, nullable=False, default=Decimal("0.00")
    )
    currency: Mapped[str] = mapped_column(CurrencyColumn, nullable=False, default="USD")
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    policy_version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    adjudicator: Mapped[Adjudicator] = mapped_column(
        _enum(Adjudicator, "adjudicator"), nullable=False, default=Adjudicator.DETERMINISTIC
    )
    #: ``ev_sha256:...`` -- the content-addressed evidence pack for this decision.
    evidence_ref: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = _created_at()

    work_item: Mapped[WorkItem] = relationship(back_populates="verdict")
    disposition: Mapped[Disposition | None] = relationship(
        back_populates="verdict", cascade="all, delete-orphan", uselist=False
    )


class Disposition(Base, OrgScoped):
    """SPEC section 6's tiering, plus the review state screen 2 acts on.

    The review columns live here rather than in a separate table because a disposition has at
    most one open review at a time and the queue query is "dispositions where state is open".
    ``# ponytail: review state on the disposition row; split into a review table if an item
    ever needs a review history rather than a current state.``

    Four-eyes (AS 1105 requirement 3) is enforced by ``tieout/audit/identity.py`` at write time
    and mirrored by ``ck_disposition_four_eyes`` here, so a direct SQL write cannot record a
    self-approval either.
    """

    __tablename__ = "disposition"
    __table_args__ = (
        UniqueConstraint("verdict_id", name="uq_disposition_verdict"),
        Index("ix_disposition_org_queue", "org_id", "review_state", "blocking"),
        Index("ix_disposition_org_action", "org_id", "action"),
        CheckConstraint(
            "reviewed_by IS NULL OR approved_by IS NULL OR reviewed_by <> approved_by",
            name="ck_disposition_four_eyes",
        ),
        #: I4, restated at the database. A REFUSE is never a posting action, and no row may
        #: claim REFUSE while declaring itself non-blocking.
        CheckConstraint(
            "action <> 'REFUSE' OR blocking IS TRUE",
            name="ck_disposition_refuse_is_blocking",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    verdict_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("verdict.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tier: Mapped[Tier] = mapped_column(_enum(Tier, "tier"), nullable=False)
    action: Mapped[DispositionAction] = mapped_column(
        _enum(DispositionAction, "disposition_action"), nullable=False
    )
    blocking: Mapped[bool] = mapped_column(nullable=False, default=False)
    triggers: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    #: Denormalised from the work item so the queue sorts by materiality without a join.
    amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(CurrencyColumn, nullable=False, default="USD")

    review_state: Mapped[ReviewState] = mapped_column(
        _enum(ReviewState, "review_state"), nullable=False, default=ReviewState.OPEN
    )
    #: Human principals, e.g. ``human:controller@acme``.
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(TimestampColumn)
    review_note: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(TimestampColumn)
    #: Set when the human reclassified rather than approved or rejected.
    reclassified_to: Mapped[OutcomeClass | None] = mapped_column(
        _enum(OutcomeClass, "outcome_class")
    )
    #: The prior decision cited in the recommendation, if any (SPEC section 9).
    cited_prior_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prior_decision.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _created_at()

    verdict: Mapped[Verdict] = relationship(back_populates="disposition")


# ── Decision memory (SPEC section 9) ──────────────────────────────────────────


class PriorDecision(Base, OrgScoped):
    """A human's judgment, replayable. Never a machine's.

    SPEC section 9: memory may *accelerate* a decision, never *create admissibility*. Nothing
    in this table can promote a REFUSE, and the column set makes that visible -- there is no
    tier, no action and no ``overrides`` field. A prior decision is evidence to cite, not a
    permission to post.
    """

    __tablename__ = "prior_decision"
    __table_args__ = (
        #: Section 9's algorithm: exact-match bucket on reason code, then nearest neighbour
        #: over normalised features within the bucket. This index is that bucket.
        Index("ix_prior_decision_org_reason", "org_id", "reason_code"),
        CheckConstraint("decided_by LIKE 'human:%'", name="ck_prior_decision_human_only"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome_class: Mapped[OutcomeClass] = mapped_column(
        _enum(OutcomeClass, "outcome_class"), nullable=False
    )
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    amount_delta: Mapped[Decimal] = mapped_column(
        MoneyColumn, nullable=False, default=Decimal("0.00")
    )
    currency: Mapped[str] = mapped_column(CurrencyColumn, nullable=False, default="USD")
    human_verdict: Mapped[HumanVerdict] = mapped_column(
        _enum(HumanVerdict, "human_verdict"), nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    #: Human principal. Enforced by CHECK -- a service identity cannot seed the memory.
    decided_by: Mapped[str] = mapped_column(String(255), nullable=False)
    decided_at: Mapped[datetime] = _created_at()
    #: Where the decision came from, for the "who and when" the queue displays.
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("run.id", ondelete="SET NULL")
    )
    source_work_key: Mapped[str | None] = mapped_column(String(255))


# ── Background jobs (ADR-003: Postgres-backed, no Redis) ──────────────────────


class Job(Base, OrgScoped):
    """A unit of background work claimed with ``SELECT ... FOR UPDATE SKIP LOCKED``.

    ``# ponytail: single polling worker, SKIP LOCKED claim. Fine to ~1 run/sec.``
    ``# Run N workers if throughput matters -- the claim is already safe.``
    """

    __tablename__ = "job"
    __table_args__ = (
        #: The claim query's index: status, then availability, then FIFO.
        Index("ix_job_claim", "status", "available_at", "created_at"),
        Index("ix_job_org_status", "org_id", "status"),
        CheckConstraint("attempts >= 0", name="ck_job_attempts_nonneg"),
        CheckConstraint("max_attempts >= 1", name="ck_job_max_attempts_positive"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_job_progress_range"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    #: Handler key, resolved against ``tieout.platform.jobs.JOB_HANDLERS``.
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[JobStatus] = mapped_column(
        _enum(JobStatus, "job_status"), nullable=False, default=JobStatus.QUEUED
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Safe to render to a user: no traceback, no filesystem path, no connection string.
    error_message: Mapped[str | None] = mapped_column(Text)
    #: Set on failure so a retry is delayed rather than spun on. A job at max attempts is
    #: terminal and is never made available again.
    available_at: Mapped[datetime] = _created_at()
    claimed_at: Mapped[datetime | None] = mapped_column(TimestampColumn)
    claimed_by: Mapped[str | None] = mapped_column(String(128))
    finished_at: Mapped[datetime | None] = mapped_column(TimestampColumn)
    created_at: Mapped[datetime] = _created_at()


#: Every tenant-scoped model. Used by the tenancy tests and by ``docs/PLATFORM.md``.
TENANT_MODELS: tuple[type[Base], ...] = (
    Entity,
    PolicyVersion,
    Upload,
    Run,
    WorkItem,
    Verdict,
    Disposition,
    PriorDecision,
    Job,
    Membership,
)
