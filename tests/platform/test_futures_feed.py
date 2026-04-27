"""Unit tests for farm_platform.feeds.futures_feed.

Verifies that pull_and_store() calls upsert_futures_price with a datetime
instance (not a string) for the time argument -- asyncpg requires datetime
objects for TIMESTAMPTZ columns and will raise DataError on strings.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from farm_platform.feeds.futures_feed import pull_and_store


FAKE_TICKER_RESPONSE = {
    "Open": 450.25,
    "High": 452.00,
    "Low": 449.50,
    "Close": 451.00,
    "Volume": 12345,
}


def _make_fake_hist() -> object:
    """Return a minimal DataFrame-like object that pull_symbol() can consume."""
    import pandas as pd

    return pd.DataFrame([FAKE_TICKER_RESPONSE])


@pytest.mark.asyncio
async def test_upsert_called_with_datetime_not_string() -> None:
    """time argument passed to upsert_futures_price must be a datetime instance."""
    fake_hist = _make_fake_hist()

    with (
        patch(
            "farm_platform.feeds.futures_feed.yf.Ticker",
        ) as mock_ticker,
        patch(
            "farm_platform.feeds.futures_feed.upsert_futures_price",
            new_callable=AsyncMock,
        ) as mock_upsert,
    ):
        mock_ticker.return_value.history.return_value = fake_hist
        await pull_and_store("ZC=F")

    assert mock_upsert.called, "upsert_futures_price was not called"
    call_kwargs = mock_upsert.call_args.kwargs
    assert isinstance(call_kwargs["time"], datetime), (
        f"Expected datetime, got {type(call_kwargs['time'])}: {call_kwargs['time']!r}"
    )


@pytest.mark.asyncio
async def test_stale_upsert_called_with_datetime_not_string() -> None:
    """Stale-price fallback path also passes a datetime to upsert_futures_price."""
    import asyncpg

    fake_last = AsyncMock(spec=asyncpg.Record)
    fake_last.__getitem__ = lambda self, k: {
        "open": 450.0, "high": 452.0, "low": 449.0,
        "close": 451.0, "volume": 1000,
    }[k]

    with (
        patch(
            "farm_platform.feeds.futures_feed.yf.Ticker",
        ) as mock_ticker,
        patch(
            "farm_platform.feeds.futures_feed.get_latest_futures",
            new_callable=AsyncMock,
            return_value=fake_last,
        ),
        patch(
            "farm_platform.feeds.futures_feed.upsert_futures_price",
            new_callable=AsyncMock,
        ) as mock_upsert,
    ):
        # Make yfinance return empty so the stale path is triggered
        import pandas as pd
        mock_ticker.return_value.history.return_value = pd.DataFrame()

        await pull_and_store("ZC=F")

    assert mock_upsert.called, "upsert_futures_price was not called on stale path"
    call_kwargs = mock_upsert.call_args.kwargs
    assert isinstance(call_kwargs["time"], datetime), (
        f"Stale path: expected datetime, got {type(call_kwargs['time'])}: {call_kwargs['time']!r}"
    )
