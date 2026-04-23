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
