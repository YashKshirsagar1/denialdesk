"""Seed the dev database with a realistic demo: Lakeside Family Practice, 10 cases.

Run from repo root:
    python scripts/seed_demo.py

For a full reset (wipe + migrate + seed):
    make demo   # or: bash scripts/reset_demo.sh
"""
import json
import sys
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from denialdesk.auth.jwt import create_dev_token
from denialdesk.auth.models import Role
from denialdesk.models.case import (
    AuditEvent,
    Base,
    Batch,
    Case,
    CaseState,
    Diagnosis,
    DocumentRequest,
    DocumentRequestStatus,
    Draft,
    OnboardingStatus,
    Outcome,
    Practice,
    Review,
    Statement,
    StatementStatus,
    VerificationMethod,
)

DB_PATH = "data/dev.db"

# ---------------------------------------------------------------------------
# Demo case definitions
# ---------------------------------------------------------------------------
# Each row: (patient_ref, payer, cpt, carc, rarc, dos_days_ago, denial_days_ago,
#            billed_amt, decline_override, decline_rationale)
#
# decline_override=True means we force the winnability score to < 0.20 so the
# case is declined regardless of what the rule engine would normally compute.
# ---------------------------------------------------------------------------
_DEMO_CASES = [
    # Winnable cases
    ("PT-LAK-001", "Aetna",                  "99214", "16", "M76",  60, 45, 185.00, False, None),
    ("PT-LAK-002", "Blue Cross Blue Shield",  "93000", "4",  "M51",  90, 75, 125.00, False, None),
    ("PT-LAK-003", "UnitedHealthcare",        "99215", "96", "N130", 45, 30, 265.00, False, None),
    ("PT-LAK-004", "Aetna",                  "80053", "97", "N519", 55, 40,  95.00, False, None),
    ("PT-LAK-005", "Cigna",                  "71046", "16", "M76",  35, 20, 310.00, False, None),
    ("PT-LAK-006", "Blue Cross Blue Shield",  "99213", "22", "N30",  70, 55, 145.00, False, None),
    # Declined cases
    (
        "PT-LAK-007", "UnitedHealthcare", "99214", "50", "N130", 200, 185, 185.00,
        True,
        "Service is excluded from the patient's plan benefits. CARC 50 (non-covered service). "
        "No appeal path — payer policy explicitly excludes this procedure under this plan."
    ),
    (
        "PT-LAK-008", "Aetna", "99215", "29", "N29", 400, 385, 265.00,
        True,
        "Timely filing deadline exceeded. Claim denied 385 days after date of service. "
        "Aetna's filing window is 180 days; no waiver exceptions apply."
    ),
    (
        "PT-LAK-009", "Cigna", "99213", "18", "N522", 60, 45, 145.00,
        True,
        "Exact duplicate of a previously adjudicated claim. CARC 18 indicates this claim "
        "was already processed and paid. Resubmission will be rejected."
    ),
    # More winnable
    ("PT-LAK-010", "Blue Cross Blue Shield",  "99214", "4",  "M51",  25, 10, 185.00, False, None),
]

_CARC_ROOT_CAUSE = {
    "4": "not_covered", "16": "missing_info", "18": "duplicate",
    "22": "eligibility", "29": "timely_filing", "50": "not_covered",
    "96": "not_covered", "97": "bundling_ncci",
}
_CARC_DELTA = {
    "4": -0.30, "11": 0.15, "16": 0.20, "18": -0.10,
    "22": -0.20, "29": 0.0, "45": -0.05, "50": 0.10,
    "96": -0.30, "97": 0.05,
}


def _rule_score(carc: str, filing_deadline: datetime | None) -> float:
    score = 0.5 + _CARC_DELTA.get(carc, 0.0)
    if carc == "29" and filing_deadline:
        now = datetime.now(timezone.utc)
        dl = filing_deadline if filing_deadline.tzinfo else filing_deadline.replace(tzinfo=timezone.utc)
        score = 0.5 + (-0.40 if dl < now else 0.10)
    return max(0.05, min(0.95, round(score, 2)))


def _appeal_letter(patient_ref: str, payer: str, cpt: str, carc: str, practice_name: str) -> str:
    reasons = {
        "16": "missing information required to process the claim",
        "4":  "non-covered service",
        "96": "non-covered charge",
        "97": "claim bundling (NCCI edit)",
        "22": "coordination of benefits",
        "29": "timely filing limit",
        "18": "duplicate claim",
        "50": "not medically necessary",
    }
    reason = reasons.get(carc, f"reason code {carc}")
    return f"""RE: Appeal for Claim {patient_ref} — CPT {cpt}

Dear {payer} Appeals Department,

We are writing to formally appeal the denial of the above-referenced claim, which was denied for {reason} (CARC {carc}).

Patient: {patient_ref}
Procedure: CPT {cpt}
Rendering Provider: {practice_name}

We respectfully request reconsideration. The enclosed documentation supports the medical necessity, coverage eligibility, and accurate coding of this service. Please review the attached clinical notes, authorization records, and policy citations.

We request a response within 30 days per your appeals process requirements.

Sincerely,
{practice_name} — Billing Department"""


def _call_packet(patient_ref: str, payer: str, cpt: str, carc: str) -> str:
    return f"""CALL PACKET — {payer} Provider Services

Claim: {patient_ref} | CPT: {cpt} | Denial: CARC {carc}

Phone tree: Provider Services → Claims Appeals → Speak to representative
Reference number: [obtain at start of call]

Opening ask:
  "I'm calling to appeal claim {patient_ref} denied under CARC {carc}.
   I'd like to understand the specific reason and initiate a formal appeal."

Key talking points:
  1. Confirm the claim was received and processed
  2. Request the exact policy citation for the denial
  3. Ask whether additional documentation would overturn the denial
  4. Document: representative name, call reference number, next steps

Target outcome: Written confirmation of appeal submission or fax number for documentation."""


def seed(db_path: str) -> None:
    now = datetime.now(timezone.utc)
    today = now.date()

    url = f"sqlite:///{db_path}"
    engine = create_engine(url, echo=False)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # ------------------------------------------------------------------
        # Practice
        # ------------------------------------------------------------------
        practice = Practice(
            name="Lakeside Family Practice",
            specialty="Family Medicine",
            contact="billing@lakesidefp.com",
            address="142 Lakeshore Drive, Madison, WI 53703",
            phone="608-555-0142",
            npi="1234567890",
            specialties='["Family Medicine"]',
            payers_billed='["Aetna", "Blue Cross Blue Shield", "UnitedHealthcare", "Cigna"]',
            onboarding_status=OnboardingStatus.active.value,
            baa_signed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            baa_signed_by="ops-admin-demo",
            service_agreement_signed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            service_agreement_signed_by="ops-admin-demo",
            fee_rate_standard=Decimal("0.2200"),
            fee_rate_aged=Decimal("0.3200"),
            aged_threshold_days=180,
        )
        session.add(practice)
        session.flush()

        # ------------------------------------------------------------------
        # Batch
        # ------------------------------------------------------------------
        batch = Batch(
            practice_id=practice.id,
            tenant_id=practice.id,
            uploaded_at=now - timedelta(days=30),
            source_files="demo_835_lakeside_2026.835",
        )
        session.add(batch)
        session.flush()

        # ------------------------------------------------------------------
        # Cases
        # ------------------------------------------------------------------
        created_cases: list[Case] = []

        for i, (
            patient_ref, payer, cpt, carc, rarc,
            dos_days_ago, denial_days_ago, billed_amt,
            decline_override, decline_rationale
        ) in enumerate(_DEMO_CASES):
            dos = now - timedelta(days=dos_days_ago)
            denial_date = now - timedelta(days=denial_days_ago)
            filing_deadline = denial_date + timedelta(days=180)
            claim_number = f"DEMO-ICN-{i + 1:04d}"

            case = Case(
                batch_id=batch.id,
                tenant_id=practice.id,
                payer=payer,
                patient_ref=patient_ref,
                dos=dos,
                cpt_hcpcs=cpt,
                icd10="Z00.00",
                billed_amt=billed_amt,
                allowed_amt=round(billed_amt * 0.8, 2),
                carc=carc,
                rarc=rarc,
                denial_date=denial_date,
                filing_deadline=filing_deadline,
                state=CaseState.ingested,
                claim_number=claim_number,
            )
            session.add(case)
            session.flush()

            session.add(AuditEvent(
                case_id=case.id, tenant_id=practice.id,
                actor="seed_demo", action="ingested",
                timestamp=now - timedelta(days=29),
            ))

            # --- diagnosed ---
            ev = case.transition(CaseState.diagnosed, actor="diagnosis_agent",
                                 action_note=f"carc={carc}")
            session.add(ev)
            session.flush()

            root_cause = _CARC_ROOT_CAUSE.get(carc, "other")

            if decline_override:
                score = 0.08
                rationale = decline_rationale
            else:
                score = _rule_score(carc, filing_deadline)
                rationale = (
                    f"CARC {carc} maps to root cause '{root_cause}'. "
                    f"Winnability score {score:.2f} based on denial type and payer history. "
                    f"Proceeding with appeal — strong documentation likely to overturn."
                )

            diag = Diagnosis(
                case_id=case.id,
                tenant_id=practice.id,
                root_cause=root_cause,
                winnability_score=score,
                expected_value=round(score * billed_amt * 0.75, 2),
                rationale=rationale,
                model_version="rule_v1+demo",
            )
            session.add(diag)
            session.flush()

            if score < 0.20:
                # --- declined ---
                ev = case.transition(CaseState.declined, actor="coordinator",
                                     action_note=f"auto_decline score={score:.2f}")
                session.add(ev)
                session.flush()
            else:
                # --- approved → drafted → awaiting_human_review ---
                ev = case.transition(CaseState.approved, actor="coordinator")
                session.add(ev)
                session.flush()

                # Appeal draft
                appeal = Draft(
                    case_id=case.id, tenant_id=practice.id,
                    type="appeal",
                    content=_appeal_letter(patient_ref, payer, cpt, carc, "Lakeside Family Practice"),
                    attachments=json.dumps(["clinical_notes", "eob", "physician_letter"]),
                    version=1,
                )
                session.add(appeal)
                ev = case.transition(CaseState.drafted, actor="drafting_agent",
                                     action_note="drafted appeal")
                session.add(ev)
                session.flush()

                # Call packet draft
                call_draft = Draft(
                    case_id=case.id, tenant_id=practice.id,
                    type="call_packet",
                    content=_call_packet(patient_ref, payer, cpt, carc),
                    attachments=None,
                    version=1,
                )
                session.add(call_draft)

                ev = case.transition(CaseState.awaiting_human_review, actor="coordinator",
                                     action_note="ready for review")
                session.add(ev)
                session.flush()

                # Document requests for cases that need supporting docs
                if carc in ("16",):  # missing info
                    session.add(DocumentRequest(
                        case_id=case.id, tenant_id=practice.id,
                        requested_by="diagnosis_agent",
                        document_type="chart_note",
                        description=(
                            f"Please upload the chart note or clinical documentation "
                            f"for the service on {dos.date()} (CPT {cpt})."
                        ),
                        status=DocumentRequestStatus.pending,
                        created_at=now - timedelta(days=28),
                    ))
                elif carc in ("4",):  # prior auth
                    session.add(DocumentRequest(
                        case_id=case.id, tenant_id=practice.id,
                        requested_by="diagnosis_agent",
                        document_type="prior_auth",
                        description=(
                            f"Please upload the prior authorization for CPT {cpt} "
                            f"from {payer}."
                        ),
                        status=DocumentRequestStatus.pending,
                        created_at=now - timedelta(days=28),
                    ))

            created_cases.append(case)

        session.commit()

        # ------------------------------------------------------------------
        # Advance case 1 (PT-LAK-001) all the way to paid
        # ------------------------------------------------------------------
        case1 = created_cases[0]

        # Find the appeal draft
        appeal_draft = next(
            (d for d in session.query(Draft).filter_by(case_id=case1.id, type="appeal").all()),
            None,
        )
        if appeal_draft:
            review = Review(
                draft_id=appeal_draft.id,
                tenant_id=practice.id,
                reviewer="demo-reviewer",
                decision="approved",
                edits_diff=None,
                timestamp=now - timedelta(days=21),
            )
            session.add(review)

        ev = case1.transition(CaseState.submitted, actor="demo-reviewer",
                              action_note="review:approved")
        session.add(ev)
        session.flush()

        ev = case1.transition(CaseState.pending_payer, actor="system",
                              action_note="submitted to Aetna portal")
        session.add(ev)
        session.flush()

        ev = case1.transition(CaseState.paid, actor="system",
                              action_note="payment received from Aetna")
        session.add(ev)
        session.flush()

        paid_date = now - timedelta(days=7)
        outcome = Outcome(
            case_id=case1.id,
            tenant_id=practice.id,
            result="paid",
            amount_recovered=185.00,
            paid_date=paid_date,
            notes="Aetna reversed denial after appeal. Full amount paid.",
            verified=True,
            verification_method=VerificationMethod.clinic_confirmation.value,
            verified_at=now - timedelta(days=6),
            verified_by="demo-reviewer",
            billable_amount=Decimal("40.70"),  # 185 * 0.22
        )
        session.add(outcome)
        session.flush()

        # Monthly statement for last month
        last_month_start = date(today.year, today.month - 1 if today.month > 1 else 12, 1)
        if today.month == 1:
            last_month_start = date(today.year - 1, 12, 1)
        last_month_end = date(today.year, today.month, 1) - timedelta(days=1)

        line_items = json.dumps([{
            "case_id": case1.id,
            "patient_ref": "PT-LAK-001",
            "amount_recovered": 185.00,
            "fee": 40.70,
            "rate": 0.22,
            "aged": False,
        }])
        statement = Statement(
            practice_id=practice.id,
            period_start=last_month_start,
            period_end=last_month_end,
            total_recovered=Decimal("185.00"),
            fee_amount=Decimal("40.70"),
            status=StatementStatus.sent.value,
            line_items=line_items,
            generated_at=now - timedelta(days=5),
            sent_at=now - timedelta(days=5),
        )
        session.add(statement)
        session.commit()

        # Capture IDs before the session closes (objects become detached after)
        practice_id = practice.id

    # ------------------------------------------------------------------
    # Summary + tokens
    # ------------------------------------------------------------------
    clinic_token = create_dev_token(
        user_id="demo-clinic-admin",
        email="billing@lakesidefp.com",
        tenant_id=practice_id,
        role=Role.clinic_admin,
    )
    ops_token = create_dev_token(
        user_id="demo-ops-admin",
        email="ops@denialdesk.local",
        tenant_id=None,
        role=Role.ops_admin,
    )

    declined_refs = [c[0] for c in _DEMO_CASES if c[8]]
    winnable_refs = [c[0] for c in _DEMO_CASES if not c[8] and c[0] != "PT-LAK-001"]

    print("\n=== Demo seeded ===")
    print(f"Practice : Lakeside Family Practice (id={practice_id})")
    print(f"Cases    : {len(_DEMO_CASES)} total")
    print(f"  Declined ({len(declined_refs)}) : {', '.join(declined_refs)}")
    print(f"  Awaiting review ({len(winnable_refs)}) : {', '.join(winnable_refs)}")
    print(f"  Paid (1)         : PT-LAK-001 ($185.00 recovered)")
    print()
    print("Dev tokens (valid 8 hours) — paste these into the login form:")
    print(f"  Clinic admin : {clinic_token}")
    print(f"  Ops admin    : {ops_token}")
    print()
    print("Run the app:")
    print("  uvicorn denialdesk.api.main:app --reload &")
    print("  cd frontend && npm run dev")
    print("Then open: http://localhost:5173")
    print()
    print("Or use: make demo  (resets DB + seeds + prints tokens)")


def main() -> None:
    Path("data").mkdir(exist_ok=True)

    # Remove existing DB so seed is idempotent (reset_demo.sh also does this)
    db_file = Path(DB_PATH)
    if db_file.exists():
        db_file.unlink()
        print(f"[seed_demo] Removed existing {DB_PATH}")

    seed(DB_PATH)

    # Write .env.dev so the API picks up the right DB
    env_dev = Path(".env.dev")
    env_dev.write_text(f"DATABASE_URL=sqlite:///{DB_PATH}\n")
    print(f"[seed_demo] Wrote {env_dev}")


if __name__ == "__main__":
    main()
