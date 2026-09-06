"""SaaS persistence and multi-tenancy layer (ADR-003).

The exports here are the ones domain code should reach for. Notably absent:
``get_sessionmaker`` and ``unscoped_session``. Both exist in
:mod:`tieout.platform.session`, both are documented, and neither is one import away by
accident -- a domain read that wants a session gets :func:`~tieout.platform.tenancy.tenant_session`,
which cannot be called without an :class:`~tieout.platform.tenancy.OrgScope`.

See ``docs/PLATFORM.md``.
"""

from tieout.platform.settings import PlatformSettings, get_settings
from tieout.platform.tenancy import (
    CrossTenantWriteError,
    OrgScope,
    TenantScopeError,
    tenant_session,
)

__all__ = [
    "CrossTenantWriteError",
    "OrgScope",
    "PlatformSettings",
    "TenantScopeError",
    "get_settings",
    "tenant_session",
]
