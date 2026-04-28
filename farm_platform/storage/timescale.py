"""AsyncPG connection pool and write/query helpers for TimescaleDB."""

from __future__ import annotations

from datetime import date, datetime

import asyncpg
import structlog
from asyncpg import Connection, Pool

from farm_platform.config import settings

log = structlog.get_logger(__name__)

_pool: Pool | None = None


async def get_pool() -> Pool:
    """Return the global connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.db.dsn,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        log.info("timescaledb_pool_created")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("timescaledb_pool_closed")


async def execute(sql: str, *args: object) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        conn: Connection
        await conn.execute(sql, *args)


async def fetch(sql: str, *args: object) -> list[asyncpg.Record]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(sql, *args)


async def fetchrow(sql: str, *args: object) -> asyncpg.Record | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(sql, *args)


# ── Futures prices ──────────────────────────────────────────────────────────

async def upsert_futures_price(
    *,
    time: datetime,
    symbol: str,
    open: float | None,
    high: float | None,
    low: float | None,
    close: float | None,
    volume: int | None,
    stale: bool = False,
) -> None:
    await execute(
        """
        INSERT INTO futures_prices (time, symbol, open, high, low, close, volume, stale)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT DO NOTHING
        """,
        time, symbol, open, high, low, close, volume, stale,
    )


async def get_latest_futures(symbol: str) -> asyncpg.Record | None:
    return await fetchrow(
        "SELECT * FROM futures_prices WHERE symbol = $1 ORDER BY time DESC LIMIT 1",
        symbol,
    )


async def get_futures_history(symbol: str, days: int = 90) -> list[asyncpg.Record]:
    return await fetch(
        """
        SELECT time, open, high, low, close, volume, stale
        FROM futures_prices
        WHERE symbol = $1
          AND time >= NOW() - ($2 || ' days')::INTERVAL
        ORDER BY time ASC
        """,
        symbol, str(days),
    )


# ── Cash prices ─────────────────────────────────────────────────────────────

async def insert_cash_price(
    *,
    time: datetime,
    elevator: str,
    commodity: str,
    cash_price: float,
    futures_ref: float | None,
    basis: float | None,
    contract_month: str | None,
) -> None:
    await execute(
        """
        INSERT INTO cash_prices
            (time, elevator, commodity, cash_price, futures_ref, basis, contract_month)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        time, elevator, commodity, cash_price, futures_ref, basis, contract_month,
    )


async def get_latest_cash(elevator: str, commodity: str) -> asyncpg.Record | None:
    return await fetchrow(
        """
        SELECT * FROM cash_prices
        WHERE elevator = $1 AND commodity = $2
        ORDER BY time DESC LIMIT 1
        """,
        elevator, commodity,
    )


async def get_basis_history(
    commodity: str, days: int = 180, elevator: str | None = None
) -> list[asyncpg.Record]:
    if elevator:
        return await fetch(
            """
            SELECT time, elevator, commodity, cash_price, futures_ref, basis
            FROM cash_prices
            WHERE commodity = $1
              AND elevator = $2
              AND time >= NOW() - ($3 || ' days')::INTERVAL
            ORDER BY time ASC
            """,
            commodity, elevator, str(days),
        )
    return await fetch(
        """
        SELECT time, elevator, commodity, cash_price, futures_ref, basis
        FROM cash_prices
        WHERE commodity = $1
          AND time >= NOW() - ($2 || ' days')::INTERVAL
        ORDER BY time ASC
        """,
        commodity, str(days),
    )


async def get_nep_history(days: int = 365) -> list[asyncpg.Record]:
    return await fetch(
        """
        SELECT time, position_id, underlying_px, net_eff_price, pnl_per_bushel, premium_paid
        FROM options_snapshots
        WHERE time >= NOW() - ($1 || ' days')::INTERVAL
        ORDER BY time ASC
        """,
        str(days),
    )


async def get_elevator_names() -> list[str]:
    rows = await fetch("SELECT DISTINCT elevator FROM cash_prices ORDER BY elevator")
    return [r["elevator"] for r in rows]


# ── Options snapshots ────────────────────────────────────────────────────────

async def insert_weather_local(
    *,
    time: datetime,
    temp_f: float | None,
    humidity: float | None,
    rain_hourly: float | None,
    rain_daily: float | None,
    wind_speed: float | None,
    wind_dir: int | None,
    solar_rad: float | None,
    baro_rel: float | None,
    soil_temp_1: float | None = None,
    wind_gust_mph: float | None = None,
    dew_point_f: float | None = None,
    uv_index: int | None = None,
    lightning_day: int | None = None,
    lightning_distance_mi: float | None = None,
) -> None:
    await execute(
        """
        INSERT INTO weather_station_local
            (time, temp_f, humidity, rain_hourly, rain_daily, wind_speed, wind_dir,
             solar_rad, baro_rel, soil_temp_1, wind_gust_mph, dew_point_f, uv_index,
             lightning_day, lightning_distance_mi)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        ON CONFLICT DO NOTHING
        """,
        time, temp_f, humidity, rain_hourly, rain_daily, wind_speed, wind_dir,
        solar_rad, baro_rel, soil_temp_1, wind_gust_mph, dew_point_f, uv_index,
        lightning_day, lightning_distance_mi,
    )


async def get_latest_weather_local() -> asyncpg.Record | None:
    return await fetchrow(
        "SELECT * FROM weather_station_local ORDER BY time DESC LIMIT 1"
    )


async def get_weather_local_history(days: int = 7) -> list[asyncpg.Record]:
    return await fetch(
        """
        SELECT time, temp_f, humidity, rain_hourly, rain_daily, wind_speed,
               wind_dir, solar_rad, baro_rel, wind_gust_mph, dew_point_f,
               uv_index, lightning_day, lightning_distance_mi
        FROM weather_station_local
        WHERE time >= NOW() - ($1 || ' days')::INTERVAL
        ORDER BY time ASC
        """,
        str(days),
    )


async def get_rain_totals() -> dict:
    """Return month-to-date and year-to-date rain totals from stored daily readings.

    Ambient's rain_daily resets to 0 at midnight local time, so the max value
    per calendar day is the total for that day. We sum the per-day maxima.
    """
    row = await fetchrow(
        """
        SELECT
          SUM(day_rain) FILTER (WHERE day >= date_trunc('month', NOW() AT TIME ZONE 'America/Chicago'))
            AS mtd_rain,
          SUM(day_rain) FILTER (WHERE day >= date_trunc('year',  NOW() AT TIME ZONE 'America/Chicago'))
            AS ytd_rain
        FROM (
          SELECT
            time::date AS day,
            MAX(rain_daily) AS day_rain
          FROM weather_station_local
          GROUP BY time::date
        ) daily
        """
    )
    return {
        "mtd_in": round(float(row["mtd_rain"]), 2) if row and row["mtd_rain"] is not None else None,
        "ytd_in": round(float(row["ytd_rain"]), 2) if row and row["ytd_rain"] is not None else None,
    }


async def insert_weather_regional(
    *,
    time: datetime,
    region: str,
    temp_c: float | None,
    precip_mm: float | None,
    soil_moisture: float | None,
    et0: float | None,
    wind_speed_10m: float | None,
) -> None:
    await execute(
        """
        INSERT INTO weather_regional (time, region, temp_c, precip_mm, soil_moisture, et0, wind_speed_10m)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT DO NOTHING
        """,
        time, region, temp_c, precip_mm, soil_moisture, et0, wind_speed_10m,
    )


async def get_latest_weather_regional(region: str) -> asyncpg.Record | None:
    return await fetchrow(
        "SELECT * FROM weather_regional WHERE region = $1 ORDER BY time DESC LIMIT 1",
        region,
    )


async def get_all_regional_history(days: int = 180) -> list[asyncpg.Record]:
    return await fetch(
        """
        SELECT time, region, temp_c, precip_mm, soil_moisture, et0, wind_speed_10m
        FROM weather_regional
        WHERE time >= NOW() - ($1 || ' days')::INTERVAL
        ORDER BY time ASC
        """,
        str(days),
    )


async def get_gdu_history(days: int = 180) -> list[asyncpg.Record]:
    return await fetch(
        """
        SELECT day, avg_temp_f, gdu
        FROM gdu_daily
        WHERE day >= NOW() - ($1 || ' days')::INTERVAL
        ORDER BY day ASC
        """,
        str(days),
    )


# ── Planting dates ───────────────────────────────────────────────────────────

async def get_planting_dates() -> list[asyncpg.Record]:
    return await fetch(
        "SELECT commodity, year, planted_date, notes FROM planting_dates ORDER BY year DESC, commodity ASC"
    )


async def get_planting_date(commodity: str, year: int) -> asyncpg.Record | None:
    return await fetchrow(
        "SELECT commodity, year, planted_date, notes FROM planting_dates WHERE commodity = $1 AND year = $2",
        commodity,
        year,
    )


async def upsert_planting_date(
    *,
    commodity: str,
    year: int,
    planted_date: date,
    notes: str | None = None,
) -> None:
    await execute(
        """
        INSERT INTO planting_dates (commodity, year, planted_date, notes)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (commodity, year) DO UPDATE
          SET planted_date = EXCLUDED.planted_date,
              notes        = EXCLUDED.notes
        """,
        commodity,
        year,
        planted_date,
        notes,
    )


async def delete_planting_date(commodity: str, year: int) -> None:
    await execute(
        "DELETE FROM planting_dates WHERE commodity = $1 AND year = $2",
        commodity,
        year,
    )


# ── Options snapshots ────────────────────────────────────────────────────────

async def insert_options_snapshot(
    *,
    time: datetime,
    position_id: str,
    underlying_px: float,
    option_px: float | None,
    delta: float | None,
    premium_paid: float | None,
    pnl_per_bushel: float | None,
    net_eff_price: float | None,
) -> None:
    await execute(
        """
        INSERT INTO options_snapshots
            (time, position_id, underlying_px, option_px, delta,
             premium_paid, pnl_per_bushel, net_eff_price)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        time, position_id, underlying_px, option_px, delta,
        premium_paid, pnl_per_bushel, net_eff_price,
    )
