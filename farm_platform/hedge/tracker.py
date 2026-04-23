"""MongoDB CRUD for options positions.

A position document looks like:
{
    "commodity":   "ZC" | "ZS",
    "contract_month": "Jul25",
    "position_type": "put" | "call",
    "strike":       4.20,
    "premium_paid_per_bu": 0.14,
    "num_contracts": 9,
    "delta_at_entry": 0.40,
    "expected_bushels": 45000,
    "phase": 1 | 2,
    "date_opened":  "2025-04-01T00:00:00Z",
    "cash_sale_price": null,     # filled in at Phase 2 transition
    "closed": false,
    "date_closed": null,
    "notes": "",
    "created_at": "...",
    "updated_at": "...",
}
"""

from __future__ import annotations

from typing import Any

import structlog

from farm_platform.storage.mongo import (
    create_position,
    get_position,
    list_positions,
    update_position,
)

log = structlog.get_logger(__name__)

REQUIRED_FIELDS = {
    "commodity",
    "contract_month",
    "position_type",
    "strike",
    "premium_paid_per_bu",
    "num_contracts",
    "delta_at_entry",
    "expected_bushels",
    "phase",
    "date_opened",
}


def _validate(doc: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS - doc.keys()
    if missing:
        raise ValueError(f"Position missing required fields: {missing}")
    if doc["position_type"] not in ("put", "call"):
        raise ValueError("position_type must be 'put' or 'call'")
    if doc["phase"] not in (1, 2):
        raise ValueError("phase must be 1 or 2")


async def add_position(doc: dict[str, Any]) -> str:
    """Validate and insert a new position. Returns the new position ID."""
    _validate(doc)
    doc.setdefault("closed", False)
    doc.setdefault("cash_sale_price", None)
    doc.setdefault("date_closed", None)
    doc.setdefault("notes", "")
    position_id = await create_position(doc)
    log.info("position_created", id=position_id, commodity=doc["commodity"])
    return position_id


async def get_position_by_id(position_id: str) -> dict[str, Any] | None:
    return await get_position(position_id)


async def get_all_positions(active_only: bool = True) -> list[dict[str, Any]]:
    return await list_positions(active_only=active_only)


async def transition_to_phase2(position_id: str, cash_sale_price: float) -> None:
    """Mark position as Phase 2: record cash sale price, open calls."""
    await update_position(position_id, {"phase": 2, "cash_sale_price": cash_sale_price})
    log.info("position_phase2_transition", id=position_id, cash_sale_price=cash_sale_price)


async def close_position(position_id: str, date_closed: str) -> None:
    await update_position(position_id, {"closed": True, "date_closed": date_closed})
    log.info("position_closed", id=position_id)


async def patch_position(position_id: str, updates: dict[str, Any]) -> None:
    """Apply partial updates to a position (e.g. update delta, notes)."""
    # Strip protected fields
    for key in ("_id", "id", "created_at"):
        updates.pop(key, None)
    await update_position(position_id, updates)
