"""Agents router — run history, manual trigger, annotation."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from farm_platform.storage.mongo import annotate_agent_run, get_agent_run, list_agent_runs

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])

# Registry: agent_name → run_once coroutine (populated at startup)
AGENT_REGISTRY: dict[str, Any] = {}


class AnnotateRequest(BaseModel):
    actual_outcome: str | None = None
    outcome_notes: str | None = None
    operator_rating: int | None = None   # 1-5


# ── Agent run history ─────────────────────────────────────────────────────────

@router.get("/runs")
async def list_runs(agent: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """List recent agent runs, newest first. Optionally filter by agent name."""
    return await list_agent_runs(agent=agent, limit=min(limit, 200))


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """Return full run detail including input snapshot, output, and token cost."""
    run = await get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/runs/{run_id}/annotate")
async def annotate_run(run_id: str, body: AnnotateRequest) -> dict[str, str]:
    """Record the actual market outcome and operator rating for retrospective tuning."""
    run = await get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await annotate_agent_run(
        run_id,
        actual_outcome=body.actual_outcome,
        outcome_notes=body.outcome_notes,
        operator_rating=body.operator_rating,
    )
    return {"id": run_id}


# ── Manual trigger ────────────────────────────────────────────────────────────

@router.post("/{agent_name}/run")
async def trigger_run(agent_name: str, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Trigger a manual agent run in the background. Returns immediately."""
    run_fn = AGENT_REGISTRY.get(agent_name)
    if run_fn is None:
        available = list(AGENT_REGISTRY.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown agent {agent_name!r}. Available: {available}",
        )
    background_tasks.add_task(_run_agent_task, agent_name, run_fn)
    return {"status": "queued", "agent": agent_name}


async def _run_agent_task(agent_name: str, run_fn: Any) -> None:
    try:
        await run_fn()
        log.info("manual_agent_run_complete", agent=agent_name)
    except Exception:
        log.exception("manual_agent_run_error", agent=agent_name)
