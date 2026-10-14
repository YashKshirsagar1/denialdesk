#!/usr/bin/env bash
# reset_demo.sh — wipe the dev database and reseed the demo from scratch.
#
# Usage:
#   bash scripts/reset_demo.sh
#   make demo
#
# Run 'chmod +x scripts/reset_demo.sh' after cloning if needed.

set -euo pipefail

DB_PATH="${DATABASE_PATH:-data/dev.db}"
export DATABASE_URL="sqlite+aiosqlite:///./${DB_PATH}"

echo "[reset] Removing ${DB_PATH}..."
rm -f "${DB_PATH}"

echo "[reset] Creating tables (SQLite dev mode — skips Alembic batch-mode issues)..."
DATABASE_URL="${DATABASE_URL}" python scripts/init_dev_db.py

echo "[reset] Seeding demo data..."
DATABASE_URL="${DATABASE_URL}" python scripts/seed_demo.py

echo ""
echo "[reset] Done. Start the app:"
echo "  uvicorn denialdesk.api.main:app --reload &"
echo "  cd frontend && npm run dev"
echo "Then open: http://localhost:5173"
