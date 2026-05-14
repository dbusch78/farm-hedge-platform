"""Base agent infrastructure — shared by all five agents.

Every agent calls `run_agent()`, which:
  1. Loads the system prompt from MongoDB (falls back to the supplied default).
  2. Calls the Claude API.
  3. Parses the JSON output (strips markdown fences if present).
  4. Writes a full run document to MongoDB `agent_runs`.
  5. Returns the run document (with `id` set).

Prompt versioning: prompts live in the `prompt_versions` collection so they
can be edited without code deploys and replayed against historical inputs.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from anthropic import APIError, AsyncAnthropic, RateLimitError

from farm_platform.config import settings
from farm_platform.storage.mongo import create_agent_run, get_prompt

log = structlog.get_logger(__name__)

# Sonnet 4.6 pricing per 1M tokens (approximate at time of writing)
_INPUT_PRICE_PER_M = 3.00
_OUTPUT_PRICE_PER_M = 15.00

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic.api_key)
    return _client


def _parse_output(raw: str) -> dict[str, Any]:
    """Extract JSON from Claude's response, stripping markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            inner = parts[1]
            if inner.startswith("json\n"):
                inner = inner[5:]
            text = inner.strip()
    try:
        result = json.loads(text)
        if not isinstance(result, dict):
            return {"summary": raw, "parse_error": "not a JSON object"}
        return result
    except json.JSONDecodeError as e:
        return {"summary": raw, "parse_error": str(e)}


async def run_agent(
    agent_name: str,
    input_snapshot: dict[str, Any],
    default_prompt: str,
    prompt_version: str = "v1.0",
) -> dict[str, Any]:
    """Run an agent and persist the result to MongoDB.

    Loads the prompt from `prompt_versions` if one exists; otherwise uses
    `default_prompt`.  Returns the stored run document (with `id`).

    Raises on hard API errors (network, auth). Rate-limit errors are caught
    and stored as error runs so the scheduler doesn't crash.
    """
    # Prompt resolution: MongoDB first, then code default.
    stored = await get_prompt(agent_name, prompt_version)
    if stored and stored.get("system_prompt"):
        system_prompt = stored["system_prompt"]
    else:
        system_prompt = default_prompt

    model = settings.anthropic.model
    user_message = (
        "Current data snapshot:\n\n"
        + json.dumps(input_snapshot, indent=2, default=str)
        + "\n\nRespond with a JSON object matching the schema in your system prompt."
    )

    output: dict[str, Any]
    token_usage = {"input": 0, "output": 0}
    cost_usd = 0.0
    error: str | None = None

    try:
        client = _get_client()
        response = await client.messages.create(
            model=model,
            max_tokens=settings.anthropic.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text if response.content else ""
        output = _parse_output(raw)
        token_usage = {
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        }
        cost_usd = round(
            response.usage.input_tokens * _INPUT_PRICE_PER_M / 1_000_000
            + response.usage.output_tokens * _OUTPUT_PRICE_PER_M / 1_000_000,
            6,
        )
    except RateLimitError as e:
        log.warning("agent_rate_limited", agent=agent_name, error=str(e))
        output = {"summary": "Rate limited — will retry on next scheduled run.", "error": "rate_limited"}
        error = "rate_limited"
    except APIError as e:
        log.error("agent_api_error", agent=agent_name, error=str(e))
        output = {"summary": f"API error: {e}", "error": "api_error"}
        error = str(e)

    run_doc: dict[str, Any] = {
        "agent": agent_name,
        "prompt_version": prompt_version,
        "model": model,
        "input_snapshot": input_snapshot,
        "output": output,
        "token_usage": token_usage,
        "cost_usd": cost_usd,
        "actual_outcome": None,
        "outcome_notes": None,
        "operator_rating": None,
    }
    if error:
        run_doc["error"] = error

    run_id = await create_agent_run(run_doc)
    run_doc["id"] = run_id
    log.info(
        "agent_run_stored",
        agent=agent_name,
        run_id=run_id,
        cost_usd=cost_usd,
        input_tokens=token_usage["input"],
        output_tokens=token_usage["output"],
    )
    return run_doc
