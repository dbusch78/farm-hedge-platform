"""yfinance futures price feed for ZC=F, ZS=F, ZW=F.

Pulls OHLCV on a configurable interval during market hours and writes rows
to the futures_prices hypertable. Sets stale=True if the pull fails; never
crashes the scheduler.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog
import yfinance as yf

from farm_platform.config import settings
from farm_platform.storage.timescale import get_latest_futures, upsert_futures_price

log = structlog.get_logger(__name__)

SYMBOLS: list[str] = ["ZC=F", "ZS=F", "ZW=F"]

# Callback registry: any async callable(symbol, price_row) is notified after
# each successful write so the WebSocket broadcaster can forward updates.
_price_callbacks: list[Any] = []


def register_price_callback(cb: Any) -> None:
    _price_callbacks.append(cb)


async def _notify(symbol: str, row: dict[str, Any]) -> None:
    for cb in _price_callbacks:
        try:
            await cb(symbol, row)
        except Exception:
            log.exception("price_callback_error", symbol=symbol)


async def pull_symbol(symbol: str) -> dict[str, Any] | None:
    """Fetch the latest OHLCV bar for one symbol. Returns None on failure."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="15m")
        if hist.empty:
            log.warning("futures_feed_empty", symbol=symbol)
            return None
        row = hist.iloc[-1]
        return {
            "time": datetime.now(tz=timezone.utc),
            "symbol": symbol,
            "open": float(row["Open"]) if "Open" in row else None,
            "high": float(row["High"]) if "High" in row else None,
            "low": float(row["Low"]) if "Low" in row else None,
            "close": float(row["Close"]) if "Close" in row else None,
            "volume": int(row["Volume"]) if "Volume" in row else None,
            "stale": False,
        }
    except Exception:
        log.exception("futures_feed_pull_error", symbol=symbol)
        return None


async def pull_and_store(symbol: str) -> None:
    """Pull one symbol, write to TimescaleDB, notify callbacks."""
    data = await pull_symbol(symbol)

    if data is None:
        # Fetch last known price and re-write with stale=True
        last = await get_latest_futures(symbol)
        if last is not None:
            await upsert_futures_price(
                time=datetime.now(tz=timezone.utc),
                symbol=symbol,
                open=last["open"],
                high=last["high"],
                low=last["low"],
                close=last["close"],
                volume=last["volume"],
                stale=True,
            )
            log.warning("futures_feed_stale_written", symbol=symbol)
        return

    await upsert_futures_price(**data)
    log.info("futures_price_written", symbol=symbol, close=data["close"])
    await _notify(symbol, data)


async def run_once() -> None:
    """Pull all symbols once. Used by the APScheduler job."""
    await asyncio.gather(*[pull_and_store(s) for s in SYMBOLS])


# ── APScheduler job entrypoint ───────────────────────────────────────────────

def scheduled_pull() -> None:
    """Synchronous wrapper called by APScheduler (runs in thread pool)."""
    asyncio.get_event_loop().run_until_complete(run_once())
