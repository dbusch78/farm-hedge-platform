#!/usr/bin/env bash
# Dump dev data to data/dumps/ so it can be committed and shared between machines.
# Run from the repo root: bash scripts/dump_dev_data.sh
set -euo pipefail

DUMPS_DIR="$(dirname "$0")/../data/dumps"
mkdir -p "$DUMPS_DIR"

echo "==> Dumping TimescaleDB..."
docker exec farm-platform-timescaledb-1 \
  pg_dump -U farm -d farm_platform --no-owner --no-acl \
  > "$DUMPS_DIR/timescale.sql"
echo "    Written: data/dumps/timescale.sql ($(wc -l < "$DUMPS_DIR/timescale.sql") lines)"

echo "==> Dumping MongoDB collections..."
for collection in positions agent_runs alerts elevator_snapshots trading_mode_audit prompt_versions; do
  docker exec farm-platform-mongodb-1 \
    mongoexport \
      --uri="mongodb://farm:${MONGO_PASSWORD:-changeme}@localhost:27017/farm_platform?authSource=admin" \
      --collection="$collection" \
      --out="/tmp/${collection}.json" 2>/dev/null || true
  docker cp "farm-platform-mongodb-1:/tmp/${collection}.json" "$DUMPS_DIR/${collection}.json" 2>/dev/null \
    && echo "    Written: data/dumps/${collection}.json" \
    || echo "    Skipped: ${collection} (empty or not found)"
done

echo ""
echo "Done. Commit data/dumps/ to share with other machines:"
echo "  git add data/dumps/ && git commit -m 'chore: update dev data dumps'"
