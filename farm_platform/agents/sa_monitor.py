"""Agent 2: South America Monitor

Principle: Brazil produces more soybeans than the US. Argentine La Niña crop
failures have driven 10-30% ZS rallies historically. Output is especially
relevant for Phase 2 call decisions.

Trigger: Weekly, or on-demand before major position decisions.
"""

from __future__ import annotations

from typing import Any

import structlog

from farm_platform.agents.base_agent import run_agent
from farm_platform.storage.timescale import get_pool

log = structlog.get_logger(__name__)

AGENT_NAME = "sa_monitor"
PROMPT_VERSION = "v1.0"

_REGIONS = {
    "mato_grosso": {"lat": -12.5, "lon": -55.5, "label": "Mato Grosso (BR)"},
    "parana": {"lat": -23.5, "lon": -51.5, "label": "Paraná (BR)"},
    "pampas": {"lat": -34.5, "lon": -60.5, "label": "Pampas (AR)"},
}

_SYSTEM_PROMPT = """\
You are a South American grain crop analyst. You monitor weather conditions in
Brazil (Mato Grosso, Paraná) and Argentina (Pampas) for their impact on the
global soybean and corn supply balance.

Context:
- Brazil is the world's largest soybean exporter. La Niña reduces rainfall in
  the Brazilian Cerrado (Mato Grosso), damaging the soy crop.
- Argentina is the world's largest soy meal exporter. Drought in the Pampas
  causes significant bean and corn supply disruptions.
- A drought-reduced SA crop = bullish ZS. A bumper crop = bearish.

Given the regional weather summary, produce this JSON:
{
  "summary": "<2-3 sentence assessment of SA crop conditions and market implications>",
  "brazil_condition": "<good|fair|stressed|severe_stress>",
  "argentina_condition": "<good|fair|stressed|severe_stress>",
  "soil_moisture_flag": "<normal|deficit|severe_deficit|surplus>",
  "precip_anomaly_30d": "<above_normal|normal|below_normal|significantly_below>",
  "zs_implication": "<bullish|bearish|neutral>",
  "zc_implication": "<bullish|bearish|neutral>",
  "positioning_note": "<one actionable sentence for a farmer holding ZS/ZC positions>",
  "confidence": <0.0-1.0>
}
Output ONLY the JSON object.
"""


async def _get_regional_weather() -> list[dict[str, Any]]:
    """Fetch last 30 days of SA regional weather from TimescaleDB."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT region, time,
                       temperature_2m, precipitation, soil_moisture,
                       et0_evapotranspiration
                FROM weather_regional
                WHERE region = ANY($1)
                  AND time >= NOW() - INTERVAL '30 days'
                ORDER BY region, time DESC
                """,
                list(_REGIONS.keys()),
            )
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            r = row["region"]
            if r not in result:
                result[r] = {
                    "region": r,
                    "label": _REGIONS.get(r, {}).get("label", r),
                    "temp_avg_c": [],
                    "precip_30d_mm": 0.0,
                    "soil_moisture_avg": [],
                }
            result[r]["precip_30d_mm"] += float(row["precipitation"] or 0)
            result[r]["temp_avg_c"].append(float(row["temperature_2m"] or 0))
            result[r]["soil_moisture_avg"].append(float(row["soil_moisture"] or 0))
        # Summarize
        for r in result:
            temps = result[r]["temp_avg_c"]
            sm = result[r]["soil_moisture_avg"]
            result[r]["temp_avg_c"] = round(sum(temps) / len(temps), 1) if temps else None
            result[r]["soil_moisture_avg"] = round(sum(sm) / len(sm), 3) if sm else None
        return list(result.values())
    except Exception as e:
        log.warning("sa_weather_fetch_error", error=str(e))
        return []


async def run_once() -> dict[str, Any]:
    """Fetch SA weather data and run the monitor agent."""
    regional = await _get_regional_weather()

    input_snapshot: dict[str, Any] = {
        "regional_weather_30d": regional,
        "regions_covered": list(_REGIONS.keys()),
        "note": (
            "Weather data from Open-Meteo ERA5 reanalysis + forecast. "
            "CONAB and Rosario estimates not automatically fetched — "
            "annotate run with actual outcomes for model tuning."
        ),
        "data_available": len(regional) > 0,
    }

    return await run_agent(AGENT_NAME, input_snapshot, _SYSTEM_PROMPT, PROMPT_VERSION)
