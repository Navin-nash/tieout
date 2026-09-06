"""Platform configuration, read from the environment.

``DATABASE_URL`` is required and has no default. A default that silently points at a dev
database is how production rows end up in a scratch Postgres, so there isn't one: constructing
:class:`PlatformSettings` without it raises.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Upload ceiling. The three ReconRiver CSVs total ~2 MB; 64 MB is generous and still bounded.
DEFAULT_MAX_UPLOAD_BYTES = 64 * 1024 * 1024

#: The only content types an upload endpoint may accept (ADR-003: fixed ReconRiver schema,
#: no generic column-mapping UI). A filename is never trusted; this is checked instead.
ALLOWED_UPLOAD_CONTENT_TYPES = frozenset(
    {"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel"}
)

#: Drivers we refuse outright rather than fail on at first query.
_SYNC_OR_WRONG_DRIVERS = ("postgresql+psycopg2://", "postgresql+asyncpg://", "postgresql+pg8000://")


def normalise_database_url(url: str) -> str:
    """Force the psycopg 3 async dialect onto an otherwise ordinary Postgres URL.

    Hosted providers (Neon, Supabase, RDS) hand out ``postgresql://...``. Rewriting the scheme
    here means the operator pastes the provider's URL verbatim and it works, rather than
    discovering at first query that SQLAlchemy loaded psycopg2 and cannot await.
    """
    if url.startswith(_SYNC_OR_WRONG_DRIVERS):
        driver = url.split("://", 1)[0]
        raise ValueError(
            f"DATABASE_URL uses driver {driver!r}; the platform layer is psycopg 3 async only. "
            "Use postgresql:// or postgresql+psycopg://."
        )
    if url.startswith("postgres://"):  # heroku-style alias
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith(("postgresql+psycopg://", "postgresql+psycopg_async://")):
        return url
    raise ValueError(
        "DATABASE_URL must be a PostgreSQL URL, e.g. "
        f"postgresql://user:password@host:5432/database (got {url.split('://', 1)[0]!r})"
    )


class PlatformSettings(BaseSettings):
    """Environment-derived platform settings. Frozen; read once at startup."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    database_url: str = Field(
        ...,
        description="Postgres URL. Required -- there is deliberately no default.",
    )
    data_root: Path = Field(
        default=Path("data"),
        description="Filesystem root under which per-organisation storage lives.",
    )
    max_upload_bytes: int = Field(default=DEFAULT_MAX_UPLOAD_BYTES, gt=0)
    sql_echo: bool = Field(default=False)

    db_hostaddr: str | None = Field(
        default=None,
        alias="TIEOUT_DB_HOSTADDR",
        description=(
            "Optional libpq hostaddr. Set only when the local resolver cannot see the database "
            "hostname (some corporate DNS refuses hosted-Postgres subdomains). libpq still "
            "sends the URL's hostname for SNI and TLS verification, so the connection stays "
            "authenticated against the right certificate."
        ),
    )

    @field_validator("database_url")
    @classmethod
    def _normalise(cls, value: str) -> str:
        return normalise_database_url(value)


@lru_cache(maxsize=1)
def get_settings() -> PlatformSettings:
    """Process-wide settings. Cached; call ``get_settings.cache_clear()`` in tests."""
    return PlatformSettings()  # type: ignore[call-arg]  # values come from the environment
