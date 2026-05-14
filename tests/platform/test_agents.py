"""Tests for farm_platform.agents — base_agent and individual agents."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from farm_platform.agents.base_agent import _parse_output


# ── _parse_output ─────────────────────────────────────────────────────────────

def test_parse_output_clean_json():
    raw = '{"summary": "test", "confidence": 0.8}'
    result = _parse_output(raw)
    assert result["summary"] == "test"
    assert result["confidence"] == 0.8


def test_parse_output_strips_markdown_fence():
    raw = '```json\n{"summary": "fenced", "confidence": 0.7}\n```'
    result = _parse_output(raw)
    assert result["summary"] == "fenced"


def test_parse_output_strips_plain_fence():
    raw = '```\n{"summary": "plain", "confidence": 0.6}\n```'
    result = _parse_output(raw)
    assert result["summary"] == "plain"


def test_parse_output_invalid_json_returns_summary():
    raw = "This is not JSON at all."
    result = _parse_output(raw)
    assert "summary" in result
    assert "parse_error" in result
    assert result["summary"] == raw


def test_parse_output_non_dict_json_returns_summary():
    raw = "[1, 2, 3]"
    result = _parse_output(raw)
    assert "parse_error" in result


def test_parse_output_nested_json():
    raw = json.dumps({
        "summary": "complex",
        "market_bias": {"ZC": "bullish", "ZS": "neutral"},
        "confidence": 0.65,
    })
    result = _parse_output(raw)
    assert result["confidence"] == 0.65
    assert result["market_bias"]["ZC"] == "bullish"


# ── run_agent (mocked Claude) ─────────────────────────────────────────────────

@pytest.fixture
def mock_anthropic_response():
    """Minimal mock of an Anthropic messages.create response."""
    msg = MagicMock()
    msg.content = [MagicMock(text='{"summary": "mock output", "confidence": 0.75}')]
    msg.usage.input_tokens = 500
    msg.usage.output_tokens = 150
    return msg


@pytest.mark.asyncio
async def test_run_agent_stores_run_and_returns_id(mock_anthropic_response):
    with (
        patch("farm_platform.agents.base_agent._get_client") as mock_client_fn,
        patch("farm_platform.agents.base_agent.get_prompt", new=AsyncMock(return_value=None)),
        patch("farm_platform.agents.base_agent.create_agent_run", new=AsyncMock(return_value="abc123")),
    ):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
        mock_client_fn.return_value = mock_client

        from farm_platform.agents.base_agent import run_agent
        result = await run_agent(
            agent_name="test_agent",
            input_snapshot={"key": "value"},
            default_prompt="You are a test agent.",
        )

    assert result["id"] == "abc123"
    assert result["agent"] == "test_agent"
    assert result["output"]["confidence"] == 0.75
    assert result["token_usage"]["input"] == 500
    assert result["cost_usd"] > 0


@pytest.mark.asyncio
async def test_run_agent_uses_mongodb_prompt_when_available(mock_anthropic_response):
    stored_prompt = {"system_prompt": "Custom prompt from DB", "version": "v2.0"}
    with (
        patch("farm_platform.agents.base_agent._get_client") as mock_client_fn,
        patch("farm_platform.agents.base_agent.get_prompt", new=AsyncMock(return_value=stored_prompt)),
        patch("farm_platform.agents.base_agent.create_agent_run", new=AsyncMock(return_value="xyz")),
    ):
        captured_kwargs: dict = {}

        async def capture_create(**kwargs: object) -> object:
            captured_kwargs.update(kwargs)
            return mock_anthropic_response

        mock_client = MagicMock()
        mock_client.messages.create = capture_create
        mock_client_fn.return_value = mock_client

        from farm_platform.agents.base_agent import run_agent
        await run_agent("agent", {}, "Default prompt — should NOT be used")

    assert captured_kwargs.get("system") == "Custom prompt from DB"


@pytest.mark.asyncio
async def test_run_agent_handles_rate_limit_gracefully():
    from anthropic import RateLimitError

    with (
        patch("farm_platform.agents.base_agent._get_client") as mock_client_fn,
        patch("farm_platform.agents.base_agent.get_prompt", new=AsyncMock(return_value=None)),
        patch("farm_platform.agents.base_agent.create_agent_run", new=AsyncMock(return_value="err1")),
    ):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=RateLimitError(
                "rate limited",
                response=MagicMock(status_code=429, headers={}),
                body={"error": {"message": "rate limited"}},
            )
        )
        mock_client_fn.return_value = mock_client

        from farm_platform.agents.base_agent import run_agent
        result = await run_agent("agent", {}, "prompt")

    # Should not raise — error stored in run doc
    assert result["error"] == "rate_limited"
    assert "error" in result["output"]


# ── news_feed keyword filter ──────────────────────────────────────────────────

def test_news_feed_dedup_removes_duplicate_urls():
    from farm_platform.feeds.news_feed import _dedupe

    articles = [
        {"url": "http://a.com/1", "title": "Corn rally"},
        {"url": "http://a.com/1", "title": "Corn rally (duplicate)"},
        {"url": "http://a.com/2", "title": "Soybean"},
    ]
    result = _dedupe(articles)
    assert len(result) == 2
    assert result[0]["title"] == "Corn rally"


def test_news_feed_dedup_empty():
    from farm_platform.feeds.news_feed import _dedupe
    assert _dedupe([]) == []
