"""Tax router — cash sales CRUD, position audit log, tax summary export."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import HTTPException
from fastapi.routing import APIRouter

from backend.models.tax import (
    CashSaleCreate,
    CashSaleResponse,
    CashSaleUpdate,
    TaxPositionRow,
    TaxSummary,
)
from farm_platform.storage.mongo import (
    create_cash_sale,
    get_cash_sale,
    list_cash_sales,
    update_cash_sale,
)
from farm_platform.storage.timescale import insert_cash_sale_audit
from farm_platform.hedge.tracker import get_all_positions

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/tax", tags=["tax"])

TAX_YEAR = 2025


# ── Cash sales ────────────────────────────────────────────────────────────────

@router.get("/cash-sales", response_model=list[CashSaleResponse])
async def list_cash_sales_endpoint(
    commodity: str | None = None,
) -> list[dict[str, Any]]:
    docs = await list_cash_sales(commodity=commodity)
    return [_enrich_cash_sale(d) for d in docs]


@router.get("/cash-sales/{sale_id}", response_model=CashSaleResponse)
async def get_cash_sale_endpoint(sale_id: str) -> dict[str, Any]:
    doc = await get_cash_sale(sale_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Cash sale not found")
    return _enrich_cash_sale(doc)


@router.put("/cash-sales/{sale_id}", response_model=CashSaleResponse)
async def update_cash_sale_endpoint(
    sale_id: str, body: CashSaleUpdate
) -> dict[str, Any]:
    existing = await get_cash_sale(sale_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Cash sale not found")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")

    # Append audit entry for each changed field
    for field, new_val in updates.items():
        old_val = existing.get(field)
        if old_val != new_val:
            await insert_cash_sale_audit(
                cash_sale_id=sale_id,
                action="UPDATE",
                field_changed=field,
                before_value=_json(old_val),
                after_value=_json(new_val),
            )

    # Recompute derived fields if any inputs changed
    bushels = updates.get("bushels", existing.get("bushels", 0))
    price = updates.get("cash_price_per_bu", existing.get("cash_price_per_bu", 0.0))
    adjustments = updates.get("adjustments", existing.get("adjustments", 0.0))
    trucking_per_bu = updates.get("trucking_per_bu", existing.get("trucking_per_bu"))
    trucking_total = round(trucking_per_bu * bushels, 2) if trucking_per_bu is not None else existing.get("trucking_total") or 0.0
    gross = round(bushels * price, 2)
    net = round(gross - (adjustments or 0.0) - trucking_total, 2)
    updates["gross_amount"] = gross
    updates["net_amount"] = net
    if trucking_per_bu is not None:
        updates["trucking_total"] = trucking_total

    await update_cash_sale(sale_id, updates)
    updated = await get_cash_sale(sale_id)
    return _enrich_cash_sale(updated)  # type: ignore[arg-type]


@router.post("/cash-sales", response_model=CashSaleResponse, status_code=201)
async def create_cash_sale_endpoint(body: CashSaleCreate) -> dict[str, Any]:
    doc = body.model_dump()
    doc["gross_amount"] = body.gross_amount
    doc["net_amount"] = body.net_amount
    doc["migrated"] = False
    sale_id = await create_cash_sale(doc)
    await insert_cash_sale_audit(
        cash_sale_id=sale_id,
        action="CREATE",
    )
    created = await get_cash_sale(sale_id)
    return _enrich_cash_sale(created)  # type: ignore[arg-type]


# ── Tax summary ───────────────────────────────────────────────────────────────

@router.get("/summary", response_model=TaxSummary)
async def get_tax_summary(year: int = TAX_YEAR) -> dict[str, Any]:
    positions = await get_all_positions(status="all")
    rows: list[TaxPositionRow] = []

    hedge_realized = 0.0
    spec_realized = 0.0
    spec_mtm = 0.0

    for pos in positions:
        if pos.get("status") == "DELETED":
            continue
        tax = pos.get("tax_treatment", "SPECULATIVE")
        realized_pnl_total = None
        if pos.get("realized_pnl_per_bu") is not None and pos.get("expected_bushels"):
            realized_pnl_total = round(
                pos["realized_pnl_per_bu"] * pos["expected_bushels"], 2
            )

        opts_pnl_total = None
        opts_pnl_per_bu = pos.get("options_pnl_per_bu")
        if opts_pnl_per_bu is not None and pos.get("expected_bushels"):
            opts_pnl_total = round(opts_pnl_per_bu * pos["expected_bushels"], 2)

        row = TaxPositionRow(
            id=pos["id"],
            commodity=pos["commodity"],
            contract_month=pos.get("contract_month", ""),
            position_type=pos.get("position_type", ""),
            strike=pos.get("strike", 0.0),
            premium_paid_per_bu=pos.get("premium_paid_per_bu", 0.0),
            expected_bushels=pos.get("expected_bushels", 0),
            date_opened=pos.get("date_opened", ""),
            tax_treatment=tax,
            status=pos.get("status", "ACTIVE"),
            exit_date=pos.get("exit_date"),
            exit_price_per_bu=pos.get("exit_price_per_bu"),
            realized_pnl_per_bu=pos.get("realized_pnl_per_bu"),
            realized_pnl_total=realized_pnl_total,
            options_pnl_per_bu=opts_pnl_per_bu,
            options_pnl_total=opts_pnl_total,
            hedge_documentation=pos.get("hedge_documentation"),
            hedge_identification_date=pos.get("hedge_identification_date"),
            irc_1221_acknowledgment=pos.get("irc_1221_acknowledgment"),
        )
        rows.append(row)

        # Accumulate totals for closed positions
        if pos.get("status") in ("CLOSED", "EXPIRED") and realized_pnl_total is not None:
            if tax == "HEDGE":
                hedge_realized += realized_pnl_total
            else:
                spec_realized += realized_pnl_total

        # MTM for open SPECULATIVE
        if pos.get("status") == "ACTIVE" and tax == "SPECULATIVE" and opts_pnl_total is not None:
            spec_mtm += opts_pnl_total

    spec_1256 = round(spec_realized + spec_mtm, 2)
    return {
        "tax_year": year,
        "hedge_realized_total": round(hedge_realized, 2),
        "speculative_realized_total": round(spec_realized, 2),
        "speculative_mtm_total": round(spec_mtm, 2),
        "speculative_section_1256_total": spec_1256,
        "ltcg_60pct": round(spec_1256 * 0.60, 2),
        "stcg_40pct": round(spec_1256 * 0.40, 2),
        "positions": rows,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _json(val: Any) -> str:
    """json.dumps that handles datetime by converting to ISO string."""
    return json.dumps(val, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o))


def _enrich_cash_sale(doc: dict[str, Any]) -> dict[str, Any]:
    """Compute gross/net amounts from stored fields if not already present."""
    bushels = doc.get("bushels", 0)
    price = doc.get("cash_price_per_bu", 0.0)
    adjustments = doc.get("adjustments", 0.0)
    trucking = doc.get("trucking_total") or 0.0

    if "gross_amount" not in doc or doc["gross_amount"] is None:
        doc["gross_amount"] = round(bushels * price, 2)
    if "net_amount" not in doc or doc["net_amount"] is None:
        doc["net_amount"] = round(doc["gross_amount"] - adjustments - trucking, 2)

    doc.setdefault("migrated", False)
    doc.setdefault("notes", "")
    doc.setdefault("adjustments", 0.0)
    # Convert datetime fields to ISO strings for JSON serialization
    for field in ("created_at", "updated_at", "sale_date"):
        if field in doc and hasattr(doc[field], "isoformat"):
            doc[field] = doc[field].isoformat()
    if "created_at" not in doc or not isinstance(doc.get("created_at"), str):
        doc["created_at"] = datetime.now(tz=timezone.utc).isoformat()
    # sale_date: if datetime, take just the date portion
    if "sale_date" in doc and isinstance(doc["sale_date"], str) and "T" in doc["sale_date"]:
        doc["sale_date"] = doc["sale_date"][:10]
    return doc
