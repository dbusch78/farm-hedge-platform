"""MongoDB CRUD for options positions.

A position document looks like:
{
    "commodity":   "ZC" | "ZS",
    "contract_month": "ZCN26",
    "position_type": "put" | "call",
    "strike":       4.20,
    "premium_paid_per_bu": 0.14,
    "num_contracts": 9,
    "delta_at_entry": 0.40,
    "expected_bushels": 45000,
    "phase": 1 | 2,
    "date_opened":  "2025-04-01T00:00:00Z",
    "cash_sale_price": null,     # filled in at Phase 2 transition
    "status": "ACTIVE" | "CLOSED" | "EXPIRED" | "DELETED",
    "exit_price_per_bu": null,   # set at close / expire time
    "exit_date": null,
    "exit_reason": null,         # "sold" | "expired_worthless" | "expired_with_value" | "data_error"
    "realized_pnl_per_bu": null, # locked at close: exit_price - premium_paid
    "notes": "",
    "audit_log": [],
    "created_at": "...",
    "updated_at": "...",
}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from farm_platform.storage.mongo import (
    append_audit_entry,
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


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


async def add_position(doc: dict[str, Any]) -> str:
    """Validate and insert a new position. Returns the new position ID."""
    _validate(doc)
    doc.setdefault("status", "ACTIVE")
    doc.setdefault("closed", False)           # backward-compat field
    doc.setdefault("cash_sale_price", None)
    doc.setdefault("exit_price_per_bu", None)
    doc.setdefault("exit_date", None)
    doc.setdefault("exit_reason", None)
    doc.setdefault("close_reason", None)
    doc.setdefault("realized_pnl_per_bu", None)
    doc.setdefault("realized_pnl_total", None)
    doc.setdefault("parent_position_id", None)
    doc.setdefault("peak_pnl_per_bu", None)
    doc.setdefault("peak_pnl_date", None)
    doc.setdefault("notes", "")
    doc.setdefault("audit_log", [])
    # Tax classification defaults — auto-derive from phase if not supplied
    if doc.get("tax_treatment") is None:
        doc["tax_treatment"] = "HEDGE" if doc.get("phase") == 1 else "SPECULATIVE"
    if doc["tax_treatment"] == "HEDGE" and doc.get("hedge_identification_date") is None:
        # Identification date = entry date (date portion only)
        date_opened = doc.get("date_opened", "")
        doc["hedge_identification_date"] = date_opened[:10] if date_opened else None
    doc.setdefault("irc_1221_acknowledgment", False)
    doc.setdefault("linked_cash_sale_ids", [])
    position_id = await create_position(doc)
    await append_audit_entry(position_id, "created", {})
    log.info("position_created", id=position_id, commodity=doc["commodity"])
    return position_id


async def get_position_by_id(position_id: str) -> dict[str, Any] | None:
    return await get_position(position_id)


async def get_all_positions(
    active_only: bool = True,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Return positions filtered by status.

    ``active_only`` is the legacy parameter kept for callers that haven't
    been updated; ``status`` takes precedence when supplied.
    """
    resolved = status if status is not None else ("active" if active_only else "all")
    return await list_positions(resolved)


async def close_position_with_pnl(
    position_id: str,
    exit_price_per_bu: float,
    close_reason: str = "manual",
    exit_date: str | None = None,
    notes: str = "",
) -> None:
    """Mark a position CLOSED and lock in realized P&L."""
    pos = await get_position(position_id)
    if pos is None:
        raise ValueError(f"Position {position_id} not found")
    if pos.get("status", "ACTIVE") != "ACTIVE":
        raise ValueError(f"Position {position_id} is not ACTIVE (status={pos.get('status')})")

    realized_pnl_per_bu = round(exit_price_per_bu - pos["premium_paid_per_bu"], 4)
    realized_pnl_total = round(realized_pnl_per_bu * pos["expected_bushels"], 2)
    exit_dt = exit_date or _now_iso()

    updates: dict[str, Any] = {
        "status": "CLOSED",
        "closed": True,                      # backward-compat
        "exit_price_per_bu": exit_price_per_bu,
        "exit_date": exit_dt,
        "close_reason": close_reason,
        "realized_pnl_per_bu": realized_pnl_per_bu,
        "realized_pnl_total": realized_pnl_total,
    }
    if notes:
        existing = pos.get("notes", "")
        updates["notes"] = f"{existing}\n[Closed] {notes}".strip() if existing else f"[Closed] {notes}"

    await update_position(position_id, updates)
    await append_audit_entry(position_id, "closed", {
        "exit_price_per_bu": exit_price_per_bu,
        "close_reason": close_reason,
        "realized_pnl_per_bu": realized_pnl_per_bu,
        "realized_pnl_total": realized_pnl_total,
    })
    log.info("position_closed", id=position_id, realized_pnl_per_bu=realized_pnl_per_bu)


async def expire_position(
    position_id: str,
    exit_date: str | None = None,
) -> None:
    """Mark a position EXPIRED (held to expiration worthless).

    Realized P&L is always -(premium_paid) — expiry means the option was worthless.
    close_reason is always "expiry" so the field is never null on non-active positions.
    """
    pos = await get_position(position_id)
    if pos is None:
        raise ValueError(f"Position {position_id} not found")
    if pos.get("status", "ACTIVE") != "ACTIVE":
        raise ValueError(f"Position {position_id} is not ACTIVE (status={pos.get('status')})")

    realized_pnl_per_bu = round(0.0 - pos["premium_paid_per_bu"], 4)
    realized_pnl_total = round(realized_pnl_per_bu * pos["expected_bushels"], 2)
    exit_dt = exit_date or _now_iso()

    await update_position(position_id, {
        "status": "EXPIRED",
        "closed": True,                      # backward-compat
        "exit_price_per_bu": 0.0,
        "exit_date": exit_dt,
        "close_reason": "expiry",
        "realized_pnl_per_bu": realized_pnl_per_bu,
        "realized_pnl_total": realized_pnl_total,
    })
    await append_audit_entry(position_id, "expired", {
        "realized_pnl_per_bu": realized_pnl_per_bu,
        "realized_pnl_total": realized_pnl_total,
    })
    log.info("position_expired", id=position_id, realized_pnl_per_bu=realized_pnl_per_bu)


async def delete_position(position_id: str) -> None:
    """Hard-delete a position from MongoDB. Personal use only — cannot be undone."""
    from farm_platform.storage.mongo import delete_position_hard
    pos = await get_position(position_id)
    if pos is None:
        raise ValueError(f"Position {position_id} not found")

    await delete_position_hard(position_id)
    log.info("position_hard_deleted", id=position_id)


async def transition_to_phase2(position_id: str, cash_sale_price: float) -> None:
    """Mark position as Phase 2: record cash sale price, open calls."""
    await update_position(position_id, {"phase": 2, "cash_sale_price": cash_sale_price})
    await append_audit_entry(position_id, "updated", {
        "phase": {"from": 1, "to": 2},
        "cash_sale_price": {"from": None, "to": cash_sale_price},
    })
    log.info("position_phase2_transition", id=position_id, cash_sale_price=cash_sale_price)


async def patch_position(position_id: str, updates: dict[str, Any]) -> None:
    """Apply partial updates to a position. Edits are only allowed on ACTIVE positions."""
    for key in ("_id", "id", "created_at", "status", "exit_price_per_bu",
                "exit_date", "exit_reason", "close_reason", "realized_pnl_per_bu",
                "realized_pnl_total", "parent_position_id"):
        updates.pop(key, None)

    if not updates:
        return

    old = await get_position(position_id)
    if old is None:
        raise ValueError(f"Position {position_id} not found")
    if old.get("status", "ACTIVE") != "ACTIVE":
        raise ValueError(f"Position {position_id} cannot be edited (status={old.get('status')})")
    changes = {
        k: {"from": (old or {}).get(k), "to": v}
        for k, v in updates.items()
        if (old or {}).get(k) != v
    }
    await update_position(position_id, updates)
    if changes:
        await append_audit_entry(position_id, "updated", changes)


async def close_position(position_id: str, date_closed: str) -> None:
    """Legacy shim — prefer close_position_with_pnl."""
    await update_position(position_id, {"closed": True, "date_closed": date_closed})
    log.info("position_closed_legacy", id=position_id)
