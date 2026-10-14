# DenialDesk Demo Walkthrough

Lakeside Family Practice uploaded 10 denied claims. The system auto-declined 3 (unwinnable), drafted appeals for 7, and already recovered one payment. This walkthrough shows both sides: the clinic's portal and the ops team's console.

---

## Setup (one time)

```bash
# Install Python deps
pip install -e .

# Install frontend deps
cd frontend && npm install && cd ..
```

---

## Reset to a clean demo state

```bash
make demo
# or: bash scripts/reset_demo.sh
```

This wipes `data/dev.db`, runs all Alembic migrations, seeds the demo, and prints two JWT tokens. **Copy the tokens** — you'll paste them into the login form.

Expected output:
```
=== Demo seeded ===
Practice : Lakeside Family Practice (id=1)
Cases    : 10 total
  Declined (3) : PT-LAK-007, PT-LAK-008, PT-LAK-009
  Awaiting review (6) : PT-LAK-002, PT-LAK-003, ...
  Paid (1)     : PT-LAK-001 ($185.00 recovered)

Dev tokens (valid 8 hours):
  Clinic admin : eyJ...
  Ops admin    : eyJ...
```

---

## Start the app

```bash
# Terminal 1 — API
uvicorn denialdesk.api.main:app --reload

# Terminal 2 — Frontend
cd frontend && npm run dev
```

Open: **http://localhost:5173**

---

## The story

Lakeside Family Practice has 10 denied claims sitting in their system. They uploaded them through the portal. Our agents analyzed every one:

- **3 declined automatically** — no viable appeal path (excluded service, timely filing window closed, exact duplicate).
- **6 approved and drafted** — appeal letters ready for our team's review.
- **1 already paid** — PT-LAK-001, Aetna reversed the denial, $185 recovered, 22% fee invoiced.

---

## Act 1: The clinic's view

*Use the **clinic_admin token** printed by `make demo`.*

### Step 1 — Sign in as the clinic
- Open http://localhost:5173
- Paste the **clinic_admin** token into the Token field
- Select role: **clinic_admin**
- Set Tenant ID: **1**
- Click **Sign In**

You land on **My Claims**.

### Step 2 — Read the case list
Point out the status column:

| Patient | Payer | Status |
|---------|-------|--------|
| PT-LAK-001 | Aetna | **Paid** (green) |
| PT-LAK-007 | UnitedHealthcare | Declined — not pursuing appeal |
| PT-LAK-008 | Aetna | Declined — not pursuing appeal |
| PT-LAK-009 | Cigna | Declined — not pursuing appeal |
| PT-LAK-002…006, 010 | Various | Appeal under internal review |

**Talking point:** "You can see exactly why each claim was declined — no black box. PT-LAK-008 was 400 days old; Aetna's window is 180 days. We caught that on day one instead of wasting time on an unwinnable appeal."

### Step 3 — Expand a declined case
Click **PT-LAK-008** (Aetna, $265, timely filing).

The detail panel shows: "Timely filing deadline exceeded. Claim denied 385 days after date of service. Aetna's filing window is 180 days; no waiver exceptions apply."

**Talking point:** "We surface the exact reason in plain English so the practice understands what happened — not just a code."

### Step 4 — Dashboard tab
Click **Dashboard**.

Shows:
- **$185 recovered** (PT-LAK-001)
- **6 in progress**
- **1 paid**
- Recovery rate: 100% of attempted claims paid so far

### Step 5 — Requests tab
Click **Requests**.

Two document requests are pending:
- PT-LAK-001 (PT-LAK-005): chart note needed for CARC 16 (missing info)
- PT-LAK-002 (PT-LAK-010): prior auth needed for CARC 4

**Talking point:** "Instead of a phone call from your billing team, you get a structured inbox. Upload the document here — we handle the rest."

### Step 6 — Access Log tab
Click **Access Log** (visible to clinic_admin only).

Shows every read of this practice's data — who, what, when. "HIPAA requires we log every access to your data. Clinic admins can see this log at any time."

---

## Act 2: The ops team's view

*Sign out (top-right button), sign back in with the **ops_admin token**, role: **ops_admin**, Tenant ID: blank.*

### Step 7 — Review Queue tab
The queue shows 6 cases awaiting review for **Lakeside Family Practice**, with the practice name visible on every row.

### Step 8 — Approve an appeal (PT-LAK-003)
Click **PT-LAK-003** (UnitedHealthcare, $265, CARC 96 — non-covered).

The panel shows:
- **Diagnosis rationale:** "CARC 96 maps to root cause 'not_covered'. Winnability score 0.20. Proceeding with appeal — strong documentation likely to overturn."
- **Appeal letter draft:** fully written, references CPT 99215, payer, denial reason, and documentation to attach.

Click **Approve**. The case moves to **Submitted**.

**Talking point:** "The agent drafts the letter. Our reviewer reads it in under a minute and hits Approve. No one types from scratch."

### Step 9 — Edit and approve (PT-LAK-004)
Click **PT-LAK-004** (Aetna, $95, CARC 97 — bundling/NCCI).

Edit the letter body — add one sentence: *"The services were rendered separately and are not subject to NCCI bundling edit."*

Click **Edit & Approve**. The diff is logged as training signal.

### Step 10 — Deadlines tab
Click **Deadlines**.

- PT-LAK-007, PT-LAK-008, PT-LAK-009 appear in **red** (overdue — past their filing deadline).
- The remaining winnable cases show upcoming deadlines in yellow/green.

**Talking point:** "Deadlines are first-class data. The system tracks every filing window and surfaces cases before the window closes — automatically."

### Step 11 — Dashboard tab
Click **Dashboard** (ops view).

Shows the cross-clinic KPI view:
- Win rates by payer × CARC code × specialty
- Pipeline: cases by state
- Score accuracy table

### Step 12 — Practices tab
Click **Practices**.

Shows Lakeside Family Practice: `onboarding_status = active`, both agreements signed. Quick-action buttons for Sign BAA / Activate / Suspend are visible for future clinics.

### Step 13 — Statements tab
Click **Statements**.

Shows the September statement for Lakeside Family Practice: $185 recovered, $40.70 fee (22%), status: Sent.

Click **Download PDF** — opens the generated statement PDF.

---

## Act 3: Recovering more money (optional — shows the full loop)

### Step 14 — Approve PT-LAK-002
In the Review Queue, click **PT-LAK-002** (BCBS, $125, CARC 4 — prior auth).

Click **Approve**.

### Step 15 — Enter the outcome
Navigate to **Outcomes** (or use the API directly):
- Result: **paid**
- Amount: **$125**
- Date: today

### Step 16 — Verify the outcome
Click **Verify** (clinic_confirmation). Billable amount: $125 × 22% = $27.50.

### Step 17 — Generate a new statement
In the Statements tab, click **Generate**:
- Practice: Lakeside Family Practice
- Period: this month (2026-10-01 to 2026-10-31)

New statement shows $125 recovered, $27.50 fee.

---

## Resetting between demos

```bash
make demo
```

Wipes the DB, runs migrations, reseeds, prints fresh tokens. Takes about 10 seconds.
