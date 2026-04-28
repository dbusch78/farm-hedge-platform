"""Open-Meteo regional weather feed — 4 regions, polled every 6 hours.

Regions tracked:
  corn_belt   — central Iowa (proxy for US Midwest crop conditions)
  mato_grosso — central Brazil (world's largest soy/corn producing state)
  parana      — southern Brazil (secondary soy region, early harvest bellwether)
  pampas      — Argentine Pampas (major export origin, La Niña sensitivity)
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from farm_platform.storage.timescale import insert_weather_regional

log = structlog.get_logger(__name__)

_BASE = "https://api.open-meteo.com/v1/forecast"

REGIONS = [
    {"name": "corn_belt",   "lat":  41.5, "lon":  -93.5},
    {"name": "mato_grosso", "lat": -12.5, "lon":  -55.5},
    {"name": "parana",      "lat": -23.5, "lon":  -51.5},
    {"name": "pampas",      "lat": -34.5, "lon":  -60.5},
]


async def run_once() -> None:
    async with httpx.AsyncClient(timeout=20) as client:
        for region in REGIONS:
            try:
                await _fetch_and_store(client, region)
            except Exception as exc:
                log.warning("openmeteo_region_error", region=region["name"], error=str(exc))


async def _fetch_and_store(client: httpx.AsyncClient, region: dict) -> None:
    params = {
        "latitude": region["lat"],
        "longitude": region["lon"],
        "hourly": "temperature_2m,precipitation,soil_moisture_0_to_1cm,et0_fao_evapotranspiration,wind_speed_10m",
        "timezone": "UTC",
        "forecast_days": 1,
        "past_days": 0,
    }
    resp = await client.get(_BASE, params=params)
    resp.raise_for_status()
    data = resp.json()

    hourly = data["hourly"]
    times: list[str] = hourly["time"]

    # Find the index for the current UTC hour
    now_hour = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:00")
    try:
        idx = times.index(now_hour)
    except ValueError:
        # Fall back to the last available entry
        idx = len(times) - 1

    def _val(key: str) -> float | None:
        vals = hourly.get(key, [])
        v = vals[idx] if idx < len(vals) else None
        return float(v) if v is not None else None

    ts = datetime.strptime(times[idx], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)

    await insert_weather_regional(
        time=ts,
        region=region["name"],
        temp_c=_val("temperature_2m"),
        precip_mm=_val("precipitation"),
        soil_moisture=_val("soil_moisture_0_to_1cm"),
        et0=_val("et0_fao_evapotranspiration"),
        wind_speed_10m=_val("wind_speed_10m"),
    )

    log.info(
        "openmeteo_region_ok",
        region=region["name"],
        time=ts.isoformat(),
        temp_c=_val("temperature_2m"),
        precip_mm=_val("precipitation"),
    )
