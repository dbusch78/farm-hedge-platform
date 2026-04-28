"""Regression test for /net-price commodity aggregation.

Previously, get_net_prices() returned one row per position. The frontend's
.find() picked only the first matching commodity, silently dropping the rest.
This test locks in the correct weighted-average aggregation.

Design note: positions with deliberately divergent P&L per bushel are used
so that dropping any single position produces a noticeably wrong aggregate —
bugs in aggregation logic hide when inputs are similar and reveal themselves
when inputs are diverse.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.routers.hedge import get_net_prices

# ── Fixture data (matches real ZSN26 positions from test_calculator.py) ────────
#
# ZSN26 C $10.25: 3 contracts (15,000 bu), $0.40 premium, cash $10.34
#   At futures $11.87: intrinsic $1.62, call_pnl ≈ +$1.22/bu
#
# ZSN26 C $11.75: 1 contract (5,000 bu), $0.35 premium, cash $11.33
#   At futures $11.87: intrinsic $0.12, call_pnl ≈ -$0.23/bu
#
# Weighted blend (by raw_contracts: 3.0 and 1.0):
#   (3.0 × 1.22 + 1.0 × -0.23) / 4.0 = +$0.8575/bu

FUTURES_PRICE = 11.87

POS_A = {
    "commodity": "ZS",
    "phase": 2,
    "strike": 10.25,
    "premium_paid_per_bu": 0.40,
    "expected_bushels": 15_000,
    "delta_at_entry": 0.54,
    "cash_sale_price": 10.34,
    "status": "ACTIVE",
}

POS_B = {
    "commodity": "ZS",
    "phase": 2,
    "strike": 11.75,
    "premium_paid_per_bu": 0.35,
    "expected_bushels": 5_000,
    "delta_at_entry": 0.51,
    "cash_sale_price": 11.33,
    "status": "ACTIVE",
}

FAKE_LATEST = {"close": FUTURES_PRICE, "stale": False}

# A Phase 1 put position — must NOT be merged with Phase 2 calls even in same commodity.
ZC_PUT = {
    "commodity": "ZC",
    "phase": 1,
    "strike": 4.50,
    "premium_paid_per_bu": 0.09,
    "expected_bushels": 30_000,
    "delta_at_entry": 0.22,
    "cash_sale_price": None,
    "status": "ACTIVE",
}

ZC_CALL = {
    "commodity": "ZC",
    "phase": 2,
    "strike": 4.50,
    "premium_paid_per_bu": 0.08,
    "expected_bushels": 30_000,
    "delta_at_entry": 0.50,
    "cash_sale_price": 4.69,
    "status": "ACTIVE",
}

ZC_FUTURES = {"close": 4.72, "stale": False}


@pytest.mark.asyncio
async def test_single_row_returned_per_commodity_phase() -> None:
    """Two positions with same commodity AND phase must collapse to one row."""
    with (
        patch("backend.routers.hedge.get_all_positions", new_callable=AsyncMock, return_value=[POS_A, POS_B]),
        patch("backend.routers.hedge.get_latest_futures", new_callable=AsyncMock, return_value=FAKE_LATEST),
    ):
        result = await get_net_prices()

    zs_rows = [r for r in result if r["commodity"] == "ZS" and r["phase"] == 2]
    assert len(zs_rows) == 1, (
        f"Expected 1 ZS phase-2 row after aggregation, got {len(zs_rows)}. "
        "Multiple same-phase positions per commodity must collapse to one weighted-average row."
    )


@pytest.mark.asyncio
async def test_options_pnl_is_weighted_by_raw_contracts() -> None:
    """options_pnl_per_bu must be a weighted average by raw_contracts, not a first-match or simple average.

    POS_A: raw=3.0, call_pnl≈+1.22/bu
    POS_B: raw=1.0, call_pnl≈-0.23/bu
    Weighted: (3.0×1.22 + 1.0×-0.23) / 4.0 ≈ +0.858/bu

    First-match would return +1.22; simple average would return +0.50; weighted gives +0.86.
    """
    with (
        patch("backend.routers.hedge.get_all_positions", new_callable=AsyncMock, return_value=[POS_A, POS_B]),
        patch("backend.routers.hedge.get_latest_futures", new_callable=AsyncMock, return_value=FAKE_LATEST),
    ):
        result = await get_net_prices()

    row = next(r for r in result if r["commodity"] == "ZS")
    pnl = row["options_pnl_per_bu"]

    assert abs(pnl - 0.858) < 0.05, (
        f"Weighted P&L should be ≈+$0.86/bu, got {pnl:.3f}. "
        "If this shows +$1.22 the aggregation is returning first-match only. "
        "If this shows +$0.50 the weights are equal instead of by raw_contracts."
    )

    # Guard: first-match would be POS_A's pnl (~+1.22), which is clearly wrong
    assert pnl < 1.0, (
        f"P&L of {pnl:.3f} is suspiciously close to POS_A alone (+$1.22/bu). "
        "Aggregation may be returning first match only."
    )


@pytest.mark.asyncio
async def test_raw_contracts_summed_not_averaged() -> None:
    """raw_contracts in the aggregate row must be the sum across positions."""
    with (
        patch("backend.routers.hedge.get_all_positions", new_callable=AsyncMock, return_value=[POS_A, POS_B]),
        patch("backend.routers.hedge.get_latest_futures", new_callable=AsyncMock, return_value=FAKE_LATEST),
    ):
        result = await get_net_prices()

    row = next(r for r in result if r["commodity"] == "ZS")
    # POS_A: 15000/5000 = 3.0 raw; POS_B: 5000/5000 = 1.0 raw; total = 4.0
    assert abs(row["raw_contracts"] - 4.0) < 0.01, (
        f"raw_contracts should be 4.0 (sum of 3.0 + 1.0), got {row['raw_contracts']}"
    )


@pytest.mark.asyncio
async def test_single_position_commodity_passes_through() -> None:
    """A commodity with only one active position must not be affected by aggregation."""
    with (
        patch("backend.routers.hedge.get_all_positions", new_callable=AsyncMock, return_value=[POS_A]),
        patch("backend.routers.hedge.get_latest_futures", new_callable=AsyncMock, return_value=FAKE_LATEST),
    ):
        result = await get_net_prices()

    assert len(result) == 1
    row = result[0]
    # POS_A: raw_contracts = 3.0, call_pnl ≈ +$1.22/bu
    assert abs(row["raw_contracts"] - 3.0) < 0.01
    assert row["options_pnl_per_bu"] > 1.0, "Single-position path must return POS_A's own pnl unchanged"


@pytest.mark.asyncio
async def test_puts_and_calls_never_blended_in_same_commodity() -> None:
    """Phase 1 puts and Phase 2 calls in the same commodity must produce separate rows.

    ZC has both a Phase 1 put (floor protection) and a Phase 2 call (upside
    participation). These use different P&L formulas and represent different
    strategies — blending them would produce a meaningless average.
    """
    def fake_latest(symbol: str):
        return ZC_FUTURES

    fake_futures = AsyncMock(side_effect=fake_latest)

    with (
        patch("backend.routers.hedge.get_all_positions", new_callable=AsyncMock, return_value=[ZC_PUT, ZC_CALL]),
        patch("backend.routers.hedge.get_latest_futures", fake_futures),
    ):
        result = await get_net_prices()

    zc_rows = [r for r in result if r["commodity"] == "ZC"]
    assert len(zc_rows) == 2, (
        f"Expected 2 ZC rows (one per phase), got {len(zc_rows)}. "
        "Puts (phase 1) and calls (phase 2) must not be aggregated together."
    )
    phases = {r["phase"] for r in zc_rows}
    assert phases == {1, 2}, f"Expected phases {{1, 2}}, got {phases}"

    put_row  = next(r for r in zc_rows if r["phase"] == 1)
    call_row = next(r for r in zc_rows if r["phase"] == 2)

    # Put P&L: max(4.50 - 4.72, 0) - 0.09 = -0.09 (OTM)
    assert put_row["options_pnl_per_bu"] < 0, "OTM put should have negative P&L"
    # Call P&L: max(4.72 - 4.50, 0) - 0.08 = 0.14 (ITM)
    assert call_row["options_pnl_per_bu"] > 0, "ITM call should have positive P&L"
