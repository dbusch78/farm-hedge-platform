"""Ambient Weather REST feed — polls the farm station every N minutes.

Only the outdoor station fields are stored. Indoor channel sensors
(temp3f–temp6f: freezer, fridge, indoor rooms) are intentionally ignored.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from farm_platform.config import settings
from farm_platform.storage.timescale import insert_weather_local

log = structlog.get_logger(__name__)

_BASE = "https://rt.ambientweather.net/v1"


async def run_once() -> None:
    cfg = settings.ambient
    if not cfg.api_key or not cfg.app_key:
        log.debug("ambient_feed_skipped", reason="API keys not configured")
        return

    mac = cfg.station_mac.upper()
    url = (
        f"{_BASE}/devices/{mac}"
        f"?applicationKey={cfg.app_key}&apiKey={cfg.api_key}&limit=1"
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            records = resp.json()
    except Exception as exc:
        log.warning("ambient_feed_error", error=str(exc))
        return

    if not records:
        log.warning("ambient_feed_empty", mac=mac)
        return

    d = records[0]
    # dateutc is milliseconds since epoch
    ts = datetime.fromtimestamp(d["dateutc"] / 1000, tz=timezone.utc)

    def _f(key: str) -> float | None:
        v = d.get(key)
        return float(v) if v is not None else None

    def _i(key: str) -> int | None:
        v = d.get(key)
        return int(v) if v is not None else None

    await insert_weather_local(
        time=ts,
        temp_f=_f("tempf"),
        humidity=_f("humidity"),
        rain_hourly=_f("hourlyrainin"),
        rain_daily=_f("dailyrainin"),
        # Use 10-min averages for smoother wind readings
        wind_speed=_f("windspdmph_avg10m") or _f("windspeedmph"),
        wind_dir=_i("winddir_avg10m") or _i("winddir"),
        solar_rad=_f("solarradiation"),
        baro_rel=_f("baromrelin"),
        soil_temp_1=None,  # no soil probe on this station
        wind_gust_mph=_f("windgustmph"),
        dew_point_f=_f("dewPoint"),
        uv_index=_i("uv"),
        lightning_day=_i("lightning_day"),
        lightning_distance_mi=_f("lightning_distance"),
    )

    log.info(
        "ambient_feed_ok",
        time=ts.isoformat(),
        temp_f=d.get("tempf"),
        wind_mph=d.get("windspdmph_avg10m"),
        rain_daily=d.get("dailyrainin"),
        lightning_day=d.get("lightning_day"),
    )
