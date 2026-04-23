"""Motor (async MongoDB) client and collection helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from farm_platform.config import settings

log = structlog.get_logger(__name__)

_client: AsyncIOMotorClient | None = None  # type: ignore[type-arg]
_db: AsyncIOMotorDatabase | None = None  # type: ignore[type-arg]

# Collection names that must exist; created on init.
COLLECTIONS = [
    "positions",
    "usda_releases",
    "agent_runs",
    "news_articles",
    "conab_reports",
    "congressional_trades",
    "trade_journal",
    "elevator_snapshots",
    "prompt_versions",
    "trading_mode_audit",
]


def get_db() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(settings.mongo.uri)
        _db = _client.get_default_database()
        log.info("mongodb_client_created")
    return _db


async def ensure_collections() -> None:
    """Create collections and indexes if they don't already exist."""
    db = get_db()
    existing = await db.list_collection_names()
    for name in COLLECTIONS:
        if name not in existing:
            await db.create_collection(name)
            log.info("mongodb_collection_created", collection=name)

    # Indexes
    await db.positions.create_index([("commodity", 1), ("phase", 1)])
    await db.agent_runs.create_index([("agent", 1), ("run_timestamp", -1)])
    await db.trading_mode_audit.create_index([("timestamp", -1)])
    await db.news_articles.create_index([("published_at", -1)])
    await db.congressional_trades.create_index([("filed_at", -1)])
    log.info("mongodb_indexes_ensured")


def close_client() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
        log.info("mongodb_client_closed")


# ── positions ────────────────────────────────────────────────────────────────

async def create_position(doc: dict[str, Any]) -> str:
    db = get_db()
    doc.setdefault("created_at", _now())
    result = await db.positions.insert_one(doc)
    return str(result.inserted_id)


async def get_position(position_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await db.positions.find_one({"_id": ObjectId(position_id)})
    return _serialize(doc)


async def list_positions(active_only: bool = True) -> list[dict[str, Any]]:
    db = get_db()
    filt: dict[str, Any] = {}
    if active_only:
        filt["closed"] = {"$ne": True}
    cursor = db.positions.find(filt).sort("created_at", -1)
    return [_serialize(d) async for d in cursor]


async def update_position(position_id: str, updates: dict[str, Any]) -> None:
    db = get_db()
    updates["updated_at"] = _now()
    await db.positions.update_one(
        {"_id": ObjectId(position_id)},
        {"$set": updates},
    )


# ── agent_runs ───────────────────────────────────────────────────────────────

async def create_agent_run(doc: dict[str, Any]) -> str:
    db = get_db()
    doc.setdefault("run_timestamp", _now())
    result = await db.agent_runs.insert_one(doc)
    return str(result.inserted_id)


async def get_agent_run(run_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await db.agent_runs.find_one({"_id": ObjectId(run_id)})
    return _serialize(doc)


async def list_agent_runs(
    agent: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    db = get_db()
    filt: dict[str, Any] = {}
    if agent:
        filt["agent"] = agent
    cursor = db.agent_runs.find(filt).sort("run_timestamp", -1).limit(limit)
    return [_serialize(d) async for d in cursor]


async def annotate_agent_run(
    run_id: str,
    *,
    actual_outcome: str | None,
    outcome_notes: str | None,
    operator_rating: int | None,
) -> None:
    db = get_db()
    await db.agent_runs.update_one(
        {"_id": ObjectId(run_id)},
        {"$set": {
            "actual_outcome": actual_outcome,
            "outcome_notes": outcome_notes,
            "operator_rating": operator_rating,
        }},
    )


# ── trading_mode_audit ───────────────────────────────────────────────────────

async def get_current_trading_mode() -> str:
    """Return 'paper' or 'live'. Defaults to 'paper' if no audit log exists."""
    db = get_db()
    doc = await db.trading_mode_audit.find_one(sort=[("timestamp", -1)])
    if doc is None:
        return "paper"
    return str(doc["new_mode"])


async def log_mode_change(
    *,
    previous_mode: str,
    new_mode: str,
    confirmation_phrase: str,
    client_ip: str,
    user_agent: str,
) -> None:
    db = get_db()
    await db.trading_mode_audit.insert_one({
        "timestamp": _now(),
        "previous_mode": previous_mode,
        "new_mode": new_mode,
        "confirmed_by": "operator",
        "confirmation_phrase": confirmation_phrase,
        "client_ip": client_ip,
        "user_agent": user_agent,
    })


# ── elevator_snapshots ───────────────────────────────────────────────────────

async def save_elevator_snapshot(doc: dict[str, Any]) -> None:
    db = get_db()
    doc.setdefault("scraped_at", _now())
    await db.elevator_snapshots.insert_one(doc)


# ── helpers ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert ObjectId to str so documents can be JSON-serialized."""
    if doc is None:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc
