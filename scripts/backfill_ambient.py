"""Back-fill historical Ambient Weather data.

Fetches up to --days of 5-min data from the Ambient Weather API and
inserts it into weather_station_local. Safe to re-run; duplicate
timestamps are ignored (ON CONFLICT DO NOTHING).

Rate limit: Ambient allows 1 req/sec. This script sleeps 1.1s between
requests. A full 30-day backfill takes ~2 minutes.

Usage:
    docker compose exec fastapi python scripts/backfill_ambient.py
    docker compose exec fastapi python scripts/backfill_ambient.py --days 7
    docker compose exec fastapi python scripts/backfill_ambient.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx
import structlog

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from farm_platform.config import settings
from farm_platform.storage.timescale import get_pool, close_pool, insert_weather_local

log = structlog.get_logger(__name__)

_BASE = "https://rt.ambientweather.net/v1"


def _parse_record(d: dict) -> dict | None:
    """Extract outdoor fields from a raw Ambient data record."""
    if "dateutc" not in d:
        return None

    def _f(key: str) -> float | None:
        v = d.get(key)
        return float(v) if v is not None else None

    def _i(key: str) -> int | None:
        v = d.get(key)
        return int(v) if v is not None else None

    ts = datetime.fromtimestamp(d["dateutc"] / 1000, tz=timezone.utc)
    return dict(
        time=ts,
        temp_f=_f("tempf"),
        humidity=_f("humidity"),
        rain_hourly=_f("hourlyrainin"),
        rain_daily=_f("dailyrainin"),
        wind_speed=_f("windspdmph_avg10m") or _f("windspeedmph"),
        wind_dir=_i("winddir_avg10m") or _i("winddir"),
        solar_rad=_f("solarradiation"),
        baro_rel=_f("baromrelin"),
        soil_temp_1=None,
        wind_gust_mph=_f("windgustmph"),
        dew_point_f=_f("dewPoint"),
        uv_index=_i("uv"),
        lightning_day=_i("lightning_day"),
        lightning_distance_mi=_f("lightning_distance"),
    )


async def backfill(days: int, dry_run: bool) -> None:
    cfg = settings.ambient
    if not cfg.api_key or not cfg.app_key:
        log.error("backfill_aborted", reason="AMBIENT_API_KEY / AMBIENT_APP_KEY not set")
        return

    mac = cfg.station_mac.upper()
    cutoff_ms = int((datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    end_date_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    total_inserted = 0
    total_skipped = 0
    page = 0

    async with httpx.AsyncClient(timeout=20) as client:
        while True:
            page += 1
            url = (
                f"{_BASE}/devices/{mac}"
                f"?applicationKey={cfg.app_key}&apiKey={cfg.api_key}"
                f"&limit=288&endDate={end_date_ms}"
            )

            try:
                resp = await client.get(url)
                resp.raise_for_status()
                records = resp.json()
            except Exception as exc:
                log.error("backfill_fetch_error", page=page, error=str(exc))
                break

            if not records:
                log.info("backfill_no_more_records", page=page)
                break

            log.info("backfill_page", page=page, count=len(records),
                     oldest=datetime.fromtimestamp(records[-1]["dateutc"] / 1000, tz=timezone.utc).isoformat())

            for raw in records:
                parsed = _parse_record(raw)
                if parsed is None:
                    total_skipped += 1
                    continue

                if dry_run:
                    print(f"  {parsed['time'].isoformat()}  temp={parsed['temp_f']}°F  "
                          f"wind={parsed['wind_speed']}mph  rain={parsed['rain_daily']}in")
                    total_inserted += 1
                else:
                    await insert_weather_local(**parsed)
                    total_inserted += 1

            oldest_ms = records[-1]["dateutc"]
            if oldest_ms <= cutoff_ms:
                log.info("backfill_reached_cutoff", cutoff_days=days)
                break

            end_date_ms = oldest_ms - 1
            await asyncio.sleep(1.1)  # respect 1 req/sec rate limit

    log.info(
        "backfill_complete",
        pages=page,
        inserted=total_inserted,
        skipped=total_skipped,
        dry_run=dry_run,
    )
    print(f"\n{'DRY RUN — ' if dry_run else ''}Done: {total_inserted} records over {page} API pages.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Back-fill Ambient Weather historical data")
    parser.add_argument("--days", type=int, default=30, help="Days of history to fetch (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing to DB")
    args = parser.parse_args()

    if not args.dry_run:
        await get_pool()

    await backfill(args.days, args.dry_run)

    if not args.dry_run:
        await close_pool()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level="INFO")
    asyncio.run(main())
