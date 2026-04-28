"""Migrate position contract_month values to full CME symbol format.

Converts legacy free-text values (e.g. "Jul25", "Jul26") to the standardised
CME symbol format (e.g. "ZCN26", "ZSN26"). Each record is updated individually
so every change is logged before it is written.

Idempotent: records already in the correct format (matching ^Z[A-Z]{1,3}\d{2}$)
are skipped — safe to re-run multiple times.

Usage:
    docker compose exec fastapi python scripts/migrate_contract_month.py
    docker compose exec fastapi python scripts/migrate_contract_month.py --dry-run

Output:
    - Console summary
    - logs/migrate_contract_month_YYYYMMDD_HHMMSS.log (audit trail)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import pathlib
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from farm_platform.storage.mongo import get_db

# ── Month code lookup ─────────────────────────────────────────────────────────
# Maps human-readable month abbreviations to CME month codes
MONTH_TO_CODE = {
    "jan": "F", "feb": "G", "mar": "H", "apr": "J", "may": "K", "jun": "M",
    "jul": "N", "aug": "Q", "sep": "U", "oct": "V", "nov": "X", "dec": "Z",
}

# CME symbol regex — used to detect already-migrated records
CME_PATTERN = re.compile(r"^Z[A-Z]{1,3}[FGHJKMNQUVXZ]\d{2}$")

# Commodity to base symbol mapping
COMMODITY_BASE = {"ZC": "ZC", "ZS": "ZS", "ZW": "ZW"}


def _parse_legacy_to_cme(legacy: str, commodity: str) -> str | None:
    """Convert a legacy contract_month string to a CME symbol.

    Handles formats like:
        "Jul25" → base from commodity + "N" + "25" = e.g. "ZCN25"
        "Jul26" → "ZCN26"
        "July 2026" → "ZCN26"
    Returns None if the format is unrecognised.
    """
    s = legacy.strip().lower()

    # Try "MonYY" or "MonYYYY" format (Jul25, Jul2026, July 2026, etc.)
    match = re.match(r"([a-z]+)\s*(\d{2,4})", s)
    if match:
        month_str, year_str = match.group(1)[:3], match.group(2)
        month_code = MONTH_TO_CODE.get(month_str)
        if month_code is None:
            return None
        year_2d = year_str[-2:]  # Take last 2 digits
        base = COMMODITY_BASE.get(commodity, commodity)
        return f"{base}{month_code}{year_2d}"

    return None


async def migrate(dry_run: bool) -> None:
    log_dir = pathlib.Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"migrate_contract_month_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file),
        ],
    )
    log = logging.getLogger(__name__)

    db = get_db()
    coll = db["positions"]

    cursor = coll.find({})
    total = updated = skipped = errored = 0

    async for doc in cursor:
        total += 1
        doc_id = str(doc["_id"])
        current = doc.get("contract_month", "")
        commodity = doc.get("commodity", "")

        # Already in correct format — skip
        if CME_PATTERN.match(current):
            log.info("SKIP  id=%s  contract_month=%r  (already CME format)", doc_id, current)
            skipped += 1
            continue

        new_value = _parse_legacy_to_cme(current, commodity)
        if new_value is None:
            log.warning("ERROR id=%s  contract_month=%r  (unrecognised format — manual review needed)", doc_id, current)
            errored += 1
            continue

        log.info(
            "%s id=%s  commodity=%s  %r → %r",
            "DRY-RUN" if dry_run else "UPDATE",
            doc_id,
            commodity,
            current,
            new_value,
        )

        if not dry_run:
            await coll.update_one(
                {"_id": doc["_id"]},
                {"$set": {"contract_month": new_value, "updated_at": datetime.now(tz=timezone.utc)}},
            )
        updated += 1

    summary = (
        f"\n{'DRY RUN — ' if dry_run else ''}"
        f"Migration complete: {total} records scanned, "
        f"{updated} {'would be ' if dry_run else ''}updated, "
        f"{skipped} already correct, "
        f"{errored} errors (manual review needed)."
    )
    log.info(summary)
    print(f"\nAudit log written to: {log_file}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate contract_month to CME symbol format")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing to DB")
    args = parser.parse_args()
    await migrate(args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
