"""Agent 1: USDA Skeptic

Principle: The price move lives in the gap between USDA and private trade
expectations — not in the USDA absolute number. Frame all output relative to
what the market was pricing in before the release.

Trigger: Monthly post-WASDE (roughly the 10th), or manual.
"""

from __future__ import annotations

from typing import Any

import structlog

from farm_platform.agents.base_agent import run_agent
from farm_platform.feeds.usda_feed import fetch_latest_wasde

log = structlog.get_logger(__name__)

AGENT_NAME = "usda_skeptic"
PROMPT_VERSION = "v1.0"

# Private trade estimate ranges (approximate — update from StoneX/Allendale)
_PRIVATE_ESTIMATES: dict[str, dict[str, Any]] = {
    "ZC": {
        "description": "Corn ending stocks (million bushels)",
        "private_mean_mbu": None,   # set from external source; None = unknown
        "private_range_low": None,
        "private_range_high": None,
    },
    "ZS": {
        "description": "Soybean ending stocks (million bushels)",
        "private_mean_mbu": None,
        "private_range_low": None,
        "private_range_high": None,
    },
}

_SYSTEM_PROMPT = """\
You are a commodity market analyst specializing in USDA WASDE report interpretation.
Your job is to assess whether the USDA numbers are a surprise relative to private trade expectations.

The price move after a WASDE release comes from the DIVERGENCE between USDA numbers and
pre-release private trade estimates — not from the absolute number itself.

Given supply/demand data, you must produce a JSON object with this exact structure:
{
  "summary": "<2-3 sentence plain English summary of the WASDE implications>",
  "divergence_flag": <true if USDA meaningfully diverged from private estimates, else false>,
  "divergence_magnitude": "<none|minor|moderate|significant>",
  "directional_bias": "<bullish|bearish|neutral> for corn and beans",
  "positioning_note": "<one sentence actionable positioning implication for a farmer holding puts/calls>",
  "corn_note": "<specific note on corn supply/demand>",
  "beans_note": "<specific note on soybean supply/demand>",
  "confidence": <0.0-1.0 confidence in the analysis>
}

If private trade estimates are not available (null), note this and rate confidence lower.
Output ONLY the JSON object. No markdown, no explanation text outside the JSON.
"""


async def run_once() -> dict[str, Any]:
    """Fetch USDA data and run the skeptic agent."""
    corn_data = await fetch_latest_wasde("ZC")
    beans_data = await fetch_latest_wasde("ZS")

    input_snapshot: dict[str, Any] = {
        "corn": {
            "market_year": corn_data.get("market_year"),
            "ending_stocks_mbu": corn_data.get("ending_stocks_mbu"),
            "production_mbu": corn_data.get("production_mbu"),
            "exports_mbu": corn_data.get("exports_mbu"),
            "total_use_mbu": corn_data.get("total_use_mbu"),
            "private_mean_mbu": _PRIVATE_ESTIMATES["ZC"]["private_mean_mbu"],
            "private_range_low": _PRIVATE_ESTIMATES["ZC"]["private_range_low"],
            "private_range_high": _PRIVATE_ESTIMATES["ZC"]["private_range_high"],
            "fetch_error": corn_data.get("fetch_error"),
        },
        "beans": {
            "market_year": beans_data.get("market_year"),
            "ending_stocks_mbu": beans_data.get("ending_stocks_mbu"),
            "production_mbu": beans_data.get("production_mbu"),
            "exports_mbu": beans_data.get("exports_mbu"),
            "total_use_mbu": beans_data.get("total_use_mbu"),
            "private_mean_mbu": _PRIVATE_ESTIMATES["ZS"]["private_mean_mbu"],
            "private_range_low": _PRIVATE_ESTIMATES["ZS"]["private_range_low"],
            "private_range_high": _PRIVATE_ESTIMATES["ZS"]["private_range_high"],
            "fetch_error": beans_data.get("fetch_error"),
        },
        "data_source": "USDA FAS PSD Online",
        "note": "Private trade estimates are not automatically fetched; set manually if available.",
    }

    return await run_agent(AGENT_NAME, input_snapshot, _SYSTEM_PROMPT, PROMPT_VERSION)
