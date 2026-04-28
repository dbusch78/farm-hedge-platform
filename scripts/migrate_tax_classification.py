"""Migration: tax classification, cash_sales collection, append-only audit log.

What this script does
─────────────────────
1.  Creates the cash_sales MongoDB collection and its two PostgreSQL audit tables
    (position_audit_log, cash_sale_audit_log).

2.  For every Phase 2 position that has a cash_sale_price stored directly on it,
    creates one cash_sales record (migrated=True) and updates the position to hold
    a linked_cash_sale_id instead.  Fields that are unknown at migration time
    (delivery_location, selling_entity, contract_settlement_id, trucking) are set
    to None — fill them in via the UI after running.

3.  For every position (Phase 1 and 2), sets:
      tax_treatment          HEDGE  (Phase 1) | SPECULATIVE (Phase 2)
      irc_1221_acknowledgment  None  ← not back-filled; UI shows "legacy" badge
      speculative_acknowledgment  None  ← same
    and writes a CREATE entry to position_audit_log (migrated=True, timestamp=NOW).
    Audit timestamps are NEVER back-dated — they record when the migration ran,
    not when positions were opened.

4.  For Phase 1 positions, auto-generates a plausible hedge_documentation string
    from existing fields and flags it migrated=True with a note that retroactive
    identification does not qualify for actual hedge treatment under IRS rules.

Safety guarantees
─────────────────
- Default mode is DRY-RUN.  Pass --execute to write anything.
- Idempotent: positions that already have tax_treatment set are skipped.
- No existing position fields are deleted or overwritten (except that
  cash_sale_price is RETAINED on the position record alongside
  linked_cash_sale_id until you manually clear it after verifying the migration).

Usage
─────
    # See what would happen — safe to run any number of times:
    python -m scripts.migrate_tax_classification

    # Confirm output looks correct, then apply:
    python -m scripts.migrate_tax_classification --execute
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from typing import Any

import asyncpg
import structlog

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])
log = structlog.get_logger()


# ─────────────────────────────────────────────────────────────────────────────
# Schema DDL
# ─────────────────────────────────────────────────────────────────────────────

_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS position_audit_log (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    position_id     TEXT        NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action          TEXT        NOT NULL,
    field_changed   TEXT,
    before_value    JSONB,
    after_value     JSONB,
    reason          TEXT,
    user_id         TEXT        NOT NULL DEFAULT 'dennis',
    migrated        BOOLEAN     NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_pos_audit_position
    ON position_audit_log (position_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS cash_sale_audit_log (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    cash_sale_id    TEXT        NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action          TEXT        NOT NULL,
    field_changed   TEXT,
    before_value    JSONB,
    after_value     JSONB,
    reason          TEXT,
    user_id         TEXT        NOT NULL DEFAULT 'dennis',
    migrated        BOOLEAN     NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_cash_audit_sale
    ON cash_sale_audit_log (cash_sale_id, timestamp DESC);
"""

# Append-only enforcement — applied after table creation so it doesn't fail
# if the REVOKE was already applied in a previous run.
_APPEND_ONLY_DDL = """
DO $$
BEGIN
    REVOKE UPDATE, DELETE ON position_audit_log FROM farm;
EXCEPTION WHEN others THEN NULL; END $$;
DO $$
BEGIN
    REVOKE UPDATE, DELETE ON cash_sale_audit_log FROM farm;
EXCEPTION WHEN others THEN NULL; END $$;

CREATE OR REPLACE RULE no_update_pos_audit AS
    ON UPDATE TO position_audit_log DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_pos_audit AS
    ON DELETE TO position_audit_log DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_cash_audit AS
    ON UPDATE TO cash_sale_audit_log DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_cash_audit AS
    ON DELETE TO cash_sale_audit_log DO INSTEAD NOTHING;
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _hedge_doc_from_position(pos: dict[str, Any]) -> str:
    """Generate a plausible (but retroactive) hedge documentation string."""
    bu = pos.get("expected_bushels", 0)
    commodity = "corn" if pos.get("commodity") == "ZC" else "soybean"
    # Use date_opened as a proxy; the real documentation date is unknown.
    opened = pos.get("date_opened", "")
    date_str = opened[:10] if opened else "unknown date"
    year = pos.get("date_opened", "")[:4] or "unknown"
    return (
        f"{bu:,} bushels of {year} {commodity} crop, unpriced as of {date_str} "
        f"[AUTO-GENERATED — retroactive identification; see migrated flag]"
    )


def _safe_json(v: Any) -> str:
    return json.dumps(v, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# Core migration logic
# ─────────────────────────────────────────────────────────────────────────────

async def _run(execute: bool) -> None:
    from bson import ObjectId
    from farm_platform.config import settings
    from farm_platform.storage.mongo import get_db

    tag = "[DRY-RUN]" if not execute else "[EXECUTE]"
    log.info("migration_start", mode="execute" if execute else "dry_run")

    # ── Connect ──────────────────────────────────────────────────────────────
    db = get_db()
    pg = await asyncpg.connect(settings.db.dsn)

    try:
        # ── 1. Create PostgreSQL tables ──────────────────────────────────────
        print(f"\n{tag} Creating PostgreSQL audit tables…")
        if execute:
            await pg.execute(_AUDIT_DDL)
            await pg.execute(_APPEND_ONLY_DDL)
            print("       ✓ position_audit_log and cash_sale_audit_log created / verified")
        else:
            print("       Would run DDL for position_audit_log + cash_sale_audit_log")
            print("       Would apply REVOKE UPDATE/DELETE + no-op rules for append-only enforcement")

        # ── 2. Ensure cash_sales collection exists ───────────────────────────
        print(f"\n{tag} Ensuring MongoDB cash_sales collection…")
        if execute:
            existing = await db.list_collection_names()
            if "cash_sales" not in existing:
                await db.create_collection("cash_sales")
                await db.cash_sales.create_index([("commodity", 1), ("sale_date", -1)])
                print("       ✓ cash_sales collection + index created")
            else:
                print("       ✓ cash_sales collection already exists")

        # ── 3. Load all positions ────────────────────────────────────────────
        cursor = db.positions.find({"status": {"$ne": "DELETED"}})
        positions = [p async for p in cursor]
        print(f"\n{tag} Found {len(positions)} non-deleted positions")

        # Split already-migrated from pending
        pending = [p for p in positions if "tax_treatment" not in p]
        already_done = [p for p in positions if "tax_treatment" in p]
        if already_done:
            print(f"       Skipping {len(already_done)} positions already classified: "
                  f"{[str(p['_id']) for p in already_done]}")

        if not pending:
            print(f"\n{tag} Nothing to migrate — all positions already classified.")
            return

        # ── 4. Process Phase 2 positions: extract cash_sales ────────────────
        phase2 = [p for p in pending if p.get("phase") == 2 and p.get("cash_sale_price") is not None]
        phase1 = [p for p in pending if p.get("phase") == 1]
        phase2_no_cash = [p for p in pending if p.get("phase") == 2 and p.get("cash_sale_price") is None]

        print(f"\n{tag} Phase 2 positions with cash_sale_price → will create cash_sales records:")
        cash_sale_map: dict[str, str] = {}  # position_id → cash_sale_id

        for pos in phase2:
            pid = str(pos["_id"])
            commodity = pos["commodity"]
            bushels = pos.get("expected_bushels", 0)
            price = float(pos["cash_sale_price"])
            gross = round(bushels * price, 2)
            opened = pos.get("date_opened", "")
            sale_date_str = opened[:10] if opened else "unknown"

            print(f"\n       Position {pid}")
            print(f"         {commodity} {pos.get('contract_month')} "
                  f"{pos.get('position_type','').upper()} @${pos.get('strike')}")
            print(f"         → cash_sale to create:")
            print(f"             sale_date:         {sale_date_str}  "
                  f"(derived from date_opened — edit if actual sale date differs)")
            print(f"             commodity:         {commodity}")
            print(f"             bushels:           {bushels:,}")
            print(f"             cash_price_per_bu: ${price}")
            print(f"             gross_amount:      ${gross:,.2f}")
            print(f"             adjustments:       0.00  (unknown — fill in UI)")
            print(f"             net_amount:        ${gross:,.2f}  (= gross; no adjustments known)")
            print(f"             delivery_location: None  ← FILL IN")
            print(f"             selling_entity:    None  ← FILL IN")
            print(f"             contract_settlement_id: None  ← FILL IN")
            print(f"             trucking_per_bu:   None  ← FILL IN IF APPLICABLE")
            print(f"             migrated:          True")

            if execute:
                # Parse sale_date from date_opened; default to midnight UTC
                try:
                    sale_date = datetime.fromisoformat(opened.replace("Z", "+00:00")) if opened else _now_utc()
                    sale_date = sale_date.replace(hour=0, minute=0, second=0, microsecond=0)
                except ValueError:
                    sale_date = _now_utc()

                cash_sale_doc = {
                    "sale_date": sale_date,
                    "commodity": commodity,
                    "bushels": bushels,
                    "cash_price_per_bu": price,
                    "gross_amount": gross,
                    "adjustments": 0.0,
                    "net_amount": gross,
                    "delivery_location": None,
                    "selling_entity": None,
                    "trucking_per_bu": None,
                    "trucking_total": None,
                    "contract_settlement_id": None,
                    "notes": (
                        f"Auto-migrated from position {pid}. "
                        "Fill in: delivery_location, selling_entity, contract_settlement_id."
                    ),
                    "created_at": _now_utc(),
                    "migrated": True,
                    "migrated_from_position_id": pid,
                }
                result = await db.cash_sales.insert_one(cash_sale_doc)
                cs_id = str(result.inserted_id)
                cash_sale_map[pid] = cs_id

                # Write cash_sale CREATE to PostgreSQL audit log
                await pg.execute(
                    """INSERT INTO cash_sale_audit_log
                       (cash_sale_id, action, after_value, reason, migrated)
                       VALUES ($1, 'CREATE', $2::jsonb, $3, TRUE)""",
                    cs_id,
                    _safe_json({k: str(v) if not isinstance(v, (int, float, bool, str, type(None))) else v
                                for k, v in cash_sale_doc.items()}),
                    f"Auto-migrated from position {pid}",
                )
                print(f"         ✓ cash_sale {cs_id} created and audit logged")
            else:
                cash_sale_map[pid] = "<would-be-id>"

        if phase2_no_cash:
            print(f"\n{tag} Phase 2 positions WITHOUT cash_sale_price "
                  f"(will get tax_treatment=SPECULATIVE, linked_cash_sale_id=None):")
            for pos in phase2_no_cash:
                print(f"       {str(pos['_id'])} — {pos.get('contract_month')} "
                      f"{pos.get('position_type','').upper()} @${pos.get('strike')}")
            print("       These must be linked to a cash sale manually after migration.")

        # ── 5. Update all pending positions ──────────────────────────────────
        print(f"\n{tag} Updating {len(pending)} positions with tax_treatment + audit entries…")
        now = _now_utc()

        for pos in pending:
            pid = str(pos["_id"])
            phase = pos.get("phase", 1)
            tax_treatment = "HEDGE" if phase == 1 else "SPECULATIVE"

            updates: dict[str, Any] = {"tax_treatment": tax_treatment}
            audit_snapshot: dict[str, Any] = {
                "tax_treatment": tax_treatment,
                "phase": phase,
                "commodity": pos.get("commodity"),
                "contract_month": pos.get("contract_month"),
                "strike": pos.get("strike"),
                "premium_paid_per_bu": pos.get("premium_paid_per_bu"),
                "num_contracts": pos.get("num_contracts"),
                "expected_bushels": pos.get("expected_bushels"),
                "date_opened": pos.get("date_opened"),
                "irc_1221_acknowledgment": None,
                "speculative_acknowledgment": None,
                "migrated": True,
                "migration_note": (
                    "Retroactive identification — does not qualify for IRS hedge treatment. "
                    "New positions must follow the full entry workflow."
                    if phase == 1 else
                    "Retroactive speculative classification."
                ),
            }

            if phase == 1:
                hedge_doc = _hedge_doc_from_position(pos)
                updates.update({
                    "hedge_identification_date": pos.get("date_opened", "")[:10],
                    "hedge_documentation": hedge_doc,
                    "hedge_documentation_lock_date": now.isoformat(),
                    "physical_exposure_bushels": pos.get("expected_bushels"),
                    "physical_exposure_crop_year": int(pos.get("date_opened", "2026")[:4]),
                    "physical_exposure_description": hedge_doc,
                    "irc_1221_acknowledgment": None,  # not back-filled
                    "migrated": True,
                })
                audit_snapshot["hedge_documentation"] = hedge_doc
                audit_snapshot["hedge_identification_date"] = updates["hedge_identification_date"]
                audit_snapshot["physical_exposure_bushels"] = updates["physical_exposure_bushels"]

                print(f"       Phase 1 {pid}: HEDGE, doc=\"{hedge_doc[:60]}...\"")

            else:
                cs_id = cash_sale_map.get(pid)
                updates.update({
                    "speculative_acknowledgment": None,
                    "linked_cash_sale_id": cs_id,
                    # cash_sale_price RETAINED alongside linked_cash_sale_id
                    # (backward compat — remove manually after verifying)
                    "migrated": True,
                })
                audit_snapshot["linked_cash_sale_id"] = cs_id
                cs_str = cs_id or "none (no cash_sale_price on record)"
                print(f"       Phase 2 {pid}: SPECULATIVE, linked_cash_sale_id={cs_str}")

            if execute:
                await db.positions.update_one({"_id": pos["_id"]}, {"$set": updates})

                # Write position CREATE to PostgreSQL audit log
                # Timestamp = NOW (migration run time), never back-dated.
                await pg.execute(
                    """INSERT INTO position_audit_log
                       (position_id, action, after_value, reason, migrated)
                       VALUES ($1, 'CREATE', $2::jsonb, $3, TRUE)""",
                    pid,
                    _safe_json(audit_snapshot),
                    "Tax classification migration — initial audit log entry",
                )

                # Also append to MongoDB embedded audit_log for display cache
                entry = {
                    "timestamp": now.isoformat(),
                    "action": "CREATE",
                    "changes": audit_snapshot,
                    "migrated": True,
                }
                await db.positions.update_one(
                    {"_id": pos["_id"]},
                    {"$push": {"audit_log": entry}},
                )
                print(f"         ✓ position updated + audit logged (PG + MongoDB)")

        # ── 6. Summary ───────────────────────────────────────────────────────
        print(f"\n{'─'*60}")
        if execute:
            print(f"Migration complete.")
            print(f"  Phase 1 positions classified HEDGE:        {len(phase1)}")
            print(f"  Phase 2 positions classified SPECULATIVE:  {len(phase2) + len(phase2_no_cash)}")
            print(f"  cash_sales records created:                {len(cash_sale_map)}")
            print(f"\nNext steps:")
            print(f"  1. Open each cash_sale record in the UI and fill in:")
            print(f"       delivery_location, selling_entity, contract_settlement_id")
            print(f"       (optionally: trucking_per_bu, adjustments)")
            print(f"  2. Review Phase 1 hedge_documentation strings — edit within 24h if needed")
            print(f"  3. Once cash_sale records are complete, you can clear the")
            print(f"     legacy cash_sale_price field from Phase 2 positions")
        else:
            print(f"DRY-RUN complete — no data was written.")
            print(f"  Would classify {len(phase1)} Phase 1 positions as HEDGE")
            print(f"  Would classify {len(phase2) + len(phase2_no_cash)} Phase 2 positions as SPECULATIVE")
            print(f"  Would create {len(phase2)} cash_sales records from existing cash_sale_price values")
            print(f"  Would write {len(pending)} CREATE entries to position_audit_log (migrated=True)")
            print(f"\nIf output looks correct, run with --execute to apply.")

    finally:
        await pg.close()


# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually write to the database. Default is dry-run.",
    )
    args = parser.parse_args()

    if args.execute:
        confirm = input(
            "\nThis will modify existing position documents and create new records.\n"
            "Type 'yes' to proceed: "
        ).strip().lower()
        if confirm != "yes":
            print("Aborted.")
            sys.exit(0)

    asyncio.run(_run(execute=args.execute))


if __name__ == "__main__":
    main()
