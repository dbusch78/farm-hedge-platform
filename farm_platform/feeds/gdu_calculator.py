"""GDU (Growing Degree Unit) status from TimescaleDB.

Standard corn/bean GDU formula (base 50°F):
    GDU_daily = max(((min_temp_f + max_temp_f) / 2) - 50, 0)

The gdu_daily continuous aggregate handles the per-day computation.
This module queries it and returns cumulative totals from planting date.

Planting dates are stored in the planting_dates table (one row per commodity+year).
Falls back to config defaults (PLANTING_DATE_CORN / PLANTING_DATE_BEANS env vars)
if no DB record exists for the current year.
"""

from __future__ import annotations

from datetime import date

import structlog

from farm_platform.config import settings
from farm_platform.storage.timescale import fetch, fetchrow, get_planting_date

log = structlog.get_logger(__name__)


async def _resolve_planting_date(commodity: str) -> date:
    """Return planting date from DB for current year, or fall back to config."""
    current_year = date.today().year
    row = await get_planting_date(commodity, current_year)
    if row is not None:
        return row["planted_date"]
    # Fall back to config default
    return (
        settings.farm.planting_date_corn
        if commodity == "corn"
        else settings.farm.planting_date_beans
    )


async def get_gdu_status(commodity: str = "corn") -> dict:
    planting = await _resolve_planting_date(commodity)

    rows = await fetch(
        """
        SELECT day, gdu
        FROM gdu_daily
        WHERE day >= $1
        ORDER BY day ASC
        """,
        planting,
    )

    cumulative = sum(float(r["gdu"]) for r in rows if r["gdu"] is not None)
    today_gdu = float(rows[-1]["gdu"]) if rows and rows[-1]["gdu"] is not None else 0.0
    days_tracked = len(rows)

    return {
        "commodity": commodity,
        "planting_date": planting.isoformat(),
        "days_tracked": days_tracked,
        "cumulative_gdu": round(cumulative, 1),
        "today_gdu": round(today_gdu, 1),
    }


async def get_gdu_history(days: int = 90) -> list[dict]:
    """Return daily GDU rows for charting."""
    rows = await fetch(
        """
        SELECT day, avg_temp_f, gdu
        FROM gdu_daily
        WHERE day >= NOW() - ($1 || ' days')::INTERVAL
        ORDER BY day ASC
        """,
        str(days),
    )
    return [
        {
            "day": r["day"].isoformat() if hasattr(r["day"], "isoformat") else str(r["day"]),
            "avg_temp_f": float(r["avg_temp_f"]) if r["avg_temp_f"] is not None else None,
            "gdu": float(r["gdu"]) if r["gdu"] is not None else None,
        }
        for r in rows
    ]
