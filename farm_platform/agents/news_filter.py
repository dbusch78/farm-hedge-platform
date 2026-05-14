"""Agent 4: News Sentiment Filter

Principle: Aggressive filtering only. Operator wants only news that could
move July ZC, ZS, or ZW futures. General farm news is noise.

Trigger: Daily against last 24 hours of articles.
"""

from __future__ import annotations

from typing import Any

import structlog

from farm_platform.agents.base_agent import run_agent
from farm_platform.feeds.news_feed import fetch_news

log = structlog.get_logger(__name__)

AGENT_NAME = "news_filter"
PROMPT_VERSION = "v1.0"

_SYSTEM_PROMPT = """\
You are a commodity futures news analyst. Filter news headlines for an operator
who trades corn (ZC), soybeans (ZS), and wheat (ZW) options.

Your ONLY job is to identify news that could move ZC, ZS, or ZW futures
within the next 5 trading days. Aggressively filter out everything else.

Relevant signals:
- USDA reports (WASDE, crop progress, export sales)
- China trade/tariff actions affecting US grain exports
- South American weather (drought = bullish ZS)
- Black Sea/Russia/Ukraine export disruptions (bullish ZW, ZC)
- US weather extremes during growing season
- Ethanol policy changes (affects ZC demand)
- Biofuel mandates
- Major fund positioning reports (COT)

Produce this JSON:
{
  "summary": "<3-5 bullet points of the most relevant news, each starting with a dash>",
  "article_count_scanned": <total articles reviewed>,
  "relevant_count": <how many passed the filter>,
  "zc_sentiment": <-1.0 to 1.0, negative=bearish, positive=bullish>,
  "zs_sentiment": <-1.0 to 1.0>,
  "zw_sentiment": <-1.0 to 1.0>,
  "china_demand_flag": <true if any China-related demand news>,
  "geopolitical_flag": <true if Black Sea / export disruption news>,
  "escalation_items": ["<list of items needing operator attention, or empty list>"],
  "confidence": <0.0-1.0>
}
Output ONLY the JSON object. If no relevant news, set all sentiments to 0.0 and
summary to "- No market-moving grain news in the past 24 hours."
"""


async def run_once() -> dict[str, Any]:
    """Fetch news and run the filter agent."""
    articles = await fetch_news(hours=24)

    # Truncate article text to keep token count manageable
    truncated = [
        {
            "title": a["title"],
            "description": (a.get("description") or "")[:200],
            "published_at": a.get("published_at", ""),
            "source": a.get("source", ""),
        }
        for a in articles[:30]
    ]

    input_snapshot: dict[str, Any] = {
        "articles": truncated,
        "article_count": len(articles),
        "hours_window": 24,
        "note": (
            "Articles pre-filtered for grain keywords before being passed here. "
            "NewsAPI and/or Finnhub."
            if articles
            else "No news API keys configured — articles list is empty."
        ),
    }

    return await run_agent(AGENT_NAME, input_snapshot, _SYSTEM_PROMPT, PROMPT_VERSION)
