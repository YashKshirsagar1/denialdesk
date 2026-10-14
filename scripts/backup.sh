#!/usr/bin/env bash
# backup.sh — dump PostgreSQL, encrypt with AES-256, and upload to S3.
# Requires: pg_dump, openssl, aws CLI, and these env vars:
#   POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
#   BACKUP_ENCRYPTION_KEY (from secrets manager — never hardcoded)
#   BACKUP_S3_BUCKET
# Schedule via cron or AWS EventBridge (daily recommended).

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/tmp/denialdesk_${TIMESTAMP}.sql.gz"
ENCRYPTED_FILE="${BACKUP_FILE}.enc"

echo "[backup] Starting backup at ${TIMESTAMP}"

# Dump and compress
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
  -h "${POSTGRES_HOST:-db}" \
  -U "${POSTGRES_USER}" \
  "${POSTGRES_DB}" | gzip > "${BACKUP_FILE}"

# Encrypt with AES-256 — key must come from secrets manager
openssl enc -aes-256-cbc -pbkdf2 -iter 100000 \
  -pass "env:BACKUP_ENCRYPTION_KEY" \
  -in "${BACKUP_FILE}" -out "${ENCRYPTED_FILE}"

# Upload to S3 (bucket must have versioning and SSE enabled)
aws s3 cp "${ENCRYPTED_FILE}" \
  "s3://${BACKUP_S3_BUCKET}/backups/postgres/${ENCRYPTED_FILE##*/}" \
  --sse AES256

# Clean up local plaintext
rm -f "${BACKUP_FILE}" "${ENCRYPTED_FILE}"

echo "[backup] Backup complete: ${ENCRYPTED_FILE##*/}"
