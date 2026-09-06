"""Tenant isolation is a security boundary. These tests are the proof.

ADR-003 requires that org A cannot read, review or close org B's data. The dangerous case is
not the accidental unfiltered list query -- it is the caller who *knows* another org's row id
and asks for it directly, because that is what an enumeration attack looks like and it is what
a WHERE clause added by habit tends to miss. Every read assertion below is therefore run twice:
once as a list query, and once with org B's primary key supplied by hand.

The write side is asserted too. A leak that only goes one way is still a leak: being able to
approve another tenant's exception is worse than being able to read it.
"""

# ruff: noqa: E402
# The pytest.importorskip guard below must run before the tieout.platform imports.

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

# The platform layer needs sqlalchemy, psycopg and pydantic-settings. Those are not in
# pyproject.toml yet -- that file is owned by another worker and this one only reports the
# requirement (see docs/PLATFORM.md, "Dependencies"). Until they land, skip this module loudly
# instead of failing collection and turning the whole suite red.
pytest.importorskip("sqlalchemy", reason="sqlalchemy is not installed; see docs/PLATFORM.md")
pytest.importorskip(
    "pydantic_settings", reason="pydantic-settings is not installed; see docs/PLATFORM.md"
)

from sqlalchemy import delete, func, select, update

from tieout.platform.models import (
    Adjudicator,
    Disposition,
    DispositionAction,
    Entity,
    Job,
    OutcomeClass,
    PolicyVersion,
    PriorDecision,
    ReviewState,
    Run,
    RunStatus,
    Tier,
    Upload,
    Verdict,
    WorkItem,
)
from tieout.platform.session import (
    UNSCOPED_REASONS,
    UnscopedAccessError,
    unscoped_session,
)
from tieout.platform.tenancy import (
    CrossTenantWriteError,
    OrgScope,
    TenantScopeError,
    tenant_session,
)
from tieout.platform.testing import requires_db, run, two_orgs

pytestmark = requires_db


def scope(org_id: str, actor: str = "human:controller@acme") -> OrgScope:
    return OrgScope(org_id=org_id, actor=actor)


async def seed(org_id: str) -> dict[str, uuid.UUID]:
    """One row in every tenant table, for one org. Returns the ids for direct-id probing."""
    async with tenant_session(scope(org_id)) as session:
        entity = Entity(code="MAIN", name="Main entity", functional_currency="USD")
        policy = PolicyVersion(
            version="2026.01-r3",
            document={"performance_materiality": "50000.00"},
            rationale="illustrative figures, ReconRiver sample data",
            set_by="human:controller@acme",
        )
        session.add_all([entity, policy])
        await session.flush()

        upload = Upload(
            entity_id=entity.id,
            filename="internal_transactions.csv",
            stored_path="uploads/deadbeef.csv",
            sha256="a" * 64,
            byte_size=1024,
            row_count=10_000,
            content_type="text/csv",
            uploaded_by="human:controller@acme",
        )
        run_row = Run(
            entity_id=entity.id,
            period="2026-01",
            policy_version_id=policy.id,
            policy_version_label="2026.01-r3",
            status=RunStatus.COMPLETED,
            progress=100,
            event_log_path="runs/x/events.jsonl",
        )
        prior = PriorDecision(
            reason_code="L2_TWO_CANDIDATES_WITHIN_TOLERANCE",
            outcome_class=OutcomeClass.AMBIGUOUS_MATCH,
            human_verdict="rejected",
            rationale="two admissible candidates; refused",
            decided_by="human:controller@acme",
            amount_delta=Decimal("120.55"),
        )
        session.add_all([upload, run_row, prior])
        await session.flush()

        work_item = WorkItem(
            run_id=run_row.id,
            work_key="wk_batch_4471",
            amount=Decimal("14231.99"),
            ledger_count=3,
            processor_count=3,
            bank_count=1,
        )
        session.add(work_item)
        await session.flush()

        verdict = Verdict(
            work_item_id=work_item.id,
            work_key="wk_batch_4471",
            outcome_class=OutcomeClass.AMBIGUOUS_MATCH,
            reason_code="L2_TWO_CANDIDATES_WITHIN_TOLERANCE",
            confidence=Decimal("0.4200"),
            rationale="two candidates within tolerance",
            candidate_count=2,
            policy_version_label="2026.01-r3",
            adjudicator=Adjudicator.DETERMINISTIC,
        )
        session.add(verdict)
        await session.flush()

        disposition = Disposition(
            verdict_id=verdict.id,
            run_id=run_row.id,
            tier=Tier.T3,
            action=DispositionAction.REFUSE,
            blocking=True,
            triggers=["I3_AMBIGUITY"],
            amount=Decimal("14231.99"),
            review_state=ReviewState.OPEN,
        )
        job = Job(kind="reconcile", run_id=run_row.id, payload={"period": "2026-01"})
        session.add_all([disposition, job])
        await session.commit()

        return {
            "entity": entity.id,
            "policy_version": policy.id,
            "upload": upload.id,
            "run": run_row.id,
            "prior_decision": prior.id,
            "work_item": work_item.id,
            "verdict": verdict.id,
            "disposition": disposition.id,
            "job": job.id,
        }


#: Every tenant table, with the key that :func:`seed` returns for it.
TENANT_CASES = [
    ("run", Run),
    ("work_item", WorkItem),
    ("verdict", Verdict),
    ("disposition", Disposition),
    ("prior_decision", PriorDecision),
    ("upload", Upload),
    ("policy_version", PolicyVersion),
    ("entity", Entity),
    ("job", Job),
]


# ── Reads ─────────────────────────────────────────────────────────────────────


def test_org_a_sees_none_of_org_b_rows_in_a_list_query() -> None:
    async def body() -> None:
        async with two_orgs() as (a, b):
            await seed(a)
            await seed(b)
            for name, model in TENANT_CASES:
                async with tenant_session(scope(a)) as session:
                    rows = (await session.execute(select(model))).scalars().all()
                assert rows, f"org A should see its own {name}"
                assert {r.org_id for r in rows} == {a}, f"{name} leaked across tenants"

    run(body())


@pytest.mark.parametrize(("name", "model"), TENANT_CASES, ids=[n for n, _ in TENANT_CASES])
def test_org_a_cannot_read_org_b_row_by_its_primary_key(name: str, model: type) -> None:
    """The case that actually leaks: the caller supplies the other tenant's id directly."""

    async def body() -> None:
        async with two_orgs() as (a, b):
            await seed(a)
            b_ids = await seed(b)
            victim = b_ids[name]

            async with tenant_session(scope(a)) as session:
                by_select = (
                    (await session.execute(select(model).where(model.id == victim)))
                    .scalars()
                    .first()
                )
                assert by_select is None, f"{name}: org A read org B's row via an explicit id"

                by_get = await session.get(model, victim)
                assert by_get is None, f"{name}: org A read org B's row via Session.get"

                counted = (
                    await session.execute(
                        select(func.count()).select_from(model).where(model.id == victim)
                    )
                ).scalar_one()
                assert counted == 0, f"{name}: org B's row is countable from org A"

            # ... and the row does exist, so the assertions above are not vacuous.
            async with tenant_session(scope(b)) as session:
                assert await session.get(model, victim) is not None

    run(body())


def test_a_join_does_not_reopen_the_boundary() -> None:
    """Filtering only the primary entity would let a join drag the other tenant's rows back."""

    async def body() -> None:
        async with two_orgs() as (a, b):
            await seed(a)
            b_ids = await seed(b)
            async with tenant_session(scope(a)) as session:
                rows = (
                    (
                        await session.execute(
                            select(Disposition)
                            .join(Verdict, Verdict.id == Disposition.verdict_id)
                            .join(WorkItem, WorkItem.id == Verdict.work_item_id)
                            .where(WorkItem.id == b_ids["work_item"])
                        )
                    )
                    .scalars()
                    .all()
                )
            assert rows == []

    run(body())


def test_relationship_traversal_stays_inside_the_tenant() -> None:
    async def body() -> None:
        async with two_orgs() as (a, b):
            await seed(a)
            await seed(b)
            async with tenant_session(scope(a)) as session:
                runs = (await session.execute(select(Run).options())).scalars().all()
                for r in runs:
                    items = (
                        (await session.execute(select(WorkItem).where(WorkItem.run_id == r.id)))
                        .scalars()
                        .all()
                    )
                    assert all(i.org_id == a for i in items)

    run(body())


# ── Review and close: the write side of the same boundary ─────────────────────


def test_org_a_cannot_review_org_b_queue_item_even_with_its_id() -> None:
    """Approving another tenant's exception is worse than reading it."""

    async def body() -> None:
        async with two_orgs() as (a, b):
            await seed(a)
            b_ids = await seed(b)
            victim = b_ids["disposition"]

            async with tenant_session(scope(a)) as session:
                result = await session.execute(
                    update(Disposition)
                    .where(Disposition.id == victim)
                    .values(
                        review_state=ReviewState.APPROVED,
                        reviewed_by="human:attacker@evil",
                        reviewed_at=datetime.now(UTC),
                    )
                )
                assert result.rowcount == 0, "org A updated org B's disposition"
                await session.commit()

            async with tenant_session(scope(b)) as session:
                still = await session.get(Disposition, victim)
                assert still is not None
                assert still.review_state is ReviewState.OPEN
                assert still.reviewed_by is None

    run(body())


def test_org_a_cannot_close_org_b_run_even_with_its_id() -> None:
    async def body() -> None:
        async with two_orgs() as (a, b):
            await seed(a)
            b_ids = await seed(b)
            victim = b_ids["run"]

            async with tenant_session(scope(a)) as session:
                result = await session.execute(
                    update(Run).where(Run.id == victim).values(status=RunStatus.FAILED)
                )
                assert result.rowcount == 0, "org A changed the state of org B's run"
                await session.commit()

            async with tenant_session(scope(b)) as session:
                assert (await session.get(Run, victim)).status is RunStatus.COMPLETED

    run(body())


@pytest.mark.parametrize(("name", "model"), TENANT_CASES, ids=[n for n, _ in TENANT_CASES])
def test_org_a_cannot_delete_org_b_rows(name: str, model: type) -> None:
    async def body() -> None:
        async with two_orgs() as (a, b):
            await seed(a)
            b_ids = await seed(b)
            victim = b_ids[name]

            async with tenant_session(scope(a)) as session:
                result = await session.execute(delete(model).where(model.id == victim))
                assert result.rowcount == 0, f"org A deleted org B's {name}"
                await session.commit()

            async with tenant_session(scope(b)) as session:
                assert await session.get(model, victim) is not None

    run(body())


def test_a_row_cannot_be_inserted_into_another_tenant() -> None:
    async def body() -> None:
        async with two_orgs() as (a, b):
            async with tenant_session(scope(a)) as session:
                session.add(Entity(org_id=b, code="SMUGGLED", name="belongs to B"))
                with pytest.raises(CrossTenantWriteError):
                    await session.flush()

    run(body())


def test_org_id_is_stamped_automatically_so_it_cannot_be_forgotten() -> None:
    async def body() -> None:
        async with two_orgs() as (a, _b):
            async with tenant_session(scope(a)) as session:
                entity = Entity(code="AUTO", name="no org_id supplied")
                session.add(entity)
                await session.flush()
                assert entity.org_id == a
                await session.rollback()

    run(body())


def test_a_row_cannot_be_moved_between_tenants_by_mutating_org_id() -> None:
    async def body() -> None:
        async with two_orgs() as (a, b):
            ids = await seed(a)
            async with tenant_session(scope(a)) as session:
                entity = await session.get(Entity, ids["entity"])
                assert entity is not None
                entity.org_id = b
                with pytest.raises(CrossTenantWriteError):
                    await session.flush()

    run(body())


# ── The scope object itself ───────────────────────────────────────────────────


@pytest.mark.parametrize("bad", ["", "   "])
def test_an_empty_org_scope_is_not_constructible(bad: str) -> None:
    with pytest.raises(TenantScopeError):
        OrgScope(org_id=bad, actor="human:x@y")
    with pytest.raises(TenantScopeError):
        OrgScope(org_id="org-1", actor=bad)


def test_a_session_with_no_active_organisation_has_no_tenant_context() -> None:
    """A user who belongs to no org gets an error, not an empty-string scope that matches rows."""
    with pytest.raises(TenantScopeError, match="no active organisation"):
        OrgScope.from_verified_session({"actor": "human:nobody@nowhere"})


def test_scope_is_built_from_a_verified_session_claim() -> None:
    scope_ = OrgScope.from_verified_session(
        {"activeOrganizationId": "org_abc", "actor": "human:controller@acme"}
    )
    assert (scope_.org_id, scope_.actor) == ("org_abc", "human:controller@acme")


def test_the_unscoped_path_is_not_reachable_by_accident() -> None:
    """It exists -- the worker needs it -- but not without naming a recognised reason."""

    async def body() -> None:
        with pytest.raises(UnscopedAccessError, match="tenant_session"):
            async with unscoped_session("just this once"):
                pass

    run(body())
    assert "domain-read" not in UNSCOPED_REASONS
    assert UNSCOPED_REASONS == {"worker-claim", "provisioning", "migration", "test"}


def test_tenant_session_is_not_constructible_without_a_scope() -> None:
    """No default, no ``None``, no ``org_id=''`` fallback: the signature requires a scope."""
    with pytest.raises(TypeError):
        tenant_session()  # type: ignore[call-arg]


# ── Money survives the round trip ─────────────────────────────────────────────


def test_money_round_trips_as_exact_decimal() -> None:
    """NUMERIC in, Decimal out. If this ever returns a float the column type has regressed."""

    async def body() -> None:
        async with two_orgs() as (a, _b):
            ids = await seed(a)
            async with tenant_session(scope(a)) as session:
                item = await session.get(WorkItem, ids["work_item"])
                assert item is not None
                assert isinstance(item.amount, Decimal)
                assert item.amount == Decimal("14231.99")
                verdict = await session.get(Verdict, ids["verdict"])
                assert isinstance(verdict.confidence, Decimal)
                assert verdict.confidence == Decimal("0.4200")

    run(body())
