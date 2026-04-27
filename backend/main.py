"""FastAPI application entry point.

Registers all routers, starts the APScheduler for feeds, and exposes the
WebSocket price feed at /ws/prices.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import hedge as hedge_router
from backend.websocket import on_new_price
from backend.websocket import router as ws_router
from farm_platform.config import settings
from farm_platform.feeds.elevator_scraper import run_once as elevator_run_once
from farm_platform.feeds.futures_feed import register_price_callback, run_once
from farm_platform.storage.mongo import ensure_collections
from farm_platform.storage.timescale import close_pool, get_pool

log = structlog.get_logger(__name__)

app = FastAPI(
    title="Farm Platform API",
    description="Hedge tracker, day-trading sandbox, and portfolio tracker",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://farm.local", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(hedge_router.router)
app.include_router(ws_router)


# ── Scheduler ─────────────────────────────────────────────────────────────────
_scheduler = AsyncIOScheduler()


@app.on_event("startup")
async def startup() -> None:
    # Ensure DB connections are established.
    await get_pool()
    await ensure_collections()

    # Wire the WebSocket broadcaster into the feed.
    register_price_callback(on_new_price)

    # Schedule feeds. next_run_time=now fires the first tick immediately without
    # blocking startup -- a failure in the feed will not crash the API.
    interval = settings.schedule.futures_feed_interval_min
    _scheduler.add_job(
        run_once,
        "interval",
        minutes=interval,
        id="futures_feed",
        next_run_time=datetime.now(tz=timezone.utc),
    )

    elevator_interval = settings.elevator.scraper_interval_hrs
    _scheduler.add_job(
        elevator_run_once, "interval", hours=elevator_interval, id="elevator_scraper"
    )

    _scheduler.start()
    log.info(
        "scheduler_started",
        futures_interval_min=interval,
        elevator_interval_hrs=elevator_interval,
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    _scheduler.shutdown(wait=False)
    await close_pool()
    log.info("app_shutdown")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
