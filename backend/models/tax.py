"""Pydantic models for tax classification, cash sales, and audit log."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ── Cash sales ────────────────────────────────────────────────────────────────

class CashSaleCreate(BaseModel):
    sale_date: str                          # ISO date string "2026-01-05"
    commodity: Literal["ZC", "ZS"]
    bushels: int = Field(gt=0)
    cash_price_per_bu: float = Field(gt=0)
    adjustments: float = 0.0
    delivery_location: str | None = None
    selling_entity: str | None = None
    trucking_per_bu: float | None = None
    trucking_total: float | None = None
    contract_settlement_id: str | None = None
    notes: str = ""

    @model_validator(mode="after")
    def compute_amounts(self) -> "CashSaleCreate":
        # Allow trucking_total to be derived from trucking_per_bu if not set
        if self.trucking_total is None and self.trucking_per_bu is not None:
            self.trucking_total = round(self.trucking_per_bu * self.bushels, 2)
        return self

    @property
    def gross_amount(self) -> float:
        return round(self.bushels * self.cash_price_per_bu, 2)

    @property
    def net_amount(self) -> float:
        return round(
            self.gross_amount - self.adjustments - (self.trucking_total or 0.0), 2
        )


class CashSaleUpdate(BaseModel):
    sale_date: str | None = None
    bushels: int | None = Field(default=None, gt=0)
    cash_price_per_bu: float | None = Field(default=None, gt=0)
    adjustments: float | None = None
    delivery_location: str | None = None
    selling_entity: str | None = None
    trucking_per_bu: float | None = None
    trucking_total: float | None = None
    contract_settlement_id: str | None = None
    notes: str | None = None


class CashSaleResponse(BaseModel):
    id: str
    sale_date: str
    commodity: str
    bushels: int
    cash_price_per_bu: float
    gross_amount: float
    adjustments: float
    net_amount: float
    delivery_location: str | None
    selling_entity: str | None
    trucking_per_bu: float | None
    trucking_total: float | None
    contract_settlement_id: str | None
    notes: str
    created_at: str
    migrated: bool


# ── Position audit log ────────────────────────────────────────────────────────

class AuditLogEntry(BaseModel):
    id: str
    position_id: str
    timestamp: str
    action: str
    field_changed: str | None
    before_value: Any | None
    after_value: Any | None
    reason: str | None
    user_id: str
    migrated: bool


# ── Tax export ────────────────────────────────────────────────────────────────

class TaxPositionRow(BaseModel):
    id: str
    commodity: str
    contract_month: str
    position_type: str
    strike: float
    premium_paid_per_bu: float
    expected_bushels: int
    date_opened: str
    tax_treatment: str
    status: str
    # Closed positions
    exit_date: str | None
    exit_price_per_bu: float | None
    realized_pnl_per_bu: float | None
    realized_pnl_total: float | None
    # Live P&L for open SPECULATIVE (mark-to-market)
    options_pnl_per_bu: float | None
    options_pnl_total: float | None
    # Hedge documentation (HEDGE only)
    hedge_documentation: str | None
    hedge_identification_date: str | None
    irc_1221_acknowledgment: bool | None


class TaxSummary(BaseModel):
    tax_year: int
    hedge_realized_total: float
    speculative_realized_total: float
    speculative_mtm_total: float          # open positions, mark-to-market
    speculative_section_1256_total: float # realized + mtm
    ltcg_60pct: float                     # 60% of section_1256_total
    stcg_40pct: float                     # 40% of section_1256_total
    positions: list[TaxPositionRow]
