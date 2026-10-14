# DenialDesk Infrastructure Reference

## Environments

| | dev | prod |
|---|---|---|
| Database | SQLite (`data/dev.db`) | PostgreSQL 16 |
| `DEV_MODE` | `true` | `false` |
| Auth | HS256 dev tokens | Auth0 RS256 (BAA required) |
| PHI | synthetic only — never real | real PHI after go-live gate |

## Run locally (Docker Compose)

```bash
docker compose up --build
# API: http://localhost:8000
# Frontend: http://localhost:80
```

## Deploy to prod

```bash
# 1. Set all secrets from deploy/.env.prod.example in your secrets manager / environment
# 2. Make scripts executable (one-time):
chmod +x scripts/*.sh
# 3. Launch:
docker compose -f docker-compose.prod.yml up -d
```

Secrets are **never** hardcoded — inject via environment or AWS Secrets Manager before running.

## Backups

**Schedule:** daily via cron or AWS EventBridge.

```bash
# Cron example (runs at 02:00 UTC):
0 2 * * * /app/scripts/backup.sh >> /var/log/denialdesk-backup.log 2>&1
```

Required env vars: `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `BACKUP_S3_BUCKET`, `BACKUP_ENCRYPTION_KEY`.

S3 bucket must have versioning and server-side encryption enabled. Backups are AES-256 encrypted before upload.

## Restore

```bash
./scripts/restore.sh s3://denialdesk-backups-prod/backups/postgres/denialdesk_20261014_020000.sql.gz.enc
```

The script prompts for confirmation before overwriting the database.

**Test restores** in the dev environment monthly. The restore test in `tests/test_backup_restore.py` covers the Python schema layer; the shell scripts must be tested manually in prod.

## Go-live gate

All items in `CLAUDE.md` section 12.10 must be completed by the founders before any real PHI enters the system. Claude Code cannot complete these — they are legal and organizational tasks.
