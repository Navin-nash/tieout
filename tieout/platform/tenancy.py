"""Tenant isolation, enforced structurally.

ADR-003: *"No query may omit the org scope. Enforce it structurally -- a base query helper or
a session-level scope -- not by remembering to add a WHERE clause."*

The mechanism is two SQLAlchemy events registered on a session that cannot be constructed
without an :class:`OrgScope`:

**Reads, updates and deletes** -- a ``do_orm_execute`` handler attaches
``with_loader_criteria(OrgScoped, ...)`` to every ORM statement the session runs. SQLAlchemy
applies that criterion to the primary entity, to joins, to relationship lazy-loads and to
ORM-enabled UPDATE and DELETE. So ``select(Run).where(Run.id == <other org's id>)`` returns
nothing, and ``update(Disposition).where(Disposition.id == <other org's id>)`` matches nothing
-- **including when the caller supplies the other org's primary keys directly**, which is the
case that actually leaks in real systems.

**Writes** -- a ``before_flush`` handler stamps ``org_id`` on every new tenant row from the
session's scope, and refuses the flush if an object arrives carrying a different one. A row
cannot be written into the wrong tenant even by accident, and cannot be moved between tenants
by mutating ``org_id`` on a loaded object.

What this does *not* do is authenticate anybody. The org id must arrive from a verified
server-side session (Better Auth, in the Next.js app -- see ``docs/PLATFORM.md``). The one
remaining discipline point is the construction of an :class:`OrgScope`, which is deliberately a
single greppable call: ``OrgScope.from_verified_session``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event, orm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from tieout.platform.models import OrgScoped
from tieout.platform.session import get_sessionmaker

#: Key under which the active org id is stashed in ``Session.info``.
ORG_SCOPE_KEY = "tieout_org_scope"


class TenantScopeError(RuntimeError):
    """A tenant-scoped operation was attempted without, or across, an org scope."""


class CrossTenantWriteError(TenantScopeError):
    """An object carrying another org's id reached a scoped session's flush."""


@dataclass(frozen=True, slots=True)
class OrgScope:
    """The authenticated tenant context for a unit of work.

    ``org_id`` must come from a **server-verified** session. Never construct one of these from
    a request body, a path parameter, a query string or a header: a caller who can choose their
    own ``org_id`` has defeated every filter below, because the filter will faithfully scope to
    the org they named.
    """

    org_id: str
    #: The acting principal, e.g. ``human:controller@acme`` or ``svc:tieout-agent@v0.3.1``.
    #: Carried alongside so audit writes do not have to re-derive it.
    actor: str

    def __post_init__(self) -> None:
        if not self.org_id or not self.org_id.strip():
            raise TenantScopeError("OrgScope requires a non-empty org id")
        if not self.actor or not self.actor.strip():
            raise TenantScopeError("OrgScope requires an acting principal")

    @classmethod
    def from_verified_session(cls, claims: Mapping[str, Any]) -> OrgScope:
        """Build a scope from an already-verified auth session's claims.

        The single intended entry point, so ``grep -rn from_verified_session`` enumerates every
        place a tenant context is established. Anything that reaches this function must already
        have had its signature or cookie checked; this does not verify anything.
        """
        org_id = claims.get("activeOrganizationId") or claims.get("org_id")
        actor = claims.get("actor") or claims.get("principal")
        if not org_id:
            raise TenantScopeError(
                "verified session carries no active organisation; the caller is not a member "
                "of any org and has no tenant context"
            )
        if not actor:
            raise TenantScopeError("verified session carries no principal")
        return cls(org_id=str(org_id), actor=str(actor))


def _org_id_of(session: Session) -> str:
    scope = session.info.get(ORG_SCOPE_KEY)
    if scope is None:
        raise TenantScopeError(
            "tenant filtering was requested on a session with no OrgScope. This session was "
            "not created by tenant_session(); do not attach these events by hand."
        )
        # unreachable-by-design: the events below are only registered inside tenant_session.
    return scope.org_id


def _apply_read_filter(state: ORMExecuteState) -> None:
    """Attach the org criterion to every ORM select/update/delete on a scoped session."""
    if state.is_column_load or state.is_relationship_load:
        # Refreshing already-loaded columns of an object we legitimately hold. Re-filtering
        # here would break identity-map refreshes without adding a guarantee: the object only
        # entered the session through a filtered query in the first place.
        return
    if not (state.is_select or state.is_update or state.is_delete):
        return
    org_id = _org_id_of(state.session)
    state.statement = state.statement.options(
        with_loader_criteria(
            OrgScoped,
            lambda cls: cls.org_id == org_id,
            include_aliases=True,
            # Propagate onto lazy loads and secondary queries issued from these results.
            propagate_to_loaders=True,
        )
    )


def _stamp_and_verify_writes(session: Session, _flush_context: Any, _instances: Any) -> None:
    """Stamp org_id on new tenant rows; refuse anything carrying a different one."""
    org_id = _org_id_of(session)
    for obj in session.new:
        if not isinstance(obj, OrgScoped):
            continue
        current = getattr(obj, "org_id", None)
        if current is None:
            obj.org_id = org_id
        elif current != org_id:
            raise CrossTenantWriteError(
                f"refusing to insert {type(obj).__name__} with org_id={current!r} from a "
                f"session scoped to {org_id!r}"
            )
    for obj in session.dirty:
        if not isinstance(obj, OrgScoped) or not session.is_modified(obj):
            continue
        if getattr(obj, "org_id", None) != org_id:
            raise CrossTenantWriteError(
                f"refusing to update {type(obj).__name__} into org_id="
                f"{getattr(obj, 'org_id', None)!r} from a session scoped to {org_id!r}; "
                "rows do not move between tenants"
            )


def attach_tenant_scope(session: AsyncSession, scope: OrgScope) -> None:
    """Bind ``scope`` to ``session`` and register the two guards. Idempotent per session."""
    sync_session = session.sync_session
    sync_session.info[ORG_SCOPE_KEY] = scope
    event.listen(sync_session, "do_orm_execute", _apply_read_filter)
    event.listen(sync_session, "before_flush", _stamp_and_verify_writes)


@asynccontextmanager
async def tenant_session(scope: OrgScope) -> AsyncIterator[AsyncSession]:
    """The session every domain read and write goes through.

    There is no argument-free variant and no way to drop the scope afterwards: the filter is
    registered on the session object itself, so the org criterion travels with any statement
    handed to it, including ones written elsewhere and passed in.

    Commits are the caller's; the context manager rolls back and closes on exception.
    """
    factory = get_sessionmaker()
    async with factory() as session:
        attach_tenant_scope(session, scope)
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise


def tenant_scoped_models() -> tuple[type[Any], ...]:
    """Every mapped class the filter applies to. Used by the tenancy test to prove coverage."""
    from tieout.platform.models import Base

    orm.configure_mappers()
    return tuple(m.class_ for m in Base.registry.mappers if issubclass(m.class_, OrgScoped))
