#!/usr/bin/env bash
# Restore dev data from data/dumps/ into running containers.
# Run from the repo root: bash scripts/restore_dev_data.sh
# WARNING: drops and recreates all tables/collections — dev use only.
set -euo pipefail

DUMPS_DIR="$(dirname "$0")/../data/dumps"

if [ ! -d "$DUMPS_DIR" ] || [ -z "$(ls -A "$DUMPS_DIR" 2>/dev/null)" ]; then
  echo "No dumps found in data/dumps/ — run dump_dev_data.sh first."
  exit 1
fi

echo "==> Restoring TimescaleDB..."
if [ -f "$DUMPS_DIR/timescale.sql" ]; then
  # Terminate all connections then drop — WITH (FORCE) requires pg13+
  docker exec farm-platform-timescaledb-1 \
    psql -U farm -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='farm_platform' AND pid <> pg_backend_pid();" \
    2>/dev/null || true
  docker exec farm-platform-timescaledb-1 \
    psql -U farm -d postgres -c "DROP DATABASE IF EXISTS farm_platform WITH (FORCE);" 2>/dev/null || true
  docker exec farm-platform-timescaledb-1 \
    psql -U farm -d postgres -c "CREATE DATABASE farm_platform OWNER farm;"
  # Restore
  docker exec -i farm-platform-timescaledb-1 \
    psql -U farm -d farm_platform < "$DUMPS_DIR/timescale.sql"
  echo "    Restored: timescale.sql"
else
  echo "    Skipped: no timescale.sql found"
fi

echo "==> Restoring MongoDB collections..."
for collection in positions agent_runs alerts elevator_snapshots trading_mode_audit prompt_versions; do
  if [ -f "$DUMPS_DIR/${collection}.json" ]; then
    docker cp "$DUMPS_DIR/${collection}.json" "farm-platform-mongodb-1:/tmp/${collection}.json"
    docker exec farm-platform-mongodb-1 \
      mongoimport \
        --uri="mongodb://farm:${MONGO_PASSWORD:-changeme}@localhost:27017/farm_platform?authSource=admin" \
        --collection="$collection" \
        --drop \
        --file="/tmp/${collection}.json" 2>/dev/null
    echo "    Restored: ${collection}"
  else
    echo "    Skipped: ${collection} (no dump file)"
  fi
done

echo ""
echo "Done. Restart FastAPI to reconnect:"
echo "  docker restart farm-platform-fastapi-1"
