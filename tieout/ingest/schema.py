"""Canonical frozen row models — SPEC section 3."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from tieout.ingest.money import Money

FROZEN = ConfigDict(frozen=True, strict=True, arbitrary_types_allowed=True)


class SourceRowRef(BaseModel):
    """Lineage: which file and which row produced this record."""

    model_config = FROZEN

    file: str
    row_number: int = Field(ge=2, description="1-based line number in the CSV file")


class LedgerEntry(BaseModel):
    model_config = FROZEN

    id: str
    order_key: str
    occurred_at: datetime
    amount: Money
    currency: str
    status: str
    method: str
    source_row_ref: SourceRowRef


class ProcessorEvent(BaseModel):
    model_config = FROZEN

    id: str
    order_key: str
    event_type: str
    event_time: datetime
    gross: Money
    fee: Money
    net: Money
    batch_key: str
    status: str
    source_row_ref: SourceRowRef


class BankEntry(BaseModel):
    model_config = FROZEN

    id: str
    batch_key: str
    booked_at: datetime
    credited: Money
    reference: str
    description: str
    source_row_ref: SourceRowRef


class WorkItem(BaseModel):
    model_config = FROZEN

    work_key: str
    ledger: list[LedgerEntry] = Field(default_factory=list)
    processor: list[ProcessorEvent] = Field(default_factory=list)
    bank: list[BankEntry] = Field(default_factory=list)
