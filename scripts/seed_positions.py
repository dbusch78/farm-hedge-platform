"""Seed MongoDB with existing hedge positions.

Edit the POSITIONS list below to match your actual positions before running.

Usage:
    python -m scripts.seed_positions [--dry-run] [--clear]

Flags:
    --dry-run   Print what would be inserted without touching the database.
    --clear     Delete all existing positions before inserting. Use with care.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timezone

import structlog

# Configure minimal structlog for CLI output
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ]
)

log = structlog.get_logger()

# ── Edit these positions to match your actual hedge ──────────────────────────
#
# Field reference:
#   commodity          "ZC" (corn) | "ZS" (soybeans)
#   contract_month     CME symbol, e.g. "ZCN26" or "ZSN26"
#   position_type      "put" | "call"
#   strike             strike price (dollars/bushel)
#   premium_paid_per_bu  premium paid at entry (dollars/bushel)
#   num_contracts      number of contracts held (1 contract = 5,000 bu)
#   delta_at_entry     option delta at time of purchase (0 < delta <= 1)
#   expected_bushels   expected total production this crop year
#   phase              1 = pre-sale puts, 2 = post-sale calls
#   date_opened        ISO 8601 datetime string
#   cash_sale_price    (Phase 2 only) cash price received when grain was sold
#   notes              any context you want attached to this position
#
# Delta-adjusted contract count (shown in the UI) =
#   expected_bushels / 5000 / delta_at_entry
# -- the platform calculates this automatically; just record delta_at_entry.
#
POSITIONS: list[dict] = [
    # ── Example: Phase 1 corn put ────────────────────────────────────────────
    # Uncomment and edit to reflect your actual position.
    # {
    #     "commodity": "ZC",
    #     "contract_month": "ZCN26",
    #     "position_type": "put",
    #     "strike": 4.20,
    #     "premium_paid_per_bu": 0.14,
    #     "num_contracts": 9,
    #     "delta_at_entry": 0.40,
    #     "expected_bushels": 45000,
    #     "phase": 1,
    #     "date_opened": "2025-04-01T00:00:00Z",
    #     "notes": "Floor protection before planting.",
    # },
    # ── Example: Phase 2 soybean call ────────────────────────────────────────
    # {
    #     "commodity": "ZS",
    #     "contract_month": "ZCN26",
    #     "position_type": "call",
    #     "strike": 11.00,
    #     "premium_paid_per_bu": 0.22,
    #     "num_contracts": 4,
    #     "delta_at_entry": 0.38,
    #     "expected_bushels": 18000,
    #     "phase": 2,
    #     "date_opened": "2025-06-15T00:00:00Z",
    #     "cash_sale_price": 11.42,
    #     "notes": "Upside capture after elevator sale.",
    # },
]

# ─────────────────────────────────────────────────────────────────────────────


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


def _validate(doc: dict) -> None:
    missing = REQUIRED_FIELDS - doc.keys()
    if missing:
        raise ValueError(f"Position missing required fields: {missing}")
    if doc["commodity"] not in ("ZC", "ZS"):
        raise ValueError(f"commodity must be ZC or ZS, got {doc['commodity']!r}")
    if doc["position_type"] not in ("put", "call"):
        raise ValueError(f"position_type must be put or call, got {doc['position_type']!r}")
    if doc["phase"] not in (1, 2):
        raise ValueError(f"phase must be 1 or 2, got {doc['phase']!r}")
    if doc["phase"] == 2 and doc.get("cash_sale_price") is None:
        raise ValueError("Phase 2 position requires cash_sale_price")


def _delta_adj_count(expected_bushels: int, num_contracts: int, delta: float) -> float:
    raw = expected_bushels / 5000
    adj = raw / delta
    return round(adj, 2)


async def _run(dry_run: bool, clear: bool) -> None:
    from farm_platform.storage.mongo import close_client, create_position, get_db
    from datetime import datetime

    if not POSITIONS:
        log.warning("no_positions_defined", hint="Edit the POSITIONS list in this script.")
        return

    # Validate all positions before touching the DB
    for i, pos in enumerate(POSITIONS):
        try:
            _validate(pos)
        except ValueError as exc:
            log.error("validation_failed", position_index=i, error=str(exc))
            sys.exit(1)

    db = get_db()

    if clear and not dry_run:
        result = await db.positions.delete_many({})
        log.info("positions_cleared", deleted=result.deleted_count)

    inserted = 0
    for pos in POSITIONS:
        doc = dict(pos)
        doc.setdefault("closed", False)
        doc.setdefault("cash_sale_price", None)
        doc.setdefault("date_closed", None)
        doc.setdefault("notes", "")

        raw = doc["expected_bushels"] / 5000
        delta_adj = _delta_adj_count(
            doc["expected_bushels"], doc["num_contracts"], doc["delta_at_entry"]
        )

        log.info(
            "position",
            commodity=doc["commodity"],
            contract=doc["contract_month"],
            type=doc["position_type"],
            strike=doc["strike"],
            phase=doc["phase"],
            contracts=doc["num_contracts"],
            raw_contract_count=round(raw, 2),
            delta_adj_contracts=delta_adj,
            premium_per_bu=doc["premium_paid_per_bu"],
            dry_run=dry_run,
        )

        if not dry_run:
            pos_id = await create_position(doc)
            log.info("inserted", id=pos_id)
            inserted += 1

    if dry_run:
        log.info("dry_run_complete", positions_would_insert=len(POSITIONS))
    else:
        log.info("seed_complete", inserted=inserted)
        close_client()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print without writing to DB")
    parser.add_argument("--clear", action="store_true", help="Delete all existing positions first")
    args = parser.parse_args()

    asyncio.run(_run(dry_run=args.dry_run, clear=args.clear))


if __name__ == "__main__":
    main()
