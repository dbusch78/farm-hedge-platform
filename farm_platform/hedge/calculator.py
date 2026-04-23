"""Net effective price and delta-adjusted contract count calculators.

All calculations are pure functions with no I/O — easy to unit test.

Phase 1 formula:
    net = current_cash_price + put_intrinsic_value - total_premiums_paid

Phase 2 formula:
    net = cash_sale_price_locked + call_pnl - total_premiums_paid
          (total_premiums_paid includes both puts and calls paid so far)

Premium is always shown as a deduction — never hidden.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Phase1Result:
    put_intrinsic_value: float    # max(strike - underlying, 0) per bushel
    total_premiums_paid: float    # all premiums paid, per bushel
    net_effective_price: float    # cash + intrinsic - premiums
    raw_contracts: float          # expected_bushels / 5000
    delta_adj_contracts: float    # raw_contracts / delta_at_entry


@dataclass
class Phase2Result:
    call_pnl: float               # max(underlying - strike, 0) - call_premium, per bu
    total_premiums_paid: float    # puts + calls, per bushel
    net_effective_price: float    # cash_locked + call_pnl - premiums
    raw_contracts: float
    delta_adj_contracts: float


def calc_phase1(
    *,
    current_cash_price: float,
    underlying_price: float,
    strike: float,
    total_premiums_paid_per_bu: float,
    expected_bushels: int,
    delta_at_entry: float,
) -> Phase1Result:
    """Calculate Phase 1 (pre-sale floor) net effective price."""
    put_intrinsic = max(strike - underlying_price, 0.0)
    net = current_cash_price + put_intrinsic - total_premiums_paid_per_bu
    raw = expected_bushels / 5_000
    delta_adj = raw / delta_at_entry if delta_at_entry else 0.0
    return Phase1Result(
        put_intrinsic_value=round(put_intrinsic, 4),
        total_premiums_paid=round(total_premiums_paid_per_bu, 4),
        net_effective_price=round(net, 4),
        raw_contracts=round(raw, 2),
        delta_adj_contracts=round(delta_adj, 2),
    )


def calc_phase2(
    *,
    cash_sale_price: float,
    underlying_price: float,
    call_strike: float,
    call_premium_paid_per_bu: float,
    total_premiums_paid_per_bu: float,   # puts + calls combined
    expected_bushels: int,
    delta_at_entry: float,
) -> Phase2Result:
    """Calculate Phase 2 (post-sale upside capture) net effective price."""
    call_intrinsic = max(underlying_price - call_strike, 0.0)
    call_pnl = call_intrinsic - call_premium_paid_per_bu
    net = cash_sale_price + call_pnl - (total_premiums_paid_per_bu - call_premium_paid_per_bu)
    # Simplify: net = cash_sale_price + call_intrinsic - total_premiums_paid
    net = cash_sale_price + call_intrinsic - total_premiums_paid_per_bu
    raw = expected_bushels / 5_000
    delta_adj = raw / delta_at_entry if delta_at_entry else 0.0
    return Phase2Result(
        call_pnl=round(call_pnl, 4),
        total_premiums_paid=round(total_premiums_paid_per_bu, 4),
        net_effective_price=round(net, 4),
        raw_contracts=round(raw, 2),
        delta_adj_contracts=round(delta_adj, 2),
    )


def delta_adjusted_contracts(
    expected_bushels: int,
    delta_at_entry: float,
) -> tuple[float, float]:
    """Return (raw_contracts, delta_adjusted_contracts)."""
    raw = expected_bushels / 5_000
    delta_adj = raw / delta_at_entry if delta_at_entry else 0.0
    return round(raw, 2), round(delta_adj, 2)
