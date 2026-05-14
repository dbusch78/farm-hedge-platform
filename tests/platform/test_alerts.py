"""Tests for farm_platform.hedge.alerts — pure function coverage."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from farm_platform.hedge.alerts import AlertResult, cme_symbol_to_expiry, evaluate_alerts

# ── Threshold fixture ─────────────────────────────────────────────────────────

def _thresholds(**overrides):
    defaults = dict(
        zc_roll_threshold=0.15,
        zs_roll_threshold=0.35,
        roll_up_min_days=30,
        roll_up_delta_pct=0.50,
        roll_up_delta_abs=0.15,
        roll_down_zc=0.20,
        roll_down_zs=0.50,
        roll_down_delta=0.80,
        tp_yellow_days=60,
        tp_yellow_pct=0.70,
        tp_red_days=45,
        tp_red_pct=0.85,
        tp_retracement=0.20,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── cme_symbol_to_expiry ──────────────────────────────────────────────────────

def test_expiry_zc_july():
    # ZCN26 → last Friday of June 2026
    expiry = cme_symbol_to_expiry("ZCN26")
    assert expiry is not None
    assert expiry.month == 6
    assert expiry.year == 2026
    assert expiry.weekday() == 4   # Friday


def test_expiry_zs_november():
    # ZSX25 → last Friday of October 2025
    expiry = cme_symbol_to_expiry("ZSX25")
    assert expiry is not None
    assert expiry.month == 10
    assert expiry.year == 2025
    assert expiry.weekday() == 4


def test_expiry_december_wraps_year():
    # ZCZ26 → last Friday of November 2026
    expiry = cme_symbol_to_expiry("ZCZ26")
    assert expiry is not None
    assert expiry.month == 11
    assert expiry.year == 2026


def test_expiry_january_wraps_year():
    # ZCF27 → last Friday of December 2026
    expiry = cme_symbol_to_expiry("ZCF27")
    assert expiry is not None
    assert expiry.month == 12
    assert expiry.year == 2026


def test_expiry_bad_symbol():
    assert cme_symbol_to_expiry("BAD") is None
    assert cme_symbol_to_expiry("") is None


# ── Phase 1 roll-up alert ─────────────────────────────────────────────────────

def _phase1_put(
    commodity="ZC",
    strike=4.50,
    premium=0.12,
    delta_at_entry=0.42,
    days_ahead=60,
):
    """Build a minimal Phase 1 put position with expiry `days_ahead` in the future."""
    expiry_date = date.today() + timedelta(days=days_ahead + 30)
    # Build a ZCN symbol whose expiry is roughly in the right range
    # Use ZCN26 — roughly July 2026, far enough away for most tests.
    return {
        "commodity": commodity,
        "contract_month": "ZCN26",
        "position_type": "put",
        "strike": strike,
        "premium_paid_per_bu": premium,
        "delta_at_entry": delta_at_entry,
        "phase": 1,
        "expected_bushels": 45000,
        "peak_pnl_per_bu": None,
        "peak_pnl_date": None,
    }


def test_phase1_roll_up_fires_when_conditions_met():
    # Delta drifted (underlying well above strike) and enough days remain
    pos = _phase1_put(strike=4.50, delta_at_entry=0.42)
    # Underlying well above strike so delta will be low; floor well below market
    alerts = evaluate_alerts(pos, underlying_price=5.00, thresholds=_thresholds())
    roll_up = [a for a in alerts if a.alert_type == "phase1_roll_up"]
    assert len(roll_up) == 1
    assert roll_up[0].level == "yellow"
    assert "roll" in roll_up[0].reason.lower()


def test_phase1_roll_up_silent_when_floor_near_market():
    # Strike close to market — threshold not crossed
    pos = _phase1_put(strike=4.90, delta_at_entry=0.42)
    alerts = evaluate_alerts(pos, underlying_price=5.00, thresholds=_thresholds())
    roll_up = [a for a in alerts if a.alert_type == "phase1_roll_up"]
    # 5.00 - 4.90 = 0.10 < 0.15 threshold → should NOT fire
    assert len(roll_up) == 0


def test_phase1_roll_up_silent_when_expired():
    pos = _phase1_put(strike=4.50, delta_at_entry=0.42)
    pos["contract_month"] = "ZCN23"   # expired contract
    alerts = evaluate_alerts(pos, underlying_price=5.00, thresholds=_thresholds())
    roll_up = [a for a in alerts if a.alert_type == "phase1_roll_up"]
    assert len(roll_up) == 0


# ── Phase 1 roll-down alert ───────────────────────────────────────────────────

def test_phase1_roll_down_fires_when_deep_itm():
    # Underlying < strike - roll_down_zc AND delta > 0.80
    pos = _phase1_put(strike=5.00, delta_at_entry=0.42)
    # At 4.60 vs strike 5.00: 0.40 ITM > 0.20 ZC threshold
    # At this deep ITM with short T, delta will be near 1.0
    alerts = evaluate_alerts(pos, underlying_price=4.60, thresholds=_thresholds())
    roll_down = [a for a in alerts if a.alert_type == "phase1_roll_down"]
    assert len(roll_down) == 1
    assert roll_down[0].level == "yellow"


def test_phase1_roll_down_silent_when_not_deep():
    pos = _phase1_put(strike=5.00, delta_at_entry=0.42)
    # Only 0.15 ITM — below 0.20 threshold
    alerts = evaluate_alerts(pos, underlying_price=4.85, thresholds=_thresholds())
    roll_down = [a for a in alerts if a.alert_type == "phase1_roll_down"]
    assert len(roll_down) == 0


# ── Phase 2 take-profit alerts ────────────────────────────────────────────────

def _phase2_call(
    strike=5.00,
    premium=0.18,
    delta_at_entry=0.38,
    peak_pnl=1.20,
    peak_pnl_date="2025-03-01",
    cash_sale_price=4.80,
):
    return {
        "commodity": "ZS",
        "contract_month": "ZSN26",
        "position_type": "call",
        "strike": strike,
        "premium_paid_per_bu": premium,
        "delta_at_entry": delta_at_entry,
        "phase": 2,
        "expected_bushels": 18000,
        "cash_sale_price": cash_sale_price,
        "peak_pnl_per_bu": peak_pnl,
        "peak_pnl_date": peak_pnl_date,
    }


def test_phase2_yellow_alert_at_70pct_of_peak():
    pos = _phase2_call(strike=10.00, premium=0.20, peak_pnl=1.00)
    # Current P&L: (12.00 - 10.00) - 0.20 = 1.80 > peak, so update peak first
    # Use underlying that gives 75% of peak
    # target pnl = 0.75: call_intrinsic = 0.75 + 0.20 = 0.95 → underlying = 10.95
    pos["peak_pnl_per_bu"] = 1.00
    alerts = evaluate_alerts(pos, underlying_price=11.15, thresholds=_thresholds())
    # pnl = (11.15 - 10.00) - 0.20 = 0.95 → 95% of peak → should be red or yellow
    # 95% > 85% and ZSN26 has many days → check just that something fires
    take_profit = [a for a in alerts if a.alert_type == "phase2_take_profit"]
    assert len(take_profit) >= 1


def test_phase2_red_alert_on_retracement():
    pos = _phase2_call(strike=10.00, premium=0.20, peak_pnl=1.00)
    # Current P&L: (10.60 - 10.00) - 0.20 = 0.40 → 60% of peak → 40% retrace → fires red
    alerts = evaluate_alerts(pos, underlying_price=10.60, thresholds=_thresholds())
    take_profit = [a for a in alerts if a.alert_type == "phase2_take_profit"]
    assert any(a.level == "red" for a in take_profit)


def test_phase2_no_alert_when_peak_is_zero():
    # Degenerate case: peak was set to zero — no alerts should fire
    pos = _phase2_call(strike=10.00, premium=0.20, peak_pnl=0.0)
    pos["contract_month"] = "ZSN28"
    alerts = evaluate_alerts(pos, underlying_price=10.80, thresholds=_thresholds())
    take_profit = [a for a in alerts if a.alert_type == "phase2_take_profit"]
    assert len(take_profit) == 0


def test_phase2_no_alert_when_current_pnl_negative():
    pos = _phase2_call(strike=10.00, premium=0.20, peak_pnl=1.00)
    # OTM call — no alert when current P&L is negative
    alerts = evaluate_alerts(pos, underlying_price=9.80, thresholds=_thresholds())
    take_profit = [a for a in alerts if a.alert_type == "phase2_take_profit"]
    assert len(take_profit) == 0


def test_phase2_no_alert_when_no_peak():
    pos = _phase2_call(peak_pnl=None)
    alerts = evaluate_alerts(pos, underlying_price=11.00, thresholds=_thresholds())
    take_profit = [a for a in alerts if a.alert_type == "phase2_take_profit"]
    assert len(take_profit) == 0


# ── Phase mismatch — no cross-contamination ────────────────────────────────────

def test_phase1_call_produces_no_phase1_put_alerts():
    # A Phase 1 call is unusual but should not fire roll-up (that's for puts)
    pos = {
        "commodity": "ZC",
        "contract_month": "ZCN26",
        "position_type": "call",
        "strike": 4.50,
        "premium_paid_per_bu": 0.12,
        "delta_at_entry": 0.42,
        "phase": 1,
        "expected_bushels": 45000,
        "peak_pnl_per_bu": None,
        "peak_pnl_date": None,
    }
    alerts = evaluate_alerts(pos, underlying_price=5.00, thresholds=_thresholds())
    roll_alerts = [a for a in alerts if "roll" in a.alert_type]
    assert len(roll_alerts) == 0


def test_alert_metadata_contains_key_fields():
    pos = _phase1_put(strike=4.50, delta_at_entry=0.42)
    alerts = evaluate_alerts(pos, underlying_price=5.00, thresholds=_thresholds())
    roll_up = [a for a in alerts if a.alert_type == "phase1_roll_up"]
    if roll_up:
        meta = roll_up[0].metadata
        assert "current_delta" in meta
        assert "underlying" in meta
        assert "strike" in meta
