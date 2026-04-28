"""Unit tests for platform.hedge.calculator.

All calculations use known inputs so expected outputs can be verified by hand.
"""

import pytest

from farm_platform.hedge.calculator import (
    calc_phase1,
    calc_phase2,
    delta_adjusted_contracts,
)


class TestDeltaAdjustedContracts:
    def test_exact_division(self) -> None:
        raw, delta_adj = delta_adjusted_contracts(45_000, 0.40)
        assert raw == 9.0        # 45000 / 5000
        assert delta_adj == 22.5 # 9 / 0.40

    def test_small_farm(self) -> None:
        raw, delta_adj = delta_adjusted_contracts(10_000, 0.50)
        assert raw == 2.0
        assert delta_adj == 4.0

    def test_zero_delta_returns_zero(self) -> None:
        raw, delta_adj = delta_adjusted_contracts(45_000, 0.0)
        assert delta_adj == 0.0


class TestCalcPhase1:
    def test_puts_in_the_money(self) -> None:
        # Underlying has fallen below strike -- put has intrinsic value.
        # strike=4.20, underlying=4.00 → intrinsic=0.20
        # cash=3.95 (hypothetical), premium=0.14
        # net = 3.95 + 0.20 - 0.14 = 4.01
        result = calc_phase1(
            current_cash_price=3.95,
            underlying_price=4.00,
            strike=4.20,
            total_premiums_paid_per_bu=0.14,
            expected_bushels=45_000,
            delta_at_entry=0.40,
        )
        assert result.put_intrinsic_value == 0.20
        assert result.total_premiums_paid == 0.14
        assert result.net_effective_price == pytest.approx(4.01, abs=0.001)

    def test_puts_out_of_the_money(self) -> None:
        # Underlying above strike -- put intrinsic = 0.
        # net = cash - premium only
        result = calc_phase1(
            current_cash_price=4.50,
            underlying_price=4.60,
            strike=4.20,
            total_premiums_paid_per_bu=0.14,
            expected_bushels=45_000,
            delta_at_entry=0.40,
        )
        assert result.put_intrinsic_value == 0.0
        assert result.net_effective_price == pytest.approx(4.36, abs=0.001)

    def test_at_the_money(self) -> None:
        result = calc_phase1(
            current_cash_price=4.20,
            underlying_price=4.20,
            strike=4.20,
            total_premiums_paid_per_bu=0.10,
            expected_bushels=5_000,
            delta_at_entry=0.50,
        )
        assert result.put_intrinsic_value == 0.0
        assert result.net_effective_price == pytest.approx(4.10, abs=0.001)

    def test_premium_always_deducted(self) -> None:
        # Even when puts are worthless, premium is subtracted.
        result = calc_phase1(
            current_cash_price=5.00,
            underlying_price=5.00,
            strike=4.00,
            total_premiums_paid_per_bu=0.20,
            expected_bushels=5_000,
            delta_at_entry=0.50,
        )
        assert result.net_effective_price == pytest.approx(4.80, abs=0.001)

    def test_contract_counts(self) -> None:
        result = calc_phase1(
            current_cash_price=4.00,
            underlying_price=4.00,
            strike=4.20,
            total_premiums_paid_per_bu=0.14,
            expected_bushels=45_000,
            delta_at_entry=0.40,
        )
        assert result.raw_contracts == 9.0
        assert result.delta_adj_contracts == 22.5


class TestCalcPhase2:
    def test_calls_in_the_money(self) -> None:
        # Call strike 4.20, underlying 4.50 → call intrinsic = 0.30
        # cash locked = 4.00, total premiums = 0.24 (put+call), call premium = 0.10
        # net = 4.00 + 0.30 - 0.24 = 4.06
        result = calc_phase2(
            cash_sale_price=4.00,
            underlying_price=4.50,
            call_strike=4.20,
            call_premium_paid_per_bu=0.10,
            total_premiums_paid_per_bu=0.24,
            expected_bushels=45_000,
            delta_at_entry=0.40,
        )
        assert result.net_effective_price == pytest.approx(4.06, abs=0.001)

    def test_calls_out_of_the_money(self) -> None:
        # Market fell below call strike -- calls expire worthless.
        # net = cash_locked - total_premiums
        result = calc_phase2(
            cash_sale_price=4.00,
            underlying_price=3.80,
            call_strike=4.20,
            call_premium_paid_per_bu=0.10,
            total_premiums_paid_per_bu=0.24,
            expected_bushels=45_000,
            delta_at_entry=0.40,
        )
        assert result.net_effective_price == pytest.approx(3.76, abs=0.001)

    def test_premium_always_deducted(self) -> None:
        result = calc_phase2(
            cash_sale_price=11.50,
            underlying_price=11.00,
            call_strike=12.00,
            call_premium_paid_per_bu=0.20,
            total_premiums_paid_per_bu=0.40,
            expected_bushels=18_000,
            delta_at_entry=0.35,
        )
        # calls OTM → net = 11.50 - 0.40 = 11.10
        assert result.net_effective_price == pytest.approx(11.10, abs=0.001)

    def test_call_pnl_field(self) -> None:
        # call_pnl must equal call_intrinsic - call_premium (the actual options P&L)
        result = calc_phase2(
            cash_sale_price=4.00,
            underlying_price=4.50,
            call_strike=4.20,
            call_premium_paid_per_bu=0.10,
            total_premiums_paid_per_bu=0.24,
            expected_bushels=45_000,
            delta_at_entry=0.40,
        )
        # intrinsic = 4.50 - 4.20 = 0.30; pnl = 0.30 - 0.10 = 0.20
        assert result.call_pnl == pytest.approx(0.20, abs=0.001)


class TestLiveMockPositions:
    """Regression tests using the actual mock positions seeded on 2026-04-28.

    Futures reference prices: ZC=F ~$4.69, ZS=F ~$11.87.
    These tests caught a bug where the UI computed P&L as
    (net_effective_price - futures_price) instead of (intrinsic - premium).
    """

    def test_zcn26_c440_options_pnl_positive(self) -> None:
        # ZCN26 C $4.40 — 2 contracts, $0.21 premium, cash $4.34
        # At futures $4.69: intrinsic = $0.29, P&L = +$0.08/bu (minimum, ignoring time value)
        result = calc_phase2(
            cash_sale_price=4.34,
            underlying_price=4.69,
            call_strike=4.40,
            call_premium_paid_per_bu=0.21,
            total_premiums_paid_per_bu=0.21,
            expected_bushels=10_000,
            delta_at_entry=0.52,
        )
        assert result.call_pnl > 0, "ITM call must show positive options P&L"
        assert result.call_pnl == pytest.approx(0.08, abs=0.001)
        assert result.net_effective_price == pytest.approx(4.34 + 0.29 - 0.21, abs=0.001)

    def test_zcn26_c450_options_pnl_positive(self) -> None:
        # ZCN26 C $4.50 — 4 contracts, $0.17 premium, cash $4.44
        # At futures $4.69: intrinsic = $0.19, P&L = +$0.02/bu
        result = calc_phase2(
            cash_sale_price=4.44,
            underlying_price=4.69,
            call_strike=4.50,
            call_premium_paid_per_bu=0.17,
            total_premiums_paid_per_bu=0.17,
            expected_bushels=20_000,
            delta_at_entry=0.55,
        )
        assert result.call_pnl > 0
        assert result.call_pnl == pytest.approx(0.02, abs=0.001)

    def test_zsn26_c1025_options_pnl_strong_positive(self) -> None:
        # ZSN26 C $10.25 — 3 contracts, $0.40 premium, cash $10.34
        # At futures $11.87: intrinsic = $1.62, P&L = +$1.22/bu
        result = calc_phase2(
            cash_sale_price=10.34,
            underlying_price=11.87,
            call_strike=10.25,
            call_premium_paid_per_bu=0.40,
            total_premiums_paid_per_bu=0.40,
            expected_bushels=15_000,
            delta_at_entry=0.54,
        )
        assert result.call_pnl == pytest.approx(1.22, abs=0.001)
        assert result.net_effective_price == pytest.approx(10.34 + 1.62 - 0.40, abs=0.001)

    def test_zsn26_c1175_options_pnl_small_positive(self) -> None:
        # ZSN26 C $11.75 — 1 contract, $0.35 premium, cash $11.33
        # At futures $11.87: intrinsic = $0.12, P&L = -$0.23/bu (still below breakeven)
        result = calc_phase2(
            cash_sale_price=11.33,
            underlying_price=11.87,
            call_strike=11.75,
            call_premium_paid_per_bu=0.35,
            total_premiums_paid_per_bu=0.35,
            expected_bushels=4_078,
            delta_at_entry=0.51,
        )
        assert result.call_pnl == pytest.approx(0.12 - 0.35, abs=0.001)

    def test_zcn26_p450_put_pnl_negative_when_otm(self) -> None:
        # ZCN26 P $4.50 — Phase 1 put, $0.09 premium, 29,964 bu
        # At futures $4.69: put is OTM (intrinsic = 0), P&L = -$0.09/bu (cost of protection)
        result = calc_phase1(
            current_cash_price=4.69,
            underlying_price=4.69,
            strike=4.50,
            total_premiums_paid_per_bu=0.09,
            expected_bushels=29_964,
            delta_at_entry=0.22,
        )
        assert result.put_intrinsic_value == 0.0
        put_pnl = result.put_intrinsic_value - result.total_premiums_paid
        assert put_pnl == pytest.approx(-0.09, abs=0.001)

    def test_delta_adj_formula_for_put(self) -> None:
        # ZCN26 P $4.50, 29,964 bu, delta 0.22
        # raw = 5.9928 ≈ 6.0; delta_adj = 6.0 / 0.22 ≈ 27.24
        # delta_adj is the number of fully-correlated contracts needed for full coverage
        result = calc_phase1(
            current_cash_price=4.69,
            underlying_price=4.69,
            strike=4.50,
            total_premiums_paid_per_bu=0.09,
            expected_bushels=29_964,
            delta_at_entry=0.22,
        )
        assert result.raw_contracts == pytest.approx(5.99, abs=0.01)
        assert result.delta_adj_contracts == pytest.approx(27.24, abs=0.05)
