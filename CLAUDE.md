# DenialDesk — Agentic Denial-Recovery Engine

This is the project brief for Claude Code. Read it fully before writing code. It captures the business context, the architecture, and the MVP scope agreed on in planning.

## 1. What we're building (one paragraph)

DenialDesk recovers money that small US medical practices have written off. A practice uploads denied insurance claims (start: ~10 stuck denials). Our agents diagnose why each claim was denied, score whether it's winnable, draft a payer-specific appeal or corrected claim, submit it through the payer's channel (portal / fax / phone), and track it until it's paid. We charge a contingency fee: 20–25% of recovered dollars on standard denials, 30–35% on aged ones. We're open to every specialty from day one and let the data pick the winners.

## 2. Why it works (the "root questions" we must keep true)

- **Practices didn't fail, they quit.** 50–65% of denied claims are never reworked (MGMA). Much of our win rate is finishing abandoned work.
- **Cross-practice pattern data.** One practice sees only its denials. We see many, so we learn which reason code + payer + procedure gets overturned with which document or policy citation. **This outcome data is the moat. Design every component to capture it.**
- **Persistence is automated.** Agents don't forget follow-ups and they escalate on their own.
- **Knowing what not to attempt.** Some denials are unwinnable (not covered, truly miscoded, past timely filing). The scoring step must decline them early. Adverse selection is built into the model (practices upload their ugliest claims), so triage is a core feature, not a nice-to-have.

## 3. Architecture: an assembly line of specialized agents

```
Ingest -> Diagnose + Score -> [Winnable?] -- no --> Decline / park (with reason)
                                   | yes
                                   v
                             Draft appeal -> Act on payer -> Track + escalate -> Paid
                                                 ^ (human-in-the-loop)            |
                                                 +------ learning loop <----------+
```

| Component | Job | Notes |
|---|---|---|
| **Ingestion** | Parse the 835 (ERA/remittance with the denial), the 837 (original claim), EOB PDFs, and chart notes into one structured `Case` | OCR + parsing. Deterministic code where possible, LLM only for messy PDFs. |
| **Diagnosis agent** | Read the CARC/RARC codes, classify the root cause, and produce a winnability score + expected value | Root-cause classes: missing/invalid prior auth, coding error, eligibility, medical necessity, timely filing, bundling/NCCI, duplicate, missing info. |
| **Strategy + drafting agent** | Look up the payer's appeal rules and deadlines, pick the supporting docs, and draft the appeal letter or corrected claim | Payer-specific templates live in a playbook store that grows from outcomes. |
| **Action layer** | Submit through the payer's channel | MVP: generate a ready-to-submit packet + human submits. Later: browser automation for portals, an e-fax API, voice agents for phone. |
| **Tracking agent** | Watch status, catch re-denials and requests for more info, and escalate to 2nd-level appeal | Deadlines are first-class data. Never miss a filing window. |
| **Learning loop** | Record every outcome (won/lost, $ recovered, days to pay, what was attached) and feed it back to the scoring and playbooks | This is the proprietary data asset. Log richly from day one. |

Orchestrator: one coordinator moves each `Case` through explicit states. Agents are stateless workers; the state lives in the database.

**Case states:** `ingested -> diagnosed -> declined | approved -> drafted -> awaiting_human_review -> submitted -> pending_payer -> paid | re_denied -> (escalated) -> closed`

## 4. Human-in-the-loop (non-negotiable for MVP)

- A human reviews **every** appeal before submission in v1. The agent drafts; the human approves or edits. Log their edits, because they're training signal.
- Phone calls: humans make them in v1, but the agent produces a **call packet** (claim facts, denial reason, the exact ask, the payer phone tree path, and talking points) so a call takes minutes.
- Target trajectory: about 60/40 human/agent on the action layer at launch, moving toward 90%+ agent. Track this ratio as a metric.

## 5. MVP scope (build this first, nothing more)

**In scope:**
1. Upload: CSV/835 file + PDFs for a batch of denials.
2. Ingestion into a normalized `Case` model.
3. Diagnosis + scoring with a clear, explainable reason ("Declined: past timely filing limit for this payer").
4. Appeal letter drafting from templates + LLM, with citations to the chart notes used.
5. A review queue UI where a human approves, edits, or rejects each draft.
6. Export a submission packet (PDF letter + attachments) and a phone call packet.
7. Manual outcome entry (paid / denied / amount / date), feeding the outcomes table.
8. A KPI dashboard (see section 7).

**Out of scope for MVP:** live portal automation, voice agents, the e-fax integration, billing/payments, multi-tenant self-serve signup, and the claims-buying model.

## 6. Data and compliance guardrails (read before touching data)

- **Build and test only on synthetic or properly de-identified data.** Do not load real PHI until HIPAA controls are in place: a signed BAA with every vendor that touches PHI (including the LLM provider), encryption at rest and in transit, access logging, and least-privilege access.
- Planned LLM path: a provider with a signed BAA and US data regions (Azure OpenAI was the planned choice). Keep the model behind an interface so the provider can be swapped.
- Write a synthetic data generator early: realistic 835/837 records, CARC/RARC codes, payers, and chart-note snippets. Seed it with denial types across several specialties.
- Every case keeps an audit trail: who or what did each action, when, and with which inputs. Required for compliance, and it's also the learning data.
- Never let an agent submit anything to a payer without a recorded human approval in v1.

## 7. KPIs the system must compute from day one

These prove the three strategic assets (the recovery engine with pattern data, small-practice relationships, and proven recovery performance):

- Recovery rate per claim (% of attempted claims paid)
- Average dollars recovered per claim, and total recovered per practice
- Cost to serve per claim (human minutes + model cost)
- Days from upload to payment
- Decline rate at triage, and the accuracy of the score (predicted vs actual outcome)
- Human-vs-agent share of action-layer work
- Gross margin per practice (fee minus cost to serve)
- Win rate by payer x reason code x specialty, which is the pattern-data view

## 8. Suggested data model (starting point, refine as needed)

- `Practice` (id, name, specialty, contact)
- `Batch` (id, practice_id, uploaded_at, source files)
- `Case` (id, batch_id, payer, patient_ref [synthetic], dos, cpt/hcpcs, icd10, billed_amt, allowed_amt, carc, rarc, denial_date, filing_deadline, state)
- `Diagnosis` (case_id, root_cause, winnability_score, expected_value, rationale, model_version)
- `Draft` (case_id, type [appeal|corrected_claim|call_packet], content, attachments, version)
- `Review` (draft_id, reviewer, decision, edits_diff, timestamp)
- `Submission` (case_id, channel [portal|fax|mail|phone], submitted_at, reference_no)
- `Outcome` (case_id, result, amount_recovered, paid_date, notes)
- `PayerPlaybook` (payer, reason_code, specialty, winning_strategy, required_docs, success_count, attempt_count)
- `AuditEvent` (case_id, actor [agent/human], action, inputs_hash, timestamp)

## 9. Build order

1. Repo scaffold, config, and the LLM provider interface (behind an abstraction).
2. Synthetic data generator.
3. Data model + Case state machine + audit log.
4. Ingestion (CSV/835 first, PDFs second).
5. Diagnosis + scoring agent, with an eval set of labeled synthetic cases.
6. Drafting agent + payer templates.
7. Review queue UI.
8. Packet export (letter PDF + call packet).
9. Outcome entry + learning loop updates to `PayerPlaybook`.
10. KPI dashboard.

After each step, write tests and keep a running eval for diagnosis accuracy and draft quality.

## 10. Working style for this repo

- Be direct and concise. Prefer simple, working code over clever abstractions.
- Ask before choosing a stack if it isn't already set up; otherwise propose a default and explain it in one line.
- Flag anything that would touch real PHI or submit to a real payer, and stop for confirmation.

## 11. Status

Phase 1 (sections 1–10, the MVP agent pipeline) is built. Before starting Phase 2, review the existing code against this file and list any gaps. Don't rebuild what already works.

## 12. Phase 2 — Pilot-ready portal

**Goal:** 2–3 friendly clinics send real denials, we work them, and we measure a real recovery rate. Make it secure and simple, not polished.

**Product shape:** a secure web portal for clinics plus an internal ops console for our team. The clinic never runs the agent. They upload and watch; we work the claims behind the scenes.

### 12.1 Clinic portal (what the clinic sees)
- Login with MFA, invite-only (no public signup yet).
- Upload a batch: 835/CSV + EOB PDFs + chart notes.
- Case list with plain-English status ("Appeal submitted to Aetna on 10/20", "Declined: past filing deadline").
- **Requests inbox:** when the agent needs a missing document, the clinic gets a request and uploads the answer there.
- Dashboard: dollars submitted, dollars recovered, cases in progress.
- Monthly statement of recoveries and fees.

### 12.2 Internal ops console (what our team sees)
- The existing review queue, call packets, and outcome entry, now across all clinics.
- Cross-clinic KPI dashboard (section 7) and win rate by payer x reason code x specialty.
- Deadline view: every case sorted by its next filing deadline, with alerts.

### 12.3 Multi-tenancy and access
- Every record carries `tenant_id` (the clinic). Enforce isolation in the database (row-level security or equivalent), not only in app code.
- Write automated tests proving one clinic can never read another clinic's data.
- Roles: `clinic_admin`, `clinic_staff`, `reviewer`, `ops_admin`.
- Use a managed identity provider that supports MFA. Don't hand-roll auth.

### 12.4 Infrastructure (HIPAA-ready)
- Deploy on a HIPAA-eligible cloud under a signed BAA, using only BAA-covered services.
- Two environments: `dev` (synthetic data only, forever) and `prod` (real PHI). Real PHI never enters dev, test fixtures, or local machines.
- Encryption at rest and in transit. Secrets in a secrets manager, never in code or `.env` files committed to git.
- Uploaded files go in private storage with short-lived signed URLs.
- Automated backups with a tested restore.
- **No PHI in logs, error tracking, or analytics.** Scrub or tokenize before anything leaves the app.

### 12.5 LLM usage with PHI
- Only call an LLM provider under a signed BAA, with zero data retention enabled where available.
- Send the minimum necessary data in each prompt.
- Log model version + prompt template id per call, but not raw PHI outside the protected database.

### 12.6 Audit
- Log every access to PHI, reads included, not just changes: who, what, when, why.
- Clinic admins can see an access log for their own data.

### 12.7 Onboarding flow
- A clinic account stays locked (no uploads) until the BAA and service agreement are marked signed by an ops admin.
- Onboarding checklist: agreements signed, practice details, specialties, payers they bill, delegated payer-portal accounts created for our staff (never shared clinic passwords).

### 12.8 Recovery verification and billing
- An `Outcome` becomes billable only with evidence: a matching 835 payment line or a clinic confirmation recorded in the portal.
- Fee calculation: 20–25% standard, 30–35% aged, configurable per clinic contract.
- Monthly statement generated per clinic; invoices sent through a payment provider such as Stripe. Never store card or bank numbers ourselves.

### 12.9 Phase 2 build order
1. Gap review of the Phase 1 code against this file.
2. Tenant model + row-level isolation + isolation tests.
3. Auth with MFA and roles.
4. Clinic portal: upload, case list, status.
5. Requests inbox (agent -> clinic document requests).
6. Ops console upgrades: multi-clinic queue, deadline view.
7. PHI-safe logging and access audit.
8. Onboarding flow with the agreement lock.
9. Recovery verification + fee calc + monthly statements.
10. Infrastructure-as-code for `prod`, backups, restore test.
11. Security review pass (Claude Code self-review, then an outside reviewer before go-live).

### 12.10 Go-live gate (all must be true before any real PHI)
Claude Code can't do these. They are founder tasks, and the app must not be pointed at real data until each is done:
- [ ] Legal entity formed; cyber + E&O insurance in place.
- [ ] BAA signed with the cloud provider and the LLM provider.
- [ ] Clinic BAA + service agreement drafted by a healthcare lawyer.
- [ ] HIPAA risk assessment completed; written security and privacy policies.
- [ ] Isolation tests, restore test, and security review all passed.
- [ ] Pilot clinics recruited and signed.

### 12.11 Pilot success metrics
- Recovery rate on attempted claims, and dollars recovered per clinic.
- Days from upload to payment.
- Score accuracy (predicted winnable vs actual outcome).
- Reviewer minutes per claim.
- Would the clinic keep using it and refer another practice?

## Reference

Pitch deck (business context, market data, root questions, risks, exit thesis):
https://claude.ai/code/artifact/c0614e15-31c8-4a4f-a72e-47b1f0a12579

## 13. Standalone web app (current state)

DenialDesk now runs as one standalone app (`make run`, http://localhost:8000): FastAPI serves the React UI plus the API. Login is built-in email + password (argon2id, lockout after 5 failures, 30-min idle sign-out) in `denialdesk/api/routers/auth.py`, kept behind the JWT layer so a managed IdP can replace it. **It has no MFA — still required before real PHI (see 12.3).** Self-signup creates a clinic locked until an ops admin activates it (12.7). See DEMO.md.
