# DenialDesk Go-Live Checklist

All items must be true before any real PHI enters the system.
See CLAUDE.md section 12.10 for the authoritative source.

Last reviewed: 2026-10-14 (Phase 2 security self-review)

---

## Founder Tasks (not code — must be completed before go-live)

- [ ] Legal entity formed; cyber liability + E&O insurance in place
- [ ] BAA signed with the cloud provider (AWS or equivalent HIPAA-eligible host)
- [ ] BAA signed with the LLM provider (Azure OpenAI or equivalent with zero data retention)
- [ ] Clinic BAA + service agreement drafted by a healthcare attorney
- [ ] HIPAA risk assessment completed; written security and privacy policies in place
- [ ] Outside security reviewer engaged and review passed
- [ ] Pilot clinics recruited, clinic BAAs and service agreements signed

---

## Engineering Tasks

### Auth
- [ ] Auth0 tenant provisioned under a signed BAA
- [ ] Auth0 RS256 JWKS wiring implemented in `denialdesk/auth/jwt.py` (currently raises `NotImplementedError` in prod mode)
- [ ] MFA policy enforced in Auth0 for all roles
- [ ] `DEV_MODE=false` set in prod environment
- [ ] `CORS_ALLOWED_ORIGINS` set to the production domain (not `*`)

### Infrastructure
- [ ] Deploy to HIPAA-eligible cloud under signed BAA (see `deploy/INFRASTRUCTURE.md`)
- [ ] PostgreSQL encryption at rest enabled (EBS/RDS encryption)
- [ ] TLS enforced end-to-end (HTTPS only, no HTTP fallback)
- [ ] All secrets in a secrets manager (AWS Secrets Manager or equivalent) — no `.env` files in prod
- [ ] Uploaded files in private S3 bucket (server-side encryption enabled, no public ACLs)
- [ ] Automated daily backups running (see `scripts/backup.sh`); backup encryption key in secrets manager
- [ ] Restore test passed against prod database (see `scripts/restore.sh` and `tests/test_backup_restore.py`)
- [ ] Two environments confirmed: `dev` (synthetic data only), `prod` (real PHI) — never cross-contaminated

### Access and Logging
- [ ] PHI-safe logging verified in prod (no patient data in CloudWatch / log aggregator)
- [ ] Access audit log (`access_logs` table) confirmed writing on all PHI routes in prod
- [ ] Least-privilege IAM roles in place (app container has no admin permissions)
- [ ] Log retention policy set (e.g., 7-year retention per HIPAA)

### Application
- [ ] Onboarding lock confirmed: test that a clinic with `pending_agreements` status cannot upload
- [ ] Tenant isolation tests passing in CI: `tests/test_tenant_isolation.py` (12 tests)
- [ ] Security self-review passed: `fix: Phase 2 step 11` (commit `1cbbc30`) — 3 critical bugs fixed
- [ ] Full test suite passing: 223+ tests, 0 failures

### Billing
- [ ] Stripe account created and connected (production keys, not test keys)
- [ ] `stripe_customer_id` populated for each onboarded practice
- [ ] Stripe invoice creation wired in `POST /api/ops/statements/{id}/send` (currently a stub)
- [ ] Fee rates confirmed per clinic contract before first statement generation

---

## Pre-Launch Verification (run on prod, not dev)

1. Create a test clinic account → verify onboarding gate blocks uploads
2. Sign BAA + SA → activate account → verify uploads now work
3. Upload a synthetic 835 batch → confirm diagnosis, drafting, review queue all function
4. Record a paid outcome → verify outcome → generate a statement → confirm fee math
5. Check `access_logs` table for PHI reads — confirm no raw PHI in log text
6. Attempt cross-tenant access with a clinic token → confirm 403/404
7. Attempt dev-token endpoint → confirm 404 (dev_mode=false)
8. Run restore from a prod backup to a staging DB → confirm row counts match

---

## Notes

- Real PHI must **never** enter `dev`, test fixtures, or local machines.
- No agent may submit to a real payer without a recorded human approval (enforced in v1).
- All LLM calls must use a BAA-covered provider with zero data retention.
- Delegated payer portal credentials must be in the secrets manager — never in `payer_portal_access` table.
