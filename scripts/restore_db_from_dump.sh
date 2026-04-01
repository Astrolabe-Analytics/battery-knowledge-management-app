#!/usr/bin/env bash
# Restore a Postgres dump into the local docker-compose database and align schema
# for papers-registry endpoints, without re-running full ingestion.
#
# Usage:
#   bash scripts/restore_db_from_dump.sh --dump astrolabe_dump.sql
#
# Notes:
# - This drops and recreates the local 'astrolabe' database.
# - Handles UTF-16 SQL dumps by converting to UTF-8 automatically.
# - Applies paper_id compatibility migration and runs --assign-only.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DUMP_PATH=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--dump)
			DUMP_PATH="${2:-}"
			shift 2
			;;
		*)
			echo "Unknown argument: $1" >&2
			echo "Usage: bash scripts/restore_db_from_dump.sh --dump <path-to-sql-dump>" >&2
			exit 1
			;;
	esac
done

if [[ -z "$DUMP_PATH" ]]; then
	echo "ERROR: --dump is required" >&2
	echo "Usage: bash scripts/restore_db_from_dump.sh --dump <path-to-sql-dump>" >&2
	exit 1
fi

if [[ ! -f "$DUMP_PATH" ]]; then
	echo "ERROR: Dump file not found: $DUMP_PATH" >&2
	exit 1
fi

cd "$ROOT_DIR"

echo "[1/7] Ensuring docker services are up..."
docker compose up -d postgres api

echo "[2/7] Preparing dump encoding..."
ENC_INFO="$(file -b "$DUMP_PATH")"
TMP_SQL="/tmp/astrolabe_dump_utf8.sql"
if echo "$ENC_INFO" | grep -qi "UTF-16"; then
	echo "  Detected UTF-16 dump, converting to UTF-8: $TMP_SQL"
	iconv -f UTF-16LE -t UTF-8 "$DUMP_PATH" > "$TMP_SQL"
	RESTORE_FILE="$TMP_SQL"
else
	RESTORE_FILE="$DUMP_PATH"
fi

echo "[3/7] Backing up current database (best effort)..."
docker compose exec -T postgres pg_dump -U postgres -d astrolabe > "/tmp/astrolabe_backup_$(date +%s).sql" 2>/dev/null || true

echo "[4/7] Recreating local database..."
docker compose exec -T postgres psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS astrolabe;"
docker compose exec -T postgres psql -U postgres -d postgres -c "CREATE DATABASE astrolabe;"

echo "[5/7] Restoring dump into astrolabe..."
if ! docker compose exec -T postgres psql -U postgres -d astrolabe < "$RESTORE_FILE"; then
  echo "ERROR: Database restore failed. Check dump encoding/content." >&2
  exit 1
fi

echo "[6/7] Applying paper registry compatibility migration..."
docker compose exec -T postgres psql -U postgres -d astrolabe -c "ALTER TABLE papers ADD COLUMN IF NOT EXISTS paper_id VARCHAR(255);"
docker compose exec -T postgres psql -U postgres -d astrolabe -c "CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_paper_id_unique ON papers(paper_id) WHERE paper_id IS NOT NULL;"

echo "[7/7] Assigning stable paper IDs (no full pipeline run)..."
docker compose exec -T api python scripts/export_paper_registry.py --assign-only

echo ""
echo "Restore complete. Quick counts:"
docker compose exec -T postgres psql -U postgres -d astrolabe -c "SELECT 'papers' AS table, count(*) FROM papers UNION ALL SELECT 'chunks', count(*) FROM chunks UNION ALL SELECT 'paper_references', count(*) FROM paper_references;"

echo ""
echo "Post-restore verification:"
curl -sf http://localhost:8003/api/health >/dev/null && echo "  API health: OK" || echo "  API health: FAILED (try: docker compose restart api)"
ASSIGNED="$(docker compose exec -T postgres psql -U postgres -d astrolabe -t -c "SELECT COUNT(*) FROM papers WHERE paper_id IS NOT NULL;" | tr -d '[:space:]')"
echo "  Papers with assigned paper_id: ${ASSIGNED:-0}"
if [[ "${ASSIGNED:-0}" == "0" ]]; then
  echo "ERROR: No paper_id values assigned." >&2
  exit 1
fi

echo ""
echo "Done. No full ingestion re-run required after this restore path."
