"""
Synthetic denial data generator. Produces realistic fake data — no real PHI.
Usage: python scripts/generate_synthetic.py --count 20 --seed 42 --output data/
"""
import argparse
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Reference tables
# ---------------------------------------------------------------------------

CARC_CODES = {
    "4": "The service/supply is not covered by the plan",
    "11": "The diagnosis is inconsistent with the procedure",
    "16": "Claim lacks information needed for adjudication",
    "18": "Duplicate claim/service",
    "22": "This care may be covered by another payer",
    "29": "The time limit for filing has expired",
    "45": "Charges exceed your contracted/legislated fee arrangement",
    "50": "These are non-covered services because this is not deemed a medical necessity",
    "97": "The benefit for this service is included in the payment/allowance for another service",
    "167": "This does not meet the definition of a covered benefit",
}

RARC_CODES = {
    "MA01": "Alert: If you do not agree with what we approved for these services, you may appeal our decision.",
    "MA04": "Secondary payment cannot be considered without the identity of or payment information from the primary payer.",
    "N30": "Patient ineligible for this service.",
    "N115": "This decision was based on a Local Coverage Determination (LCD).",
    "N432": "Adjustment based on a Recovery Audit.",
}

SPECIALTIES = [
    "Internal Medicine",
    "Cardiology",
    "Orthopedics",
    "Dermatology",
    "Urgent Care",
]

CPT_BY_SPECIALTY = {
    "Internal Medicine": ["99213", "99214", "99215", "93000"],
    "Cardiology": ["93306", "93000", "99214", "33206"],
    "Orthopedics": ["27447", "29881", "99213", "20610"],
    "Dermatology": ["11102", "17000", "99213", "17110"],
    "Urgent Care": ["99213", "99214", "99283", "71046"],
}

ICD10_BY_SPECIALTY = {
    "Internal Medicine": ["Z00.00", "I10", "E11.9", "J06.9"],
    "Cardiology": ["I25.10", "I48.91", "I50.9", "Z95.1"],
    "Orthopedics": ["M17.11", "M23.200", "M79.3", "S82.001A"],
    "Dermatology": ["L70.0", "L57.0", "D22.9", "L82.1"],
    "Urgent Care": ["J06.9", "R05.9", "N39.0", "S93.401A"],
}

PRACTICES = [
    {"name": "Riverside Internal Medicine", "specialty": "Internal Medicine", "contact": "Dr. Amelia Torres | (555) 201-4400"},
    {"name": "Summit Cardiology Group", "specialty": "Cardiology", "contact": "Dr. Marcus Webb | (555) 302-8812"},
    {"name": "Pinecrest Orthopedic Associates", "specialty": "Orthopedics", "contact": "Dr. Sandra Nguyen | (555) 403-7710"},
    {"name": "Clearwater Dermatology Center", "specialty": "Dermatology", "contact": "Dr. Ethan Patel | (555) 504-3322"},
    {"name": "Lakeside Urgent Care", "specialty": "Urgent Care", "contact": "Dr. Julia Kim | (555) 605-9988"},
]

PAYERS = [
    "BlueCross BlueShield of California",
    "Aetna Health Inc",
    "UnitedHealthcare",
    "Cigna Health",
    "Humana Inc",
]

ROOT_CAUSE_MAP = {
    "4": "not_covered",
    "11": "coding_error",
    "16": "missing_info",
    "18": "duplicate",
    "22": "other_payer_primary",
    "29": "timely_filing",
    "45": "fee_schedule",
    "50": "medical_necessity",
    "97": "bundling_ncci",
    "167": "not_covered",
}

PLAYBOOK_STRATEGIES = {
    "not_covered": (
        "Submit a formal written appeal citing the patient's Evidence of Coverage document, "
        "specifically the benefits summary for the relevant service category. Attach a Letter of Medical Necessity "
        "signed by the treating physician. Reference any applicable state mandate if the service is mandated coverage."
    ),
    "coding_error": (
        "Submit a corrected claim (CMS-1500 box 22 with resubmission code 7) with the corrected CPT/ICD-10 pair. "
        "Include a brief cover letter explaining the correction and confirming the original service date. "
        "Attach the operative note or visit note that documents the performed service."
    ),
    "missing_info": (
        "Identify the specific missing element from the RARC code and resubmit with all required attachments. "
        "Common additions: prior auth number, referral number, NPI, taxonomy code, or place of service code. "
        "Call payer to confirm exact missing field before resubmission."
    ),
    "timely_filing": (
        "If within the appeal window, submit proof of timely filing: the original submission confirmation, "
        "clearinghouse acceptance report, or certified mail receipt. Cite the payer's own policy on timely filing "
        "exceptions for provider-side system errors."
    ),
    "medical_necessity": (
        "Draft a detailed Letter of Medical Necessity from the treating provider citing clinical guidelines (e.g., "
        "CMS LCD, AHA, ACS) that support the service. Include relevant lab results, imaging reports, and prior "
        "treatment history. Reference the specific ICD-10 diagnosis and its clinical severity."
    ),
    "bundling_ncci": (
        "Review NCCI edits to determine if a modifier (25, 59, XE, XS, XP, XU) is appropriate. "
        "If distinct services were performed, append the correct modifier and resubmit with documentation "
        "confirming separate and distinct nature of each service."
    ),
    "duplicate": (
        "Pull the original claim's trace number and compare against the duplicate flag. "
        "If the services were legitimately separate encounters, resubmit with a cover letter "
        "and separate visit documentation (distinct dates, separate progress notes)."
    ),
    "fee_schedule": (
        "Submit an appeal citing the contracted rate from the current payer contract. "
        "If no contract exists, reference the Medicare fee schedule as a benchmark. "
        "Attach the relevant contract page or rate sheet."
    ),
    "other_payer_primary": (
        "Obtain the EOB from the primary payer and submit as secondary. "
        "Ensure the CMS-1500 boxes 9a–9d are complete with the primary payer information. "
        "Include coordination of benefits documentation."
    ),
}

REQUIRED_DOCS_MAP = {
    "not_covered": ["Letter of Medical Necessity", "Evidence of Coverage excerpt", "Clinical notes"],
    "coding_error": ["Corrected CMS-1500", "Operative/visit note", "Correction cover letter"],
    "missing_info": ["Resubmitted CMS-1500 with corrections", "Prior auth documentation", "Referral if applicable"],
    "timely_filing": ["Original submission confirmation", "Clearinghouse acceptance report", "Appeal letter"],
    "medical_necessity": ["Letter of Medical Necessity", "Lab/imaging reports", "Clinical guidelines citation"],
    "bundling_ncci": ["Modified CMS-1500 with modifier", "Separate service documentation", "Progress notes"],
    "duplicate": ["Original claim trace number", "Separate encounter documentation", "Cover letter"],
    "fee_schedule": ["Contract rate sheet", "Medicare fee schedule reference", "Appeal letter"],
    "other_payer_primary": ["Primary EOB", "Completed CMS-1500 boxes 9a-9d", "COB documentation"],
}


# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------

def compute_winnability(carc: str, filing_deadline: datetime) -> float:
    score = 0.5
    now = datetime.now(timezone.utc)

    if carc == "29":
        if filing_deadline < now:
            score -= 0.4
        else:
            score += 0.1
    elif carc in ("4", "167"):
        score -= 0.3
    elif carc == "16":
        score += 0.2
    elif carc == "50":
        score += 0.1
    elif carc == "11":
        score += 0.15

    return max(0.05, min(0.95, score))


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate_cases(count: int) -> list[dict]:
    today = datetime.now(timezone.utc)
    cases = []

    carc_list = list(CARC_CODES.keys())
    rarc_list = list(RARC_CODES.keys())

    for i in range(count):
        practice = random.choice(PRACTICES)
        specialty = practice["specialty"]
        payer = random.choice(PAYERS)
        carc = random.choice(carc_list)
        rarc = random.choice(rarc_list)
        cpt = random.choice(CPT_BY_SPECIALTY[specialty])
        icd10 = random.choice(ICD10_BY_SPECIALTY[specialty])

        billed_amt = round(random.uniform(150, 4500), 2)

        if carc in ("29", "4", "167"):
            allowed_amt = 0.0
        else:
            allowed_amt = round(billed_amt * random.uniform(0.60, 0.85), 2)

        denial_days_ago = random.randint(1, 180)
        denial_date = today - timedelta(days=denial_days_ago)
        filing_deadline = denial_date + timedelta(days=90)

        winnability_score = compute_winnability(carc, filing_deadline)
        expected_value = round(allowed_amt * winnability_score, 2)
        root_cause = ROOT_CAUSE_MAP.get(carc, "other")

        dos = denial_date - timedelta(days=random.randint(5, 60))
        patient_ref = f"PT-SYNTH-{uuid.uuid4().hex[:8].upper()}"

        case = {
            "id": f"CASE-{i+1:04d}",
            "practice": practice,
            "payer": payer,
            "patient_ref": patient_ref,
            "dos": dos.isoformat(),
            "cpt_hcpcs": cpt,
            "icd10": icd10,
            "billed_amt": billed_amt,
            "allowed_amt": allowed_amt,
            "carc": carc,
            "carc_description": CARC_CODES[carc],
            "rarc": rarc,
            "rarc_description": RARC_CODES[rarc],
            "denial_date": denial_date.isoformat(),
            "filing_deadline": filing_deadline.isoformat(),
            "state": "ingested",
            "diagnosis": {
                "root_cause": root_cause,
                "winnability_score": winnability_score,
                "expected_value": expected_value,
                "rationale": (
                    f"CARC {carc}: {CARC_CODES[carc]}. "
                    f"Score {winnability_score:.2f} based on denial type and filing deadline status."
                ),
                "model_version": "rule_v1",
            },
        }
        cases.append(case)

    return cases


def generate_playbook() -> list[dict]:
    entries = []
    carc_list = list(CARC_CODES.keys())
    payers_subset = PAYERS

    seen = set()
    for payer in payers_subset:
        for carc in random.sample(carc_list, k=min(4, len(carc_list))):
            specialty = random.choice(SPECIALTIES)
            key = (payer, carc, specialty)
            if key in seen:
                continue
            seen.add(key)
            root_cause = ROOT_CAUSE_MAP.get(carc, "other")
            strategy = PLAYBOOK_STRATEGIES.get(root_cause, "Review payer guidelines and submit appeal with supporting documentation.")
            required_docs = REQUIRED_DOCS_MAP.get(root_cause, ["Appeal letter", "Clinical notes"])
            success_count = random.randint(0, 30)
            attempt_count = success_count + random.randint(0, 20)
            entries.append({
                "payer": payer,
                "reason_code": carc,
                "carc_description": CARC_CODES[carc],
                "specialty": specialty,
                "winning_strategy": strategy,
                "required_docs": required_docs,
                "success_count": success_count,
                "attempt_count": attempt_count,
            })
            if len(entries) >= 20:
                return entries
    return entries


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic denial data")
    parser.add_argument("--count", type=int, default=20, help="Number of cases to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output", type=str, default="data/", help="Output directory")
    args = parser.parse_args()

    random.seed(args.seed)
    os.makedirs(args.output, exist_ok=True)

    cases = generate_cases(args.count)
    playbook = generate_playbook()

    generated_at = datetime.now(timezone.utc).isoformat()

    cases_path = os.path.join(args.output, "synthetic_cases.json")
    with open(cases_path, "w") as f:
        json.dump({"generated_at": generated_at, "count": len(cases), "cases": cases}, f, indent=2)

    playbook_path = os.path.join(args.output, "synthetic_payer_playbook.json")
    with open(playbook_path, "w") as f:
        json.dump({"generated_at": generated_at, "count": len(playbook), "playbook": playbook}, f, indent=2)

    # Summary table
    print(f"\nGenerated {len(cases)} cases → {cases_path}")
    print(f"Generated {len(playbook)} playbook entries → {playbook_path}\n")

    carc_counts: dict[str, int] = {}
    winnable = 0
    total_billed = 0.0

    for c in cases:
        carc = c["carc"]
        carc_counts[carc] = carc_counts.get(carc, 0) + 1
        total_billed += c["billed_amt"]
        if c["diagnosis"]["winnability_score"] >= 0.5:
            winnable += 1

    print(f"{'CARC':<8} {'Count':<8} Description")
    print("-" * 60)
    for carc, cnt in sorted(carc_counts.items(), key=lambda x: -x[1]):
        print(f"{carc:<8} {cnt:<8} {CARC_CODES[carc][:45]}")

    print(f"\nTotal billed:       ${total_billed:,.2f}")
    print(f"Winnable (>=0.5):   {winnable}/{len(cases)} ({100*winnable/len(cases):.0f}%)")
    print(f"Seed used:          {args.seed}\n")


if __name__ == "__main__":
    main()
