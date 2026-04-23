"""Pydantic request/response schemas for the hedge router."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── Request bodies ────────────────────────────────────────────────────────────

class PositionCreate(BaseModel):
    commodity: Literal["ZC", "ZS"]
    contract_month: str = Field(examples=["Jul25"])
    position_type: Literal["put", "call"]
    strike: float
    premium_paid_per_bu: float
    num_contracts: int
    delta_at_entry: float = Field(gt=0, le=1)
    expected_bushels: int
    phase: Literal[1, 2] = 1
    date_opened: str = Field(examples=["2025-04-01T00:00:00Z"])
    cash_sale_price: float | None = None
    notes: str = ""


class PositionUpdate(BaseModel):
    strike: float | None = None
    premium_paid_per_bu: float | None = None
    num_contracts: int | None = None
    delta_at_entry: float | None = None
    phase: Literal[1, 2] | None = None
    cash_sale_price: float | None = None
    notes: str | None = None
    closed: bool | None = None
    date_closed: str | None = None


class ScenarioRequest(BaseModel):
    hypothetical_prices: list[float] = Field(min_length=1, max_length=50)
    current_cash_offset: float = Field(
        default=0.0,
        description="Basis: cash minus futures. Applied to each scenario price.",
    )
    strike: float
    total_premiums_paid_per_bu: float
    expected_bushels: int
    delta_at_entry: float = Field(gt=0, le=1)
    phase: Literal[1, 2] = 1
    # Phase 2 only
    cash_sale_price: float | None = None
    call_premium_paid_per_bu: float | None = None


# ── Response bodies ───────────────────────────────────────────────────────────

class PositionResponse(BaseModel):
    id: str
    commodity: str
    contract_month: str
    position_type: str
    strike: float
    premium_paid_per_bu: float
    num_contracts: int
    delta_at_entry: float
    expected_bushels: int
    phase: int
    date_opened: str
    cash_sale_price: float | None
    closed: bool
    date_closed: str | None
    notes: str


class NetPriceResponse(BaseModel):
    commodity: str
    phase: int
    underlying_price: float
    net_effective_price: float
    put_intrinsic: float
    call_intrinsic: float
    total_premiums_paid: float
    raw_contracts: float
    delta_adj_contracts: float


class ScenarioRow(BaseModel):
    futures_price: float
    put_intrinsic: float
    call_intrinsic: float
    premiums_paid: float
    net_effective_price: float


class FuturesPriceResponse(BaseModel):
    symbol: str
    time: str
    close: float | None
    stale: bool


class CashPriceResponse(BaseModel):
    elevator: str
    commodity: str
    time: str
    cash_price: float
    futures_ref: float | None
    basis: float | None
    contract_month: str | None
