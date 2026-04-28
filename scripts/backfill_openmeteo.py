"""Back-fill regional weather data from Open-Meteo ERA5 archive.

For each region, checks the earliest record already in weather_regional and
only fetches dates not yet covered. Safe to re-run; duplicate rows are
ignored (ON CONFLICT DO NOTHING).

ERA5 is free, no API key required. Rate limit is generous but we sleep 0.5s
between region calls out of courtesy.

Usage:
    docker compose exec fastapi python scripts/backfill_openmeteo.py
    docker compose exec fastapi python scripts/backfill_openmeteo.py --days 365
    docker compose exec fastapi python scripts/backfill_openmeteo.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys
from datetime import date, datetime, timedelta, timezone

import httpx
import structlog

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from farm_platform.storage.timescale import fetch, get_pool, close_pool, insert_weather_regional

log = structlog.get_logger(__name__)

_ERA5_BASE = "https://archive-api.open-meteo.com/v1/era5"

REGIONS = [
    {"name": "corn_belt",   "lat":  41.5, "lon":  -93.5},
    {"name": "mato_grosso", "lat": -12.5, "lon":  -55.5},
    {"name": "parana",      "lat": -23.5, "lon":  -51.5},
    {"name": "pampas",      "lat": -34.5, "lon":  -60.5},
]


async def _get_coverage(region: str) -> tuple[date | None, date | None]:
    """Return (oldest_date, newest_date) for a region, or (None, None) if empty."""
    rows = await fetch(
        "SELECT MIN(time)::date AS oldest, MAX(time)::date AS newest "
        "FROM weather_regional WHERE region = $1",
        region,
    )
    if not rows or rows[0]["oldest"] is None:
        return None, None
    return rows[0]["oldest"], rows[0]["newest"]


async def _fetch_era5(
    client: httpx.AsyncClient,
    region: dict,
    start: date,
    end: date,
    dry_run: bool,
) -> int:
    """Fetch hourly ERA5 data for one region/date range and insert into DB."""
    params = {
        "latitude": region["lat"],
        "longitude": region["lon"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": "temperature_2m,precipitation,soil_moisture_0_to_1cm,et0_fao_evapotranspiration,wind_speed_10m",
        "timezone": "UTC",
    }

    resp = await client.get(_ERA5_BASE, params=params)
    resp.raise_for_status()
    data = resp.json()

    hourly = data["hourly"]
    times: list[str] = hourly["time"]

    count = 0
    for i, t_str in enumerate(times):
        ts = datetime.strptime(t_str, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)

        def _val(key: str) -> float | None:
            vals = hourly.get(key, [])
            v = vals[i] if i < len(vals) else None
            return float(v) if v is not None else None

        if dry_run:
            print(
                f"  {ts.isoformat()}  {region['name']}  "
                f"temp={_val('temperature_2m')}°C  "
                f"precip={_val('precipitation')}mm"
            )
        else:
            await insert_weather_regional(
                time=ts,
                region=region["name"],
                temp_c=_val("temperature_2m"),
                precip_mm=_val("precipitation"),
                soil_moisture=_val("soil_moisture_0_to_1cm"),
                et0=_val("et0_fao_evapotranspiration"),
                wind_speed_10m=_val("wind_speed_10m"),
            )
        count += 1

    return count


async def backfill(days: int, dry_run: bool) -> None:
    today = date.today()
    cutoff = today - timedelta(days=days)

    for region in REGIONS:
        oldest_in_db, newest_in_db = await _get_coverage(region["name"])

        if oldest_in_db is None:
            # No data at all — fetch full range
            fetch_start = cutoff
            fetch_end = today - timedelta(days=1)  # ERA5 lags ~1 day
        else:
            # Only fetch what's missing before the oldest record
            if oldest_in_db <= cutoff:
                log.info(
                    "backfill_already_covered",
                    region=region["name"],
                    oldest=oldest_in_db.isoformat(),
                    cutoff=cutoff.isoformat(),
                )
                print(f"  {region['name']}: already covered back to {oldest_in_db} — skipping")
                continue
            fetch_start = cutoff
            fetch_end = oldest_in_db - timedelta(days=1)

        if fetch_start > fetch_end:
            print(f"  {region['name']}: nothing to fetch (start={fetch_start} > end={fetch_end})")
            continue

        log.info(
            "backfill_fetching",
            region=region["name"],
            start=fetch_start.isoformat(),
            end=fetch_end.isoformat(),
        )
        print(f"  {region['name']}: fetching {fetch_start} → {fetch_end} ...")

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                count = await _fetch_era5(client, region, fetch_start, fetch_end, dry_run)
                print(f"    → {count} hourly records {'(dry run)' if dry_run else 'inserted'}")
            except Exception as exc:
                log.error("backfill_region_error", region=region["name"], error=str(exc))
                print(f"    ERROR: {exc}")

        await asyncio.sleep(0.5)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Back-fill Open-Meteo ERA5 regional weather data")
    parser.add_argument("--days", type=int, default=180, help="Days of history to fetch (default: 180)")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing to DB")
    args = parser.parse_args()

    if not args.dry_run:
        await get_pool()

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Backfilling up to {args.days} days of ERA5 regional data...\n")
    await backfill(args.days, args.dry_run)
    print("\nDone.")

    if not args.dry_run:
        await close_pool()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level="INFO")
    asyncio.run(main())
