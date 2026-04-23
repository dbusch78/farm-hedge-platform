"""Scenario modeler: given a list of hypothetical futures prices, return net
effective price per bushel for each scenario.

Returns a list of ScenarioRow objects suitable for JSON serialization and
chart rendering.
"""

from __future__ import annotations

from dataclasses import dataclass

from farm_platform.hedge.calculator import calc_phase1, calc_phase2


@dataclass
class ScenarioRow:
    futures_price: float
    put_intrinsic: float   # Phase 1 only; 0 in Phase 2
    call_intrinsic: float  # Phase 2 only; 0 in Phase 1
    premiums_paid: float
    net_effective_price: float


def run_phase1_scenarios(
    *,
    hypothetical_prices: list[float],
    current_cash_offset: float,          # cash basis (cash - futures); applied to each scenario
    strike: float,
    total_premiums_paid_per_bu: float,
    expected_bushels: int,
    delta_at_entry: float,
) -> list[ScenarioRow]:
    """Model Phase 1 net effective price across a range of futures prices.

    ``current_cash_offset`` is the basis (cash minus futures) used to derive
    a hypothetical cash price for each scenario price.
    """
    rows: list[ScenarioRow] = []
    for fp in hypothetical_prices:
        hypo_cash = fp + current_cash_offset
        result = calc_phase1(
            current_cash_price=hypo_cash,
            underlying_price=fp,
            strike=strike,
            total_premiums_paid_per_bu=total_premiums_paid_per_bu,
            expected_bushels=expected_bushels,
            delta_at_entry=delta_at_entry,
        )
        rows.append(ScenarioRow(
            futures_price=round(fp, 4),
            put_intrinsic=result.put_intrinsic_value,
            call_intrinsic=0.0,
            premiums_paid=result.total_premiums_paid,
            net_effective_price=result.net_effective_price,
        ))
    return rows


def run_phase2_scenarios(
    *,
    hypothetical_prices: list[float],
    cash_sale_price: float,
    call_strike: float,
    call_premium_paid_per_bu: float,
    total_premiums_paid_per_bu: float,
    expected_bushels: int,
    delta_at_entry: float,
) -> list[ScenarioRow]:
    rows: list[ScenarioRow] = []
    for fp in hypothetical_prices:
        result = calc_phase2(
            cash_sale_price=cash_sale_price,
            underlying_price=fp,
            call_strike=call_strike,
            call_premium_paid_per_bu=call_premium_paid_per_bu,
            total_premiums_paid_per_bu=total_premiums_paid_per_bu,
            expected_bushels=expected_bushels,
            delta_at_entry=delta_at_entry,
        )
        rows.append(ScenarioRow(
            futures_price=round(fp, 4),
            put_intrinsic=0.0,
            call_intrinsic=result.call_pnl + call_premium_paid_per_bu,
            premiums_paid=result.total_premiums_paid,
            net_effective_price=result.net_effective_price,
        ))
    return rows
