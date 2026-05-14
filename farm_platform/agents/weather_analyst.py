"""Agent 3: Weather Analyst

Principle: Must understand crop phenology. A July heat event at corn R1
(pollination) is catastrophic. The same event at V6 is a setback.

Trigger: Daily May-September, weekly otherwise.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog

from farm_platform.agents.base_agent import run_agent
from farm_platform.storage.timescale import get_pool

log = structlog.get_logger(__name__)

AGENT_NAME = "weather_analyst"
PROMPT_VERSION = "v1.0"

_SYSTEM_PROMPT = """\
You are an agronomic weather analyst for a Midwest grain farm.
You interpret on-farm and regional weather data through the lens of crop physiology.

Crop growth stage calendar (approximate, northern IL planting ~May 1):
- Corn: V6 by June 15, VT/R1 (pollination, critical) mid-July, R3-R5 (fill) late July-August
- Soybeans: V stages June, R1-R2 (flowering) early July, R3-R5 (pod fill, critical) July-August

Your output must be JSON with this structure:
{
  "summary": "<2-3 sentence assessment of current weather impact on crop prospects>",
  "corn_stage": "<estimated growth stage based on GDU and planting date>",
  "beans_stage": "<estimated growth stage>",
  "gdu_status": "<ahead|on_track|behind> vs historical average",
  "soil_moisture_flag": "<adequate|deficit|severe_deficit|saturated>",
  "heat_stress_flag": <true if 3+ days >95F in next 14 days during R1>,
  "pollination_risk": "<none|low|moderate|high> — corn R1 in late July is the key window",
  "fill_period_risk": "<none|low|moderate|high> — bean R3-R5 in August",
  "local_vs_regional": "<comment on whether on-farm conditions diverge from corn belt average>",
  "zc_implication": "<bullish|bearish|neutral>",
  "zs_implication": "<bullish|bearish|neutral>",
  "confidence": <0.0-1.0>
}
Output ONLY the JSON object.
"""


async def _get_local_weather(days: int = 7) -> dict[str, Any]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT temp_f, humidity, rain_in, wind_mph, solar_radiation,
                       time, gdu_daily
                FROM weather_station_local wsl
                LEFT JOIN LATERAL (
                    SELECT SUM(gdu) as gdu_daily
                    FROM gdu_daily
                    WHERE date >= NOW()::date - $2::integer
                ) gd ON true
                WHERE time >= NOW() - ($2 || ' days')::interval
                ORDER BY time DESC
                LIMIT 200
                """,
                days, days,
            )
        if not rows:
            return {}
        temps = [float(r["temp_f"]) for r in rows if r.get("temp_f")]
        rain = sum(float(r["rain_in"] or 0) for r in rows)
        return {
            "avg_temp_f": round(sum(temps) / len(temps), 1) if temps else None,
            "max_temp_f": max(temps) if temps else None,
            "rain_total_in": round(rain, 2),
            "days_above_90f": sum(1 for t in temps if t >= 90),
            "days_above_95f": sum(1 for t in temps if t >= 95),
        }
    except Exception as e:
        log.warning("local_weather_fetch_error", error=str(e))
        return {}


async def _get_gdu_status() -> dict[str, Any]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT commodity,
                       SUM(gdu) as cumulative_gdu,
                       COUNT(*) as days_since_planting
                FROM gdu_daily
                WHERE date >= (
                    SELECT COALESCE(
                        (SELECT planted_date FROM planting_dates
                         WHERE commodity = gdu_daily.commodity
                           AND year = EXTRACT(YEAR FROM NOW())::int),
                        NOW()::date - INTERVAL '30 days'
                    )
                )
                GROUP BY commodity
                """
            )
        if row:
            return {"cumulative_gdu": float(row["cumulative_gdu"] or 0)}
        return {}
    except Exception as e:
        log.warning("gdu_fetch_error", error=str(e))
        return {}


async def run_once() -> dict[str, Any]:
    """Fetch weather data and run the analyst agent."""
    local = await _get_local_weather(days=7)
    gdu = await _get_gdu_status()
    today = date.today()

    input_snapshot: dict[str, Any] = {
        "date": today.isoformat(),
        "month": today.month,
        "day_of_year": today.timetuple().tm_yday,
        "local_station_7d": local,
        "gdu": gdu,
        "planting_date_corn": "approx May 1",
        "planting_date_beans": "approx May 10",
        "location": "Northern Illinois (Stark County area)",
        "note": "Regional corn belt weather not included; focus on local station + GDU.",
    }

    return await run_agent(AGENT_NAME, input_snapshot, _SYSTEM_PROMPT, PROMPT_VERSION)
