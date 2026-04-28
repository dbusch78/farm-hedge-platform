"""Analytics router — historical time-series data for charting."""

from __future__ import annotations

from fastapi import APIRouter

from farm_platform.storage.timescale import (
    get_basis_history,
    get_elevator_names,
    get_futures_history,
    get_nep_history,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/futures-history")
async def futures_history(
    symbol: str = "ZC=F", days: int = 365
) -> list[dict]:
    rows = await get_futures_history(symbol, days)
    return [
        {
            "time": r["time"].isoformat(),
            "open": float(r["open"]) if r["open"] is not None else None,
            "high": float(r["high"]) if r["high"] is not None else None,
            "low": float(r["low"]) if r["low"] is not None else None,
            "close": float(r["close"]) if r["close"] is not None else None,
            "volume": int(r["volume"]) if r["volume"] is not None else None,
            "stale": bool(r["stale"]),
        }
        for r in rows
    ]


@router.get("/basis-history")
async def basis_history(
    commodity: str = "ZC", days: int = 180, elevator: str | None = None
) -> list[dict]:
    rows = await get_basis_history(commodity, days, elevator)
    return [
        {
            "time": r["time"].isoformat(),
            "elevator": r["elevator"],
            "commodity": r["commodity"],
            "cash_price": float(r["cash_price"]),
            "futures_ref": float(r["futures_ref"]) if r["futures_ref"] is not None else None,
            "basis": float(r["basis"]) if r["basis"] is not None else None,
        }
        for r in rows
    ]


@router.get("/nep-history")
async def nep_history(days: int = 365) -> list[dict]:
    rows = await get_nep_history(days)
    return [
        {
            "time": r["time"].isoformat(),
            "position_id": r["position_id"],
            "underlying_px": float(r["underlying_px"]),
            "net_eff_price": float(r["net_eff_price"]) if r["net_eff_price"] is not None else None,
            "pnl_per_bushel": float(r["pnl_per_bushel"]) if r["pnl_per_bushel"] is not None else None,
            "premium_paid": float(r["premium_paid"]) if r["premium_paid"] is not None else None,
        }
        for r in rows
    ]


@router.get("/elevators")
async def list_elevators() -> list[str]:
    return await get_elevator_names()
