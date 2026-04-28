"""AsyncPG connection pool and write/query helpers for TimescaleDB."""

from __future__ import annotations

from datetime import datetime

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
