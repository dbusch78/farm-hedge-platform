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

from backend.routers import agents as agents_router
from backend.routers import analytics as analytics_router
from backend.routers import hedge as hedge_router
from backend.routers import tax as tax_router
from backend.routers import weather as weather_router
from backend.websocket import on_new_price
from backend.websocket import router as ws_router
from farm_platform.config import settings
from farm_platform.agents import (
    news_filter,
    positioning_advisor,
    sa_monitor,
    usda_skeptic,
    weather_analyst,
)
from farm_platform.feeds.ambient_feed import run_once as ambient_run_once
from farm_platform.feeds.elevator_scraper import run_once as elevator_run_once
from farm_platform.feeds.futures_feed import register_price_callback, run_once
from farm_platform.feeds.openmeteo_feed import run_once as openmeteo_run_once
from farm_platform.hedge.alerts import evaluate_alerts
from farm_platform.storage.mongo import (
    create_alert,
    ensure_collections,
    get_active_alert,
    list_positions as _list_positions_raw,
    update_position as _update_position_raw,
)
from farm_platform.storage.timescale import (
    close_pool,
    get_latest_futures,
    get_pool,
    insert_options_snapshot,
)

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
app.include_router(agents_router.router)
app.include_router(analytics_router.router)
app.include_router(weather_router.router)
app.include_router(tax_router.router)
app.include_router(ws_router)


# ── Scheduler ─────────────────────────────────────────────────────────────────
_scheduler = AsyncIOScheduler()


async def _update_peaks_and_alerts() -> None:
    """Daily job: update peak P&L high-water marks and fire phase transition alerts."""
    from datetime import date
    try:
        positions = await _list_positions_raw("active")
        if not positions:
            return

        # Batch futures price lookups
        underlying: dict[str, float] = {}
        for sym, commodity in [("ZC=F", "ZC"), ("ZS=F", "ZS")]:
            row = await get_latest_futures(sym)
            if row and row.get("close"):
                underlying[commodity] = float(row["close"])

        updated_peaks = 0
        fired_alerts = 0

        for pos in positions:
            commodity = pos.get("commodity")
            price = underlying.get(commodity)
            if price is None:
                continue

            # Compute current unrealized P&L
            phase = pos.get("phase", 1)
            strike = pos.get("strike", 0.0)
            premium = pos.get("premium_paid_per_bu", 0.0)
            if phase == 1:
                current_pnl = max(strike - price, 0.0) - premium
            else:
                current_pnl = max(price - strike, 0.0) - premium

            # Update high-water mark
            stored_peak = pos.get("peak_pnl_per_bu")
            if stored_peak is None or current_pnl > stored_peak:
                await _update_position_raw(pos["id"], {
                    "peak_pnl_per_bu": round(current_pnl, 4),
                    "peak_pnl_date": date.today().isoformat(),
                })
                pos["peak_pnl_per_bu"] = current_pnl
                updated_peaks += 1

            # Record daily snapshot for NEP history chart
            cash_ref = pos.get("cash_sale_price") or price  # Phase 2 uses locked price
            net_eff = round(cash_ref + current_pnl, 4)
            await insert_options_snapshot(
                time=datetime.now(tz=timezone.utc),
                position_id=pos["id"],
                underlying_px=price,
                option_px=None,
                delta=None,
                premium_paid=pos.get("premium_paid_per_bu"),
                pnl_per_bushel=round(current_pnl, 4),
                net_eff_price=net_eff,
            )

            # Evaluate alert rules
            triggered = evaluate_alerts(pos, price, settings.alerts)
            for alert in triggered:
                existing = await get_active_alert(pos["id"], alert.alert_type)
                if existing is None:
                    await create_alert({
                        "position_id": pos["id"],
                        "commodity": commodity,
                        "contract_month": pos.get("contract_month"),
                        "alert_type": alert.alert_type,
                        "level": alert.level,
                        "reason": alert.reason,
                        "metadata": alert.metadata,
                    })
                    fired_alerts += 1

        log.info(
            "alert_job_complete",
            positions_checked=len(positions),
            peaks_updated=updated_peaks,
            alerts_fired=fired_alerts,
        )
    except Exception:
        log.exception("alert_job_error")


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

    ambient_interval = settings.ambient.poll_interval_min
    _scheduler.add_job(
        ambient_run_once,
        "interval",
        minutes=ambient_interval,
        id="ambient_feed",
        next_run_time=datetime.now(tz=timezone.utc),
    )

    openmeteo_interval = settings.schedule.weather_feed_interval_hrs
    _scheduler.add_job(
        openmeteo_run_once,
        "interval",
        hours=openmeteo_interval,
        id="openmeteo_feed",
        next_run_time=datetime.now(tz=timezone.utc),
    )

    alert_interval = settings.schedule.alert_job_interval_hrs
    _scheduler.add_job(
        _update_peaks_and_alerts,
        "interval",
        hours=alert_interval,
        id="alert_job",
        next_run_time=datetime.now(tz=timezone.utc),
    )

    # ── AI agent jobs ──────────────────────────────────────────────────────────
    # Populate the manual-trigger registry
    agents_router.AGENT_REGISTRY.update({
        "usda_skeptic":       usda_skeptic.run_once,
        "sa_monitor":         sa_monitor.run_once,
        "weather_analyst":    weather_analyst.run_once,
        "news_filter":        news_filter.run_once,
        "positioning_advisor": positioning_advisor.run_once,
    })

    # Scheduled: news filter daily, weather analyst daily in-season,
    # SA monitor weekly, USDA skeptic monthly, positioning advisor daily
    _scheduler.add_job(news_filter.run_once, "interval", hours=24, id="news_filter")
    _scheduler.add_job(weather_analyst.run_once, "interval", hours=24, id="weather_analyst")
    _scheduler.add_job(sa_monitor.run_once, "interval", hours=168, id="sa_monitor")  # weekly
    _scheduler.add_job(usda_skeptic.run_once, "interval", hours=720, id="usda_skeptic")  # ~monthly
    _scheduler.add_job(positioning_advisor.run_once, "interval", hours=24, id="positioning_advisor")

    _scheduler.start()
    log.info(
        "scheduler_started",
        futures_interval_min=interval,
        elevator_interval_hrs=elevator_interval,
        ambient_interval_min=ambient_interval,
        openmeteo_interval_hrs=openmeteo_interval,
        alert_interval_hrs=alert_interval,
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    _scheduler.shutdown(wait=False)
    await close_pool()
    log.info("app_shutdown")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
