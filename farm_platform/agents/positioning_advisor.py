"""Agent 5: Positioning Advisor

Principle: Synthesizes agents 1-4 and speaks directly to the operator's
current positions. Output must be immediately actionable.

Trigger: On-demand, or automatically after agents 1-4 complete.
"""

from __future__ import annotations

from typing import Any

import structlog

from farm_platform.agents.base_agent import run_agent
from farm_platform.storage.mongo import get_db, list_agent_runs, list_positions
from farm_platform.storage.timescale import get_latest_futures

log = structlog.get_logger(__name__)

AGENT_NAME = "positioning_advisor"
PROMPT_VERSION = "v1.0"

_SYSTEM_PROMPT = """\
You are a commodity positioning advisor for a Midwest grain farmer who uses
options to hedge corn (ZC) and soybean (ZS) production.

The farmer uses a two-phase strategy:
- Phase 1: Buy put options to establish a price floor before sale.
- Phase 2: After physical grain sale, buy call options to capture upside.

Your job: review the farmer's current positions and the latest market intelligence,
then give one clear actionable recommendation per active position.

You must consider:
- Whether the put/call is still doing its job (delta, time to expiry)
- Phase transition alerts (roll-up, roll-down, take-profit signals)
- What the USDA skeptic, SA monitor, weather analyst, and news filter are saying

Produce this JSON:
{
  "summary": "<3-4 sentence overall market and positioning assessment>",
  "position_assessments": [
    {
      "position_id": "<id>",
      "commodity": "<ZC|ZS>",
      "phase": <1|2>,
      "contract_month": "<symbol>",
      "recommendation": "<hold|roll|close|adjust>",
      "reasoning": "<1-2 sentences>",
      "urgency": "<low|medium|high>"
    }
  ],
  "market_bias": {
    "ZC": "<bullish|bearish|neutral>",
    "ZS": "<bullish|bearish|neutral>"
  },
  "key_risk": "<the single most important risk the operator faces right now>",
  "positioning_note": "<one consolidated sentence for the dashboard card>",
  "confidence": <0.0-1.0>,
  "divergence_flag": <true if USDA/SA/weather signal a major positioning change>,
  "divergence_magnitude": "<none|minor|moderate|significant>"
}
Output ONLY the JSON object.
"""


async def _get_latest_agent_output(agent_name: str) -> dict[str, Any] | None:
    runs = await list_agent_runs(agent=agent_name, limit=1)
    if runs:
        return runs[0].get("output")
    return None


async def run_once() -> dict[str, Any]:
    """Gather all inputs and run the positioning advisor."""
    # Positions
    positions = await list_positions("active")
    position_summaries = [
        {
            "id": p.get("id"),
            "commodity": p.get("commodity"),
            "phase": p.get("phase"),
            "contract_month": p.get("contract_month"),
            "position_type": p.get("position_type"),
            "strike": p.get("strike"),
            "premium_paid_per_bu": p.get("premium_paid_per_bu"),
            "delta_at_entry": p.get("delta_at_entry"),
            "expected_bushels": p.get("expected_bushels"),
            "num_contracts": p.get("num_contracts"),
            "date_opened": p.get("date_opened"),
            "cash_sale_price": p.get("cash_sale_price"),
            "peak_pnl_per_bu": p.get("peak_pnl_per_bu"),
        }
        for p in positions
    ]

    # Current futures prices
    zc_price, zs_price = None, None
    try:
        row_zc = await get_latest_futures("ZC=F")
        row_zs = await get_latest_futures("ZS=F")
        if row_zc and row_zc.get("close"):
            zc_price = float(row_zc["close"])
        if row_zs and row_zs.get("close"):
            zs_price = float(row_zs["close"])
    except Exception as e:
        log.warning("pricing_fetch_error", error=str(e))

    # Latest outputs from agents 1-4
    usda = await _get_latest_agent_output("usda_skeptic")
    sa = await _get_latest_agent_output("sa_monitor")
    weather = await _get_latest_agent_output("weather_analyst")
    news = await _get_latest_agent_output("news_filter")

    input_snapshot: dict[str, Any] = {
        "positions": position_summaries,
        "futures_prices": {"ZC": zc_price, "ZS": zs_price},
        "agent_inputs": {
            "usda_skeptic": usda,
            "sa_monitor": sa,
            "weather_analyst": weather,
            "news_filter": news,
        },
        "data_note": "Agent inputs are the most recent stored run outputs, not live.",
    }

    return await run_agent(AGENT_NAME, input_snapshot, _SYSTEM_PROMPT, PROMPT_VERSION)
