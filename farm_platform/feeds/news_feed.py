"""News feed — NewsAPI + Finnhub with grain-focused keyword filtering.

NewsAPI (newsapi.org) requires NEWSAPI_KEY.
Finnhub (finnhub.io) requires FINNHUB_KEY.

Returns articles from the last 24 hours matching grain market keywords.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog

from farm_platform.config import settings

log = structlog.get_logger(__name__)

_GRAIN_KEYWORDS = [
    "corn", "soybeans", "soy", "USDA", "China trade", "ethanol",
    "Black Sea", "grain exports", "crop insurance", "La Nina", "El Nino",
    "Argentina drought", "Brazil harvest", "WASDE", "futures",
    "ZC", "ZS", "wheat",
]

_QUERY_STRING = " OR ".join(f'"{kw}"' for kw in [
    "corn", "soybeans", "USDA", "China trade", "ethanol",
    "Black Sea grain", "La Nina", "Argentina drought", "Brazil harvest", "WASDE",
])


async def fetch_news(hours: int = 24) -> list[dict[str, Any]]:
    """Fetch recent grain-relevant news. Returns a list of article dicts."""
    articles: list[dict[str, Any]] = []
    articles += await _fetch_newsapi(hours)
    articles += await _fetch_finnhub(hours)
    return _dedupe(articles)


async def _fetch_newsapi(hours: int) -> list[dict[str, Any]]:
    key = settings.news.newsapi_key
    if not key:
        return []
    from_dt = (datetime.now(tz=timezone.utc) - timedelta(hours=hours)).isoformat()
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "corn OR soybeans OR USDA OR WASDE OR \"grain exports\" OR \"La Nina\" OR \"Brazil harvest\"",
        "language": "en",
        "sortBy": "publishedAt",
        "from": from_dt,
        "pageSize": 20,
        "apiKey": key,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        return [
            {
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "url": a.get("url", ""),
                "published_at": a.get("publishedAt", ""),
                "source": a.get("source", {}).get("name", "NewsAPI"),
            }
            for a in data.get("articles", [])
        ]
    except Exception as e:
        log.warning("newsapi_fetch_error", error=str(e))
        return []


async def _fetch_finnhub(hours: int) -> list[dict[str, Any]]:
    key = settings.news.finnhub_key
    if not key:
        return []
    now = int(time.time())
    from_ts = now - hours * 3600
    url = "https://finnhub.io/api/v1/news"
    params = {"category": "general", "token": key, "minId": 0}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            items = resp.json()
        results = []
        grain_lower = {kw.lower() for kw in _GRAIN_KEYWORDS}
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("datetime", 0) < from_ts:
                continue
            headline = (item.get("headline") or "").lower()
            summary = (item.get("summary") or "").lower()
            combined = headline + " " + summary
            if any(kw in combined for kw in grain_lower):
                results.append({
                    "title": item.get("headline", ""),
                    "description": item.get("summary", ""),
                    "url": item.get("url", ""),
                    "published_at": datetime.fromtimestamp(
                        item.get("datetime", 0), tz=timezone.utc
                    ).isoformat(),
                    "source": item.get("source", "Finnhub"),
                })
        return results
    except Exception as e:
        log.warning("finnhub_fetch_error", error=str(e))
        return []


def _dedupe(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for a in articles:
        key = a.get("url") or a.get("title", "")
        if key and key not in seen:
            seen.add(key)
            out.append(a)
    return out
