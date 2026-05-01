"""Hedge router — positions, net effective price, scenario model, prices."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException

from backend.models.hedge import (
    AuditEntry,
    CashPriceResponse,
    CloseRequest,
    ExpireRequest,
    FuturesPriceResponse,
    NetPriceResponse,
    PositionCreate,
    PositionDetailResponse,
    PositionResponse,
    PositionUpdate,
    ScenarioRequest,
    ScenarioRow,
)
from farm_platform.hedge.calculator import calc_phase1, calc_phase2
from farm_platform.hedge.scenario_model import run_phase1_scenarios, run_phase2_scenarios
from farm_platform.hedge.tracker import (
    add_position,
    close_position_with_pnl,
    delete_position,
    expire_position,
    get_all_positions,
    get_position_by_id,
    patch_position,
)
from farm_platform.storage.timescale import get_futures_history, get_latest_cash, get_latest_futures

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/hedge", tags=["hedge"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _enrich_position_pnl(pos: dict[str, Any], underlying: float) -> None:
    """Attach live P&L fields to a position dict in-place.

    Uses the position's own cash_sale_price (Phase 2) or futures as the cash
    proxy (Phase 1). Never uses a commodity-level aggregate.
    """
    try:
        if pos["phase"] == 1:
            result = calc_phase1(
                current_cash_price=underlying,
                underlying_price=underlying,
                strike=pos["strike"],
                total_premiums_paid_per_bu=pos["premium_paid_per_bu"],
                expected_bushels=pos["expected_bushels"],
                delta_at_entry=pos["delta_at_entry"],
            )
            pos["options_pnl_per_bu"] = round(
                result.put_intrinsic_value - result.total_premiums_paid, 4
            )
            pos["net_effective_price"] = result.net_effective_price
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
            pos["options_pnl_per_bu"] = round(result2.call_pnl, 4)
            pos["net_effective_price"] = result2.net_effective_price
        pos["net_effective_vs_spot_per_bu"] = round(
            pos["net_effective_price"] - underlying, 4
        )
        pos["underlying_price"] = underlying
    except Exception:
        log.exception("position_pnl_enrich_error", position_id=pos.get("id"))


# ── Positions ─────────────────────────────────────────────────────────────────

@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(
    status: str = "active",
    active_only: bool | None = None,   # legacy param — remove after frontend updated
) -> list[dict[str, Any]]:
    # Legacy callers still send active_only=true/false
    if active_only is not None and status == "active":
        resolved = "active" if active_only else "all"
    else:
        resolved = status
    positions = await get_all_positions(status=resolved)

    # Enrich active positions with live per-position P&L.
    # Batch futures lookups: one fetch per commodity regardless of position count.
    active_commodities = {
        p["commodity"]
        for p in positions
        if p.get("status", "ACTIVE") == "ACTIVE"
    }
    underlying_by_commodity: dict[str, float] = {}
    for commodity in active_commodities:
        latest = await get_latest_futures(f"{commodity}=F")
        if latest and latest["close"]:
            underlying_by_commodity[commodity] = float(latest["close"])

    for pos in positions:
        if pos.get("status", "ACTIVE") == "ACTIVE":
            underlying = underlying_by_commodity.get(pos["commodity"])
            if underlying is not None:
                _enrich_position_pnl(pos, underlying)

    return positions


@router.post("/positions", response_model=dict[str, str], status_code=201)
async def create_position(body: PositionCreate) -> dict[str, str]:
    try:
        position_id = await add_position(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": position_id}


@router.get("/positions/{position_id}", response_model=PositionDetailResponse)
async def get_position(position_id: str) -> dict[str, Any]:
    pos = await get_position_by_id(position_id)
    if pos is None:
        raise HTTPException(status_code=404, detail="Position not found")
    pos.setdefault("audit_log", [])
    return pos


@router.put("/positions/{position_id}", response_model=dict[str, str])
async def update_position(position_id: str, body: PositionUpdate) -> dict[str, str]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")
    try:
        await patch_position(position_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": position_id}


@router.post("/positions/{position_id}/close", response_model=dict[str, str])
async def close_position_endpoint(
    position_id: str, body: CloseRequest
) -> dict[str, str]:
    pos = await get_position_by_id(position_id)
    if pos is None:
        raise HTTPException(status_code=404, detail="Position not found")
    if pos.get("status", "ACTIVE") != "ACTIVE":
        raise HTTPException(status_code=422, detail="Position is not ACTIVE")
    try:
        await close_position_with_pnl(
            position_id,
            exit_price_per_bu=body.exit_price_per_bu,
            close_reason=body.close_reason,
            exit_date=body.exit_date,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": position_id}


@router.post("/positions/{position_id}/expire", response_model=dict[str, str])
async def expire_position_endpoint(
    position_id: str, body: ExpireRequest
) -> dict[str, str]:
    pos = await get_position_by_id(position_id)
    if pos is None:
        raise HTTPException(status_code=404, detail="Position not found")
    if pos.get("status", "ACTIVE") != "ACTIVE":
        raise HTTPException(status_code=422, detail="Position is not ACTIVE")
    try:
        await expire_position(
            position_id,
            exit_date=body.exit_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": position_id}


@router.delete("/positions/{position_id}", response_model=dict[str, str])
async def delete_position_endpoint(position_id: str) -> dict[str, str]:
    try:
        await delete_position(position_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": position_id}


# ── Net effective price ───────────────────────────────────────────────────────

@router.get("/net-price", response_model=list[NetPriceResponse])
async def get_net_prices() -> list[dict[str, Any]]:
    """Return net effective price for each (commodity, phase) group.

    Active positions contribute unrealized (mark-to-market) P&L.
    Closed and expired positions contribute their locked realized P&L.
    Both are weight-averaged by raw_contracts into one row per group.
    """
    positions = await get_all_positions(status="all")   # excludes DELETED
    results = []

    # Batch futures lookups — one fetch per commodity symbol.
    futures_cache: dict[str, float] = {}

    async def _underlying(commodity: str) -> float:
        sym = f"{commodity}=F"
        if sym not in futures_cache:
            latest = await get_latest_futures(sym)
            futures_cache[sym] = float(latest["close"]) if (latest and latest["close"]) else 0.0
        return futures_cache[sym]

    for pos in positions:
        status = pos.get("status", "ACTIVE")
        underlying = await _underlying(pos["commodity"])
        if not underlying:
            continue

        raw = pos["expected_bushels"] / 5_000
        delta_adj = raw / pos["delta_at_entry"] if pos["delta_at_entry"] else 0.0

        if status == "ACTIVE":
            if pos["phase"] == 1:
                result = calc_phase1(
                    current_cash_price=underlying,
                    underlying_price=underlying,
                    strike=pos["strike"],
                    total_premiums_paid_per_bu=pos["premium_paid_per_bu"],
                    expected_bushels=pos["expected_bushels"],
                    delta_at_entry=pos["delta_at_entry"],
                )
                options_pnl = round(result.put_intrinsic_value - result.total_premiums_paid, 4)
                results.append({
                    "commodity": pos["commodity"],
                    "phase": 1,
                    "underlying_price": underlying,
                    "net_effective_price": result.net_effective_price,
                    "put_intrinsic": result.put_intrinsic_value,
                    "call_intrinsic": 0.0,
                    "options_pnl_per_bu": options_pnl,
                    "net_effective_vs_spot_per_bu": round(result.net_effective_price - underlying, 4),
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
                    "options_pnl_per_bu": result2.call_pnl,
                    "net_effective_vs_spot_per_bu": round(result2.net_effective_price - underlying, 4),
                    "total_premiums_paid": result2.total_premiums_paid,
                    "raw_contracts": result2.raw_contracts,
                    "delta_adj_contracts": result2.delta_adj_contracts,
                })

        elif status in ("CLOSED", "EXPIRED"):
            # Use locked realized P&L — no mark-to-market for non-active positions.
            realized_pnl = pos.get("realized_pnl_per_bu") or 0.0
            if pos["phase"] == 1:
                # Grain may not yet be sold; use current futures as cash proxy.
                net_price = round(underlying + realized_pnl, 4)
                results.append({
                    "commodity": pos["commodity"],
                    "phase": 1,
                    "underlying_price": underlying,
                    "net_effective_price": net_price,
                    "put_intrinsic": 0.0,
                    "call_intrinsic": 0.0,
                    "options_pnl_per_bu": realized_pnl,
                    "net_effective_vs_spot_per_bu": round(realized_pnl, 4),
                    "total_premiums_paid": pos["premium_paid_per_bu"],
                    "raw_contracts": round(raw, 2),
                    "delta_adj_contracts": round(delta_adj, 2),
                })
            else:
                cash_locked = pos.get("cash_sale_price") or underlying
                net_price = round(cash_locked + realized_pnl, 4)
                results.append({
                    "commodity": pos["commodity"],
                    "phase": 2,
                    "underlying_price": underlying,
                    "net_effective_price": net_price,
                    "put_intrinsic": 0.0,
                    "call_intrinsic": 0.0,
                    "options_pnl_per_bu": realized_pnl,
                    "net_effective_vs_spot_per_bu": round(net_price - underlying, 4),
                    "total_premiums_paid": pos["premium_paid_per_bu"],
                    "raw_contracts": round(raw, 2),
                    "delta_adj_contracts": round(delta_adj, 2),
                })
    # Aggregate by (commodity, phase) so puts and calls are never blended.
    # Multiple same-strategy positions (e.g. two ZS call strikes) collapse to
    # one weighted-average row; different strategies (ZC puts vs ZC calls) stay
    # separate and become independent hedge cards on the frontend.
    by_group: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        by_group[(r["commodity"], r["phase"])].append(r)

    aggregated: list[dict[str, Any]] = []
    for (commodity, phase), group in by_group.items():
        if len(group) == 1:
            aggregated.append(group[0])
            continue
        total_raw = sum(r["raw_contracts"] for r in group)

        def _wavg(field: str) -> float:
            return sum(r[field] * r["raw_contracts"] for r in group) / total_raw

        aggregated.append({
            "commodity": commodity,
            "phase": phase,
            "underlying_price": group[0]["underlying_price"],
            "net_effective_price": _wavg("net_effective_price"),
            "put_intrinsic": _wavg("put_intrinsic"),
            "call_intrinsic": _wavg("call_intrinsic"),
            "options_pnl_per_bu": _wavg("options_pnl_per_bu"),
            "net_effective_vs_spot_per_bu": _wavg("net_effective_vs_spot_per_bu"),
            "total_premiums_paid": _wavg("total_premiums_paid"),
            "raw_contracts": total_raw,
            "delta_adj_contracts": sum(r["delta_adj_contracts"] for r in group),
        })

    return aggregated


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


@router.get("/prices/history/{symbol}", response_model=list[dict[str, Any]])
async def get_price_history(symbol: str, days: int = 90) -> list[dict[str, Any]]:
    rows = await get_futures_history(symbol, days)
    return [
        {
            "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
            "open": float(r["open"]) if r["open"] is not None else None,
            "high": float(r["high"]) if r["high"] is not None else None,
            "low": float(r["low"]) if r["low"] is not None else None,
            "close": float(r["close"]) if r["close"] is not None else None,
            "volume": int(r["volume"]) if r["volume"] is not None else None,
            "stale": bool(r["stale"]),
        }
        for r in rows
    ]


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
