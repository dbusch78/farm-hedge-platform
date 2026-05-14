"""USDA supply/demand data feed.

Uses the USDA FAS PSD (Production, Supply, and Distribution) Online API,
which is public and requires no authentication.

API docs: https://apps.fas.usda.gov/psdonline/app/index.html#/app/downloads
Endpoint: https://apps.fas.usda.gov/psdonline/api/psd/commodity

Commodity codes used:
  0440000 — Corn
  2222000 — Soybeans
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)

_BASE = "https://apps.fas.usda.gov/psdonline/api/psd"

_COMMODITY_CODES = {
    "ZC": "0440000",   # Corn
    "ZS": "2222000",   # Soybeans
}

# Market year beginnings (month the MY starts for US exports)
_MY_START_MONTH = {
    "ZC": 9,   # September
    "ZS": 9,   # September
}


async def fetch_latest_wasde(commodity: str = "ZC") -> dict[str, Any]:
    """Return the latest USDA supply/demand estimates for a commodity.

    Returns a dict with keys:
      commodity, market_year, ending_stocks_mbu, production_mbu,
      total_use_mbu, exports_mbu, source, fetch_error (if any)
    """
    code = _COMMODITY_CODES.get(commodity.upper(), "0440000")
    country_code = 231  # United States
    url = f"{_BASE}/commodity/{code}/country/{country_code}"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        log.warning("usda_fetch_error", commodity=commodity, error=str(e))
        return {
            "commodity": commodity,
            "market_year": None,
            "ending_stocks_mbu": None,
            "production_mbu": None,
            "total_use_mbu": None,
            "exports_mbu": None,
            "source": "USDA FAS PSD",
            "fetch_error": str(e),
        }

    if not data:
        return {
            "commodity": commodity,
            "market_year": None,
            "ending_stocks_mbu": None,
            "source": "USDA FAS PSD",
            "fetch_error": "empty response",
        }

    # PSD returns a list of records with marketYear, attributeDescription, value
    # Filter for the most recent market year's key attributes
    records_by_year: dict[int, dict[str, float]] = {}
    for rec in data:
        year = rec.get("marketYear")
        attr = rec.get("attributeDescription", "")
        val = rec.get("value")
        if year and val is not None:
            if year not in records_by_year:
                records_by_year[year] = {}
            records_by_year[year][attr] = val

    if not records_by_year:
        return {
            "commodity": commodity,
            "market_year": None,
            "ending_stocks_mbu": None,
            "source": "USDA FAS PSD",
            "fetch_error": "no records parsed",
        }

    latest_year = max(records_by_year.keys())
    attrs = records_by_year[latest_year]

    # Convert thousand metric tons to million bushels
    # Corn: 1 MT = 39.368 bushels; Soybeans: 1 MT = 36.744 bushels
    bu_per_mt = 39.368 if commodity.upper() == "ZC" else 36.744

    def to_mbu(val_1000mt: float | None) -> float | None:
        if val_1000mt is None:
            return None
        return round(val_1000mt * bu_per_mt / 1000, 1)  # 1000 MT → MMT → MBu

    # Attribute names vary slightly; try common variants
    def get_attr(*keys: str) -> float | None:
        for k in keys:
            if k in attrs:
                return attrs[k]
        return None

    return {
        "commodity": commodity,
        "market_year": latest_year,
        "ending_stocks_mbu": to_mbu(get_attr("Ending Stocks")),
        "production_mbu": to_mbu(get_attr("Production")),
        "total_use_mbu": to_mbu(get_attr("Total Use")),
        "exports_mbu": to_mbu(get_attr("Exports")),
        "source": "USDA FAS PSD",
        "fetch_error": None,
    }
