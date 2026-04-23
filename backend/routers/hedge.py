"""Hedge router — positions, net effective price, scenario model, prices."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException

from backend.models.hedge import (
    CashPriceResponse,
    FuturesPriceResponse,
    NetPriceResponse,
    PositionCreate,
    PositionResponse,
    PositionUpdate,
    ScenarioRequest,
    ScenarioRow,
)
from farm_platform.hedge.calculator import calc_phase1, calc_phase2
from farm_platform.hedge.scenario_model import run_phase1_scenarios, run_phase2_scenarios
from farm_platform.hedge.tracker import (
    add_position,
    close_position,
    get_all_positions,
    get_position_by_id,
    patch_position,
)
from farm_platform.storage.timescale import get_latest_cash, get_latest_futures

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/hedge", tags=["hedge"])


# ── Positions ─────────────────────────────────────────────────────────────────

@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(active_only: bool = True) -> list[dict[str, Any]]:
    return await get_all_positions(active_only=active_only)


@router.post("/positions", response_model=dict[str, str], status_code=201)
async def create_position(body: PositionCreate) -> dict[str, str]:
    try:
        position_id = await add_position(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": position_id}


@router.get("/positions/{position_id}", response_model=PositionResponse)
async def get_position(position_id: str) -> dict[str, Any]:
    pos = await get_position_by_id(position_id)
    if pos is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return pos


@router.put("/positions/{position_id}", response_model=dict[str, str])
async def update_position(position_id: str, body: PositionUpdate) -> dict[str, str]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")
    await patch_position(position_id, updates)
    return {"id": position_id}


# ── Net effective price ───────────────────────────────────────────────────────

@router.get("/net-price", response_model=list[NetPriceResponse])
async def get_net_prices() -> list[dict[str, Any]]:
    """Return net effective price for each active position."""
    positions = await get_all_positions(active_only=True)
    results = []
    for pos in positions:
        symbol = f"{pos['commodity']}=F"
        latest = await get_latest_futures(symbol)
        if latest is None:
            continue
        underlying = float(latest["close"]) if latest["close"] else 0.0

        if pos["phase"] == 1:
            result = calc_phase1(
                current_cash_price=underlying,   # approximate with futures until cash feed is live
                underlying_price=underlying,
                strike=pos["strike"],
                total_premiums_paid_per_bu=pos["premium_paid_per_bu"],
                expected_bushels=pos["expected_bushels"],
                delta_at_entry=pos["delta_at_entry"],
            )
            results.append({
                "commodity": pos["commodity"],
                "phase": 1,
                "underlying_price": underlying,
                "net_effective_price": result.net_effective_price,
                "put_intrinsic": result.put_intrinsic_value,
                "call_intrinsic": 0.0,
                "total_premiums_paid": result.total_premiums_paid,
                "raw_contracts": result.raw_contracts,
                "delta_adj_contracts": result.delta_adj_contracts,
            })
        else:
            cash_locked = pos.get("cash_sale_price") or underlying
            result2 = calc_phase2(
                cash_sale_price=cash_locked,
                underlying_price=underlying,
                call_strike=pos["strike"],
                call_premium_paid_per_bu=pos["premium_paid_per_bu"],
                total_premiums_paid_per_bu=pos["premium_paid_per_bu"],
                expected_bushels=pos["expected_bushels"],
                delta_at_entry=pos["delta_at_entry"],
            )
            results.append({
                "commodity": pos["commodity"],
                "phase": 2,
                "underlying_price": underlying,
                "net_effective_price": result2.net_effective_price,
                "put_intrinsic": 0.0,
                "call_intrinsic": max(underlying - pos["strike"], 0.0),
                "total_premiums_paid": result2.total_premiums_paid,
                "raw_contracts": result2.raw_contracts,
                "delta_adj_contracts": result2.delta_adj_contracts,
            })
    return results


# ── Scenario modeler ─────────────────────────────────────────────────────────

@router.post("/scenario", response_model=list[ScenarioRow])
async def run_scenario(body: ScenarioRequest) -> list[dict[str, Any]]:
    if body.phase == 1:
        rows = run_phase1_scenarios(
            hypothetical_prices=body.hypothetical_prices,
            current_cash_offset=body.current_cash_offset,
            strike=body.strike,
            total_premiums_paid_per_bu=body.total_premiums_paid_per_bu,
            expected_bushels=body.expected_bushels,
            delta_at_entry=body.delta_at_entry,
        )
    else:
        if body.cash_sale_price is None or body.call_premium_paid_per_bu is None:
            raise HTTPException(
                status_code=422,
                detail="cash_sale_price and call_premium_paid_per_bu required for Phase 2",
            )
        rows = run_phase2_scenarios(
            hypothetical_prices=body.hypothetical_prices,
            cash_sale_price=body.cash_sale_price,
            call_strike=body.strike,
            call_premium_paid_per_bu=body.call_premium_paid_per_bu,
            total_premiums_paid_per_bu=body.total_premiums_paid_per_bu,
            expected_bushels=body.expected_bushels,
            delta_at_entry=body.delta_at_entry,
        )
    return [vars(r) for r in rows]


# ── Prices ────────────────────────────────────────────────────────────────────

@router.get("/prices/futures", response_model=list[FuturesPriceResponse])
async def get_futures_prices() -> list[dict[str, Any]]:
    results = []
    for symbol in ["ZC=F", "ZS=F", "ZW=F"]:
        row = await get_latest_futures(symbol)
        if row:
            results.append({
                "symbol": symbol,
                "time": row["time"].isoformat() if hasattr(row["time"], "isoformat") else str(row["time"]),
                "close": float(row["close"]) if row["close"] is not None else None,
                "stale": bool(row["stale"]),
            })
    return results


@router.get("/prices/cash", response_model=list[CashPriceResponse])
async def get_cash_prices() -> list[dict[str, Any]]:
    results = []
    for elevator, commodity in [("default", "ZC"), ("default", "ZS")]:
        row = await get_latest_cash(elevator, commodity)
        if row:
            results.append({
                "elevator": row["elevator"],
                "commodity": row["commodity"],
                "time": row["time"].isoformat() if hasattr(row["time"], "isoformat") else str(row["time"]),
                "cash_price": float(row["cash_price"]),
                "futures_ref": float(row["futures_ref"]) if row["futures_ref"] is not None else None,
                "basis": float(row["basis"]) if row["basis"] is not None else None,
                "contract_month": row["contract_month"],
            })
    return results
