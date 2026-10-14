#!/usr/bin/env bash
# restore.sh — decrypt and restore a backup from S3.
# Usage: ./scripts/restore.sh s3://bucket/backups/postgres/denialdesk_20261014_120000.sql.gz.enc
# Requires: aws CLI, openssl, psql, and the same env vars as backup.sh.

set -euo pipefail

S3_PATH="${1:?Usage: restore.sh <s3-path>}"
ENCRYPTED_FILE="/tmp/$(basename "${S3_PATH}")"
DECRYPTED_FILE="${ENCRYPTED_FILE%.enc}"
DECOMPRESSED_FILE="${DECRYPTED_FILE%.gz}"

echo "[restore] Downloading ${S3_PATH}"
aws s3 cp "${S3_PATH}" "${ENCRYPTED_FILE}"

echo "[restore] Decrypting"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
  -pass "env:BACKUP_ENCRYPTION_KEY" \
  -in "${ENCRYPTED_FILE}" -out "${DECRYPTED_FILE}"

echo "[restore] Decompressing"
gunzip "${DECRYPTED_FILE}"

echo "[restore] Restoring to database (will overwrite existing data)"
echo "  Target: ${POSTGRES_HOST:-db}/${POSTGRES_DB}"
read -rp "  Type 'yes' to confirm: " CONFIRM
[[ "${CONFIRM}" == "yes" ]] || { echo "Aborted."; exit 1; }

PGPASSWORD="${POSTGRES_PASSWORD}" psql \
  -h "${POSTGRES_HOST:-db}" \
  -U "${POSTGRES_USER}" \
  "${POSTGRES_DB}" < "${DECOMPRESSED_FILE}"

rm -f "${ENCRYPTED_FILE}" "${DECOMPRESSED_FILE}"
echo "[restore] Restore complete."
