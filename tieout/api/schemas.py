"""Request models for the HTTP boundary. Responses reuse domain report dicts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tieout.gate.invariants import OVERRIDE_PARAMETER_NAMES

FROZEN = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class ReviewRequest(BaseModel):
    """Review action — identity is required; four-eyes is enforced at write time."""

    model_config = FROZEN

    action: Literal["approve", "reject", "reclassify"]
    identity: str = Field(min_length=1, description="Reviewer principal, e.g. controller@acme")
    note: str = ""
    reclassify_to: str | None = Field(
        default=None, description="Required when action is reclassify"
    )
    initiator: str = Field(
        min_length=1,
        description="Principal of the party that escalated the item (for four-eyes)",
    )

    @field_validator("identity", "initiator")
    @classmethod
    def _reject_override_names(cls, value: str) -> str:
        if value in OVERRIDE_PARAMETER_NAMES:
            raise ValueError(f"{value!r} is not a valid identity")
        return value

    @model_validator(mode="after")
    def _reclassify_requires_target(self) -> ReviewRequest:
        if self.action == "reclassify" and not self.reclassify_to:
            raise ValueError("reclassify_to is required when action is reclassify")
        return self


class PolicyWriteRequest(BaseModel):
    """Human-only policy change with provenance (SPEC section 4)."""

    model_config = FROZEN

    version: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    identity: str = Field(min_length=1, description="Human principal, e.g. controller@acme")
    yaml_body: str = Field(min_length=1)

    @field_validator("identity")
    @classmethod
    def _reject_override_names(cls, value: str) -> str:
        if value in OVERRIDE_PARAMETER_NAMES:
            raise ValueError(f"{value!r} is not a valid identity")
        return value


class RunCreateRequest(BaseModel):
    """Enqueue a reconcile run. Org is never accepted here."""

    model_config = FROZEN

    period: str = Field(min_length=1, pattern=r"^\d{4}-\d{2}$")
