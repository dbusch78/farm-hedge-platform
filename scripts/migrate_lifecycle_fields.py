"""Migrate position documents to Task 4 lifecycle schema.

What this does:
  1. Active positions: set status = "ACTIVE" if missing; null new fields.
  2. Closed/expired positions: map old exit_reason → close_reason; add
     realized_pnl_total if missing; add parent_position_id = null.

Safe to re-run (idempotent — skips docs that already have the new fields).

Usage:
  python -m scripts.migrate_lifecycle_fields [--dry-run]
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

from farm_platform.config import settings

EXIT_REASON_MAP = {
    "sold":                "manual",
    "expired_worthless":   "expiry",
    "expired_with_value":  "expiry",
    "data_error":          "manual",
}


async def run(dry_run: bool) -> None:
    client: AsyncIOMotorClient = AsyncIOMotorClient(settings.mongo.uri)  # type: ignore[type-arg]
    db = client.get_default_database()
    col = db.positions

    active_updates = 0
    closed_updates = 0
    skipped = 0

    async for doc in col.find({"status": {"$ne": "DELETED"}}):
        oid = doc["_id"]
        status = doc.get("status")
        updates: dict[str, Any] = {}

        # ── Active positions ───────────────────────────────────────────────────
        if status in (None, "ACTIVE"):
            if not status:
                updates["status"] = "ACTIVE"
            for field in ("close_reason", "realized_pnl_total", "parent_position_id"):
                if field not in doc:
                    updates[field] = None

            if updates:
                active_updates += 1
                print(f"  ACTIVE  {oid}  → {list(updates.keys())}")
                if not dry_run:
                    await col.update_one({"_id": oid}, {"$set": updates})
            else:
                skipped += 1

        # ── Closed / expired positions ─────────────────────────────────────────
        elif status in ("CLOSED", "EXPIRED"):
            if "close_reason" not in doc or doc.get("close_reason") is None:
                old_reason = doc.get("exit_reason", "manual")
                updates["close_reason"] = EXIT_REASON_MAP.get(old_reason, "manual")

            if "realized_pnl_total" not in doc or doc.get("realized_pnl_total") is None:
                pnl_per_bu = doc.get("realized_pnl_per_bu")
                bushels = doc.get("expected_bushels")
                if pnl_per_bu is not None and bushels:
                    updates["realized_pnl_total"] = round(pnl_per_bu * bushels, 2)
                else:
                    updates["realized_pnl_total"] = None

            if "parent_position_id" not in doc:
                updates["parent_position_id"] = None

            if updates:
                closed_updates += 1
                print(f"  {status:7s} {oid}  → {list(updates.keys())}")
                if not dry_run:
                    await col.update_one({"_id": oid}, {"$set": updates})
            else:
                skipped += 1

    client.close()

    print()
    if dry_run:
        print("DRY RUN — no changes written.")
    print(f"Active updated:  {active_updates}")
    print(f"Closed/expired:  {closed_updates}")
    print(f"Already current: {skipped}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    asyncio.run(run(dry))
