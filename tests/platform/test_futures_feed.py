"""Unit tests for farm_platform.feeds.futures_feed.

Covers:
  1. time argument is a datetime (asyncpg requires TIMESTAMPTZ, not str)
  2. OHLC values are divided by 100 before storage (cents → dollars)
  3. Dollar-range assertion: stored close must be in $1–$50 range, never
     in the 100–2000 range that indicates raw exchange cents
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from farm_platform.feeds.futures_feed import pull_and_store, pull_symbol


# ── Shared fake yfinance response (exchange cents, as yfinance returns) ───────
#
# Real-world examples:
#   ZC=F  ≈ 473 cents  =  $4.73 / bu
#   ZS=F  ≈ 1185 cents = $11.85 / bu
#   ZW=F  ≈ 649 cents  =  $6.49 / bu
#
# The feed must divide by 100 before writing.

FAKE_ZC_CENTS = {"Open": 470.25, "High": 475.00, "Low": 469.50, "Close": 473.75, "Volume": 12345}
FAKE_ZS_CENTS = {"Open": 1180.0, "High": 1192.5, "Low": 1178.0, "Close": 1185.0, "Volume": 8000}
FAKE_ZW_CENTS = {"Open": 645.0,  "High": 652.0,  "Low": 644.0,  "Close": 649.0,  "Volume": 5000}


def _hist(row: dict) -> pd.DataFrame:
    return pd.DataFrame([row])


# ── 1. time argument must be a datetime ──────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_called_with_datetime_not_string() -> None:
    """time argument passed to upsert_futures_price must be a datetime instance."""
    with (
        patch("farm_platform.feeds.futures_feed.yf.Ticker") as mock_ticker,
        patch("farm_platform.feeds.futures_feed.upsert_futures_price", new_callable=AsyncMock) as mock_upsert,
    ):
        mock_ticker.return_value.history.return_value = _hist(FAKE_ZC_CENTS)
        await pull_and_store("ZC=F")

    assert mock_upsert.called
    assert isinstance(mock_upsert.call_args.kwargs["time"], datetime), (
        f"Expected datetime for 'time', got {type(mock_upsert.call_args.kwargs['time'])}"
    )


@pytest.mark.asyncio
async def test_stale_upsert_called_with_datetime_not_string() -> None:
    """Stale fallback path also passes a datetime to upsert_futures_price."""
    import asyncpg

    fake_last = AsyncMock(spec=asyncpg.Record)
    fake_last.__getitem__ = lambda self, k: {
        "open": 4.70, "high": 4.75, "low": 4.69, "close": 4.73, "volume": 1000,
    }[k]

    with (
        patch("farm_platform.feeds.futures_feed.yf.Ticker") as mock_ticker,
        patch("farm_platform.feeds.futures_feed.get_latest_futures", new_callable=AsyncMock, return_value=fake_last),
        patch("farm_platform.feeds.futures_feed.upsert_futures_price", new_callable=AsyncMock) as mock_upsert,
    ):
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        await pull_and_store("ZC=F")

    assert mock_upsert.called
    assert isinstance(mock_upsert.call_args.kwargs["time"], datetime), (
        f"Stale path: expected datetime, got {type(mock_upsert.call_args.kwargs['time'])}"
    )


# ── 2. Cents-to-dollars conversion ───────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("symbol,fake_cents,expected_close", [
    ("ZC=F", FAKE_ZC_CENTS, 4.7375),
    ("ZS=F", FAKE_ZS_CENTS, 11.85),
    ("ZW=F", FAKE_ZW_CENTS, 6.49),
])
async def test_ohlc_divided_by_100(symbol: str, fake_cents: dict, expected_close: float) -> None:
    """Feed must store prices in dollars, not exchange cents."""
    with (
        patch("farm_platform.feeds.futures_feed.yf.Ticker") as mock_ticker,
        patch("farm_platform.feeds.futures_feed.upsert_futures_price", new_callable=AsyncMock) as mock_upsert,
    ):
        mock_ticker.return_value.history.return_value = _hist(fake_cents)
        await pull_and_store(symbol)

    kw = mock_upsert.call_args.kwargs
    assert abs(kw["close"] - expected_close) < 0.001, (
        f"{symbol}: expected close ${expected_close}, got {kw['close']} — "
        "divide-by-100 conversion may be missing"
    )
    assert abs(kw["open"]  - fake_cents["Open"]  / 100) < 0.001
    assert abs(kw["high"]  - fake_cents["High"]  / 100) < 0.001
    assert abs(kw["low"]   - fake_cents["Low"]   / 100) < 0.001


# ── 3. Dollar-range assertions (regression guard) ────────────────────────────
#
# If a future data source regression causes cents to leak into storage,
# these tests will catch it even if the exact value changes.

@pytest.mark.asyncio
@pytest.mark.parametrize("symbol,fake_cents,lo,hi", [
    ("ZC=F", FAKE_ZC_CENTS, 3.0,  8.0),
    ("ZS=F", FAKE_ZS_CENTS, 8.0, 18.0),
    ("ZW=F", FAKE_ZW_CENTS, 4.0, 12.0),
])
async def test_stored_close_in_dollar_range(
    symbol: str, fake_cents: dict, lo: float, hi: float
) -> None:
    """Stored close price must be in the dollar-per-bushel range, never cents.

    If this assertion fails with a value like 473 instead of 4.73, the
    divide-by-100 conversion at the feed boundary is missing or broken.
    """
    with (
        patch("farm_platform.feeds.futures_feed.yf.Ticker") as mock_ticker,
        patch("farm_platform.feeds.futures_feed.upsert_futures_price", new_callable=AsyncMock) as mock_upsert,
    ):
        mock_ticker.return_value.history.return_value = _hist(fake_cents)
        await pull_and_store(symbol)

    close = mock_upsert.call_args.kwargs["close"]
    assert lo < close < hi, (
        f"{symbol}: stored close {close} is outside the expected dollar range "
        f"${lo}–${hi}/bu. This almost certainly means the value is in cents, "
        "not dollars. Conversion at the ingestion boundary is missing or broken."
    )


# ── 4. pull_symbol unit test (no I/O) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_pull_symbol_returns_dollars() -> None:
    """pull_symbol() must return a dict with close in dollars, not cents."""
    with patch("farm_platform.feeds.futures_feed.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = _hist(FAKE_ZC_CENTS)
        result = await pull_symbol("ZC=F")

    assert result is not None
    assert 3.0 < result["close"] < 8.0, (
        f"pull_symbol returned close={result['close']} — expected dollars in "
        f"$3–$8 range for ZC=F, not exchange cents"
    )
    # All OHLC fields converted
    for field in ("open", "high", "low", "close"):
        assert result[field] < 50.0, (
            f"Field '{field}' = {result[field]} looks like cents, not dollars"
        )
