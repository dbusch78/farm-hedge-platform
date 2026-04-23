"""First-run database initialiser.

Usage:
    python -m scripts.init_db

Creates TimescaleDB hypertables (from schemas.sql) and MongoDB collections.
Safe to re-run; all DDL statements use IF NOT EXISTS.
"""

import asyncio
import pathlib
import sys

import asyncpg
import structlog

# Allow running from repo root without installing the package.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from farm_platform.config import settings
from farm_platform.storage.mongo import ensure_collections

log = structlog.get_logger(__name__)
SQL_PATH = pathlib.Path(__file__).parent.parent / "farm_platform" / "storage" / "schemas.sql"


async def init_timescaledb() -> None:
    log.info("timescaledb_init_start", dsn=settings.db.dsn)
    conn = await asyncpg.connect(dsn=settings.db.dsn)
    try:
        sql = SQL_PATH.read_text()
        # Split on statement boundaries; asyncpg doesn't support multi-statement execute.
        for stmt in _split_statements(sql):
            if stmt.strip():
                try:
                    await conn.execute(stmt)
                except Exception as exc:
                    # Log and continue -- most failures are "already exists".
                    log.warning("ddl_statement_skipped", error=str(exc), stmt=stmt[:80])
        log.info("timescaledb_init_done")
    finally:
        await conn.close()


async def init_mongodb() -> None:
    log.info("mongodb_init_start")
    await ensure_collections()
    log.info("mongodb_init_done")


def _split_statements(sql: str) -> list[str]:
    """Split SQL on semicolons while ignoring those inside string literals."""
    stmts: list[str] = []
    current: list[str] = []
    in_single = False
    for char in sql:
        if char == "'" and not in_single:
            in_single = True
        elif char == "'" and in_single:
            in_single = False
        if char == ";" and not in_single:
            stmts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if "".join(current).strip():
        stmts.append("".join(current).strip())
    return stmts


async def main() -> None:
    await init_timescaledb()
    await init_mongodb()
    log.info("init_complete")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=settings.log_level)
    asyncio.run(main())
