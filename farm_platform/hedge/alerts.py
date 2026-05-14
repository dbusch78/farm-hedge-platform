"""Phase transition alert evaluation — pure functions, no I/O.

Two families of alerts:
  Phase 1 (puts)  — roll-up when delta drifts / floor too far below market
                  — roll-down when deep ITM
  Phase 2 (calls) — yellow / red take-profit-and-pivot based on days-to-expiry
                    and peak P&L capture percentage
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

AlertLevel = Literal["yellow", "red"]

_MONTH_CODE = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}

_HARDCODED_IV = {"ZC": 0.22, "ZS": 0.18}


def cme_symbol_to_expiry(symbol: str) -> date | None:
    """Last Friday of the month before the delivery month (mirrors frontend cmeSymbolToExpiry)."""
    if len(symbol) < 4:
        return None
    month_code = symbol[-3]
    try:
        year = 2000 + int(symbol[-2:])
    except ValueError:
        return None
    contract_month = _MONTH_CODE.get(month_code)
    if contract_month is None:
        return None
    prev_month = 12 if contract_month == 1 else contract_month - 1
    prev_year = year - 1 if contract_month == 1 else year
    # last calendar day of prev_month
    if prev_month == 12:
        last_day = date(prev_year, 12, 31)
    else:
        last_day = date(prev_year, prev_month + 1, 1) - timedelta(days=1)
    # rewind to last Friday (weekday 4)
    days_back = (last_day.weekday() - 4) % 7
    return last_day - timedelta(days=days_back)


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _black76_delta(futures: float, strike: float, T: float, sigma: float, is_call: bool) -> float:
    """Black-76 absolute delta magnitude."""
    if T <= 0 or sigma <= 0 or futures <= 0 or strike <= 0:
        return float("nan")
    d1 = (math.log(futures / strike) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    nd1 = _normal_cdf(d1)
    return nd1 if is_call else 1.0 - nd1


@dataclass
class AlertResult:
    alert_type: str
    level: AlertLevel
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _live_delta(pos: dict[str, Any], underlying: float, today: date) -> float:
    """Compute Black-76 |delta|; falls back to delta_at_entry on expired or bad inputs."""
    expiry = cme_symbol_to_expiry(pos.get("contract_month", ""))
    delta_at_entry: float = pos.get("delta_at_entry", 0.40)
    if expiry is None or expiry <= today:
        return delta_at_entry
    T = (expiry - today).days / 365.25
    sigma = _HARDCODED_IV.get(pos.get("commodity", "ZC"), 0.22)
    delta = _black76_delta(underlying, pos.get("strike", 0.0), T, sigma,
                           pos.get("position_type") == "call")
    return delta if not math.isnan(delta) else delta_at_entry


def evaluate_alerts(
    pos: dict[str, Any],
    underlying_price: float,
    thresholds: Any,
) -> list[AlertResult]:
    """Evaluate all alert rules for a single ACTIVE position.

    thresholds is an AlertSettings instance (or any object with the same attrs).
    Returns a list of triggered AlertResults; may be empty.
    """
    results: list[AlertResult] = []
    phase: int = pos.get("phase", 1)
    position_type: str = pos.get("position_type", "put")
    strike: float = pos.get("strike", 0.0)
    premium: float = pos.get("premium_paid_per_bu", 0.0)
    commodity: str = pos.get("commodity", "ZC")
    delta_at_entry: float = pos.get("delta_at_entry", 0.40)

    expiry = cme_symbol_to_expiry(pos.get("contract_month", ""))
    today = date.today()
    days_to_expiry = (expiry - today).days if expiry else None

    current_delta = _live_delta(pos, underlying_price, today)

    # Current unrealized P&L per bushel
    if phase == 1:
        current_pnl = max(strike - underlying_price, 0.0) - premium
    else:
        current_pnl = max(underlying_price - strike, 0.0) - premium

    # ── Phase 1 alerts ─────────────────────────────────────────────────────────
    if phase == 1 and position_type == "put":
        roll_threshold = thresholds.zc_roll_threshold if commodity == "ZC" else thresholds.zs_roll_threshold

        # Roll-up: delta drifted AND floor materially below market AND time left
        if days_to_expiry is not None and days_to_expiry >= thresholds.roll_up_min_days:
            delta_drifted = (
                current_delta < delta_at_entry * thresholds.roll_up_delta_pct
                or current_delta < thresholds.roll_up_delta_abs
            )
            floor_below_market = (underlying_price - strike) >= roll_threshold
            if delta_drifted and floor_below_market:
                results.append(AlertResult(
                    alert_type="phase1_roll_up",
                    level="yellow",
                    reason=(
                        f"Put delta has drifted to {current_delta:.2f} (entry: {delta_at_entry:.2f}). "
                        f"Floor at ${strike:.2f} is ${underlying_price - strike:.2f}/bu below market. "
                        f"{days_to_expiry} days to expiry. Consider rolling up your strike."
                    ),
                    metadata={
                        "current_delta": round(current_delta, 3),
                        "delta_at_entry": delta_at_entry,
                        "strike": strike,
                        "underlying": underlying_price,
                        "days_to_expiry": days_to_expiry,
                    },
                ))

        # Roll-down: deep ITM
        roll_down_thresh = thresholds.roll_down_zc if commodity == "ZC" else thresholds.roll_down_zs
        if underlying_price < strike - roll_down_thresh and current_delta > thresholds.roll_down_delta:
            results.append(AlertResult(
                alert_type="phase1_roll_down",
                level="yellow",
                reason=(
                    f"Put is deep ITM: futures ${underlying_price:.2f}, strike ${strike:.2f} "
                    f"(${strike - underlying_price:.2f}/bu ITM). Δ={current_delta:.2f}. "
                    f"Consider closing to lock in gain or rolling down the strike."
                ),
                metadata={
                    "current_delta": round(current_delta, 3),
                    "strike": strike,
                    "underlying": underlying_price,
                    "days_to_expiry": days_to_expiry,
                },
            ))

    # ── Phase 2 alerts ─────────────────────────────────────────────────────────
    if phase == 2 and position_type == "call":
        peak_pnl: float | None = pos.get("peak_pnl_per_bu")
        if peak_pnl is not None and peak_pnl > 0 and current_pnl > 0:
            pct_of_peak = current_pnl / peak_pnl

            # Stage 2 — Red alert (check first; don't also fire yellow)
            red_reasons: list[str] = []
            if days_to_expiry is not None and days_to_expiry <= thresholds.tp_red_days:
                red_reasons.append(
                    f"Time decay is accelerating with {days_to_expiry} days to expiry."
                )
            if (peak_pnl - current_pnl) / peak_pnl > thresholds.tp_retracement:
                pct_retraced = round((1.0 - pct_of_peak) * 100)
                red_reasons.append(
                    f"Position has given back {pct_retraced}% from its peak P&L of ${peak_pnl:.2f}/bu."
                )
            if (days_to_expiry is not None and days_to_expiry <= 60
                    and pct_of_peak >= thresholds.tp_red_pct):
                red_reasons.append(
                    f"You've captured {round(pct_of_peak * 100)}% of peak; "
                    f"further upside likely outweighed by time decay risk."
                )

            if red_reasons:
                results.append(AlertResult(
                    alert_type="phase2_take_profit",
                    level="red",
                    reason=(
                        f"Recommend closing this position. "
                        f"Current realized-if-closed P&L: ${current_pnl:.2f}/bu. "
                        + " ".join(red_reasons)
                    ),
                    metadata={
                        "current_pnl_per_bu": round(current_pnl, 4),
                        "peak_pnl_per_bu": round(peak_pnl, 4),
                        "pct_of_peak": round(pct_of_peak, 3),
                        "days_to_expiry": days_to_expiry,
                    },
                ))
            else:
                # Stage 1 — Yellow alert
                yellow_reasons: list[str] = []
                if days_to_expiry is not None and days_to_expiry <= thresholds.tp_yellow_days:
                    yellow_reasons.append(f"{days_to_expiry} days to expiry.")
                if pct_of_peak >= thresholds.tp_yellow_pct:
                    yellow_reasons.append(
                        f"At ${current_pnl:.2f}/bu you've captured "
                        f"{round(pct_of_peak * 100)}% of this position's peak P&L."
                    )
                if yellow_reasons:
                    results.append(AlertResult(
                        alert_type="phase2_take_profit",
                        level="yellow",
                        reason=(
                            "This position is approaching take-profit territory. "
                            + " ".join(yellow_reasons)
                            + " Begin evaluating whether to close and pivot to new crop protection."
                        ),
                        metadata={
                            "current_pnl_per_bu": round(current_pnl, 4),
                            "peak_pnl_per_bu": round(peak_pnl, 4),
                            "pct_of_peak": round(pct_of_peak, 3),
                            "days_to_expiry": days_to_expiry,
                        },
                    ))

    return results
