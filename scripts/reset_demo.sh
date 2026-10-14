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

echo "[reset] Removing ${DB_PATH}..."
rm -f "${DB_PATH}"

echo "[reset] Running Alembic migrations..."
alembic upgrade head

echo "[reset] Seeding demo data..."
python scripts/seed_demo.py

echo ""
echo "[reset] Done. Start the app:"
echo "  uvicorn denialdesk.api.main:app --reload &"
echo "  cd frontend && npm run dev"
echo "Then open: http://localhost:5173"
