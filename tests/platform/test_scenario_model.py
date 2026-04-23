"""Unit tests for platform.hedge.scenario_model."""

import pytest

from farm_platform.hedge.scenario_model import run_phase1_scenarios, run_phase2_scenarios


class TestPhase1Scenarios:
    def test_five_prices(self) -> None:
        rows = run_phase1_scenarios(
            hypothetical_prices=[3.80, 4.00, 4.20, 4.40, 4.60],
            current_cash_offset=-0.30,   # basis: cash is 30 cents under futures
            strike=4.20,
            total_premiums_paid_per_bu=0.14,
            expected_bushels=45_000,
            delta_at_entry=0.40,
        )
        assert len(rows) == 5

        # At 3.80: put intrinsic = 4.20 - 3.80 = 0.40; cash = 3.80 - 0.30 = 3.50
        # net = 3.50 + 0.40 - 0.14 = 3.76
        r = rows[0]
        assert r.futures_price == 3.80
        assert r.put_intrinsic == pytest.approx(0.40, abs=0.001)
        assert r.net_effective_price == pytest.approx(3.76, abs=0.001)

        # At 4.60: put OTM; cash = 4.30; net = 4.30 - 0.14 = 4.16
        r = rows[4]
        assert r.futures_price == 4.60
        assert r.put_intrinsic == 0.0
        assert r.net_effective_price == pytest.approx(4.16, abs=0.001)

    def test_floor_never_lower_than_strike_minus_premium(self) -> None:
        # The put floor should be: strike - premium (in deeply ITM scenarios).
        rows = run_phase1_scenarios(
            hypothetical_prices=[2.00],
            current_cash_offset=0.0,
            strike=4.20,
            total_premiums_paid_per_bu=0.14,
            expected_bushels=5_000,
            delta_at_entry=0.50,
        )
        # put intrinsic = 4.20 - 2.00 = 2.20; net = 2.00 + 2.20 - 0.14 = 4.06
        assert rows[0].net_effective_price == pytest.approx(4.06, abs=0.001)

    def test_returns_list_of_scenario_rows(self) -> None:
        rows = run_phase1_scenarios(
            hypothetical_prices=[4.00],
            current_cash_offset=0.0,
            strike=4.20,
            total_premiums_paid_per_bu=0.10,
            expected_bushels=5_000,
            delta_at_entry=0.50,
        )
        row = rows[0]
        assert hasattr(row, "futures_price")
        assert hasattr(row, "net_effective_price")
        assert hasattr(row, "premiums_paid")


class TestPhase2Scenarios:
    def test_five_prices(self) -> None:
        rows = run_phase2_scenarios(
            hypothetical_prices=[4.00, 4.20, 4.40, 4.60, 4.80],
            cash_sale_price=4.10,
            call_strike=4.20,
            call_premium_paid_per_bu=0.10,
            total_premiums_paid_per_bu=0.24,
            expected_bushels=45_000,
            delta_at_entry=0.40,
        )
        assert len(rows) == 5

        # At 4.00: call OTM; net = 4.10 - 0.24 = 3.86
        assert rows[0].net_effective_price == pytest.approx(3.86, abs=0.001)

        # At 4.80: call intrinsic = 0.60; net = 4.10 + 0.60 - 0.24 = 4.46
        assert rows[4].net_effective_price == pytest.approx(4.46, abs=0.001)
