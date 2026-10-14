"""Seed a SQLite dev DB with synthetic cases for UI testing."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make the package importable when run from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from denialdesk.models.case import (
    AuditEvent,
    Base,
    Batch,
    Case,
    CaseState,
    Diagnosis,
    Draft,
    Outcome,
    Practice,
)


def _parse_date(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _rule_based_score(carc: str, filing_deadline: datetime | None) -> tuple[str, float]:
    from denialdesk.agents.diagnosis_agent import CARC_ROOT_CAUSE, RootCause, _CARC_SCORE_DELTA

    root_cause = CARC_ROOT_CAUSE.get(carc, RootCause.other).value
    score = 0.5
    delta = _CARC_SCORE_DELTA.get(carc, 0.0)
    score += delta

    if carc == "29" and filing_deadline:
        now = datetime.now(timezone.utc)
        if filing_deadline < now:
            score -= 0.4
        else:
            score += 0.1

    score = max(0.05, min(0.95, score))
    return root_cause, round(score, 2)


def _mock_appeal(case_data: dict, practice_name: str) -> str:
    payer = case_data.get("payer", "Unknown Payer")
    claim_num = case_data.get("patient_ref", "Unknown")
    carc = case_data.get("carc", "")
    carc_desc = case_data.get("carc_description", f"CARC {carc}")
    return (
        f"RE: Appeal for Claim Number {claim_num}\n\n"
        f"Dear {payer} Appeals Department,\n\n"
        f"We are writing to formally appeal the denial of the above-referenced claim. "
        f"The claim was denied with reason code CARC {carc}: {carc_desc}.\n\n"
        f"We respectfully request reconsideration and full payment. "
        f"Supporting documentation is enclosed.\n\n"
        f"Sincerely,\n{practice_name} Billing Department"
    )


def seed(db_path: str, count: int) -> None:
    cases_file = Path(__file__).parent.parent / "data" / "synthetic_cases.json"
    if not cases_file.exists():
        print(f"ERROR: {cases_file} not found. Run scripts/generate_synthetic.py first.")
        sys.exit(1)

    with open(cases_file) as f:
        data = json.load(f)

    raw_cases = data["cases"][:count]

    url = f"sqlite:///{db_path}"
    engine = create_engine(url, echo=False)
    Base.metadata.create_all(engine)

    practices_map: dict[str, Practice] = {}

    with Session(engine) as session:
        # Create practices
        practice_names = list({c["practice"]["name"] for c in raw_cases})[:5]
        for raw in raw_cases:
            pname = raw["practice"]["name"]
            if pname not in practices_map:
                p = Practice(
                    name=pname,
                    specialty=raw["practice"]["specialty"],
                    contact=raw["practice"].get("contact"),
                )
                session.add(p)
                session.flush()
                practices_map[pname] = p

        states_count: dict[str, int] = {}

        for raw in raw_cases:
            practice = practices_map[raw["practice"]["name"]]

            batch = Batch(
                practice_id=practice.id,
                uploaded_at=datetime.now(timezone.utc),
                source_files="seed_dev_db",
            )
            session.add(batch)
            session.flush()

            filing_deadline = _parse_date(raw["filing_deadline"]) if raw.get("filing_deadline") else None
            carc = raw.get("carc", "")
            root_cause, score = _rule_based_score(carc, filing_deadline)

            case = Case(
                batch_id=batch.id,
                payer=raw["payer"],
                patient_ref=raw["patient_ref"],
                dos=_parse_date(raw["dos"]),
                cpt_hcpcs=raw.get("cpt_hcpcs", ""),
                icd10=raw.get("icd10", ""),
                billed_amt=float(raw.get("billed_amt", 0)),
                allowed_amt=float(raw.get("allowed_amt", 0)),
                carc=carc,
                rarc=raw.get("rarc", ""),
                denial_date=_parse_date(raw["denial_date"]) if raw.get("denial_date") else None,
                filing_deadline=filing_deadline,
                state=CaseState.ingested,
            )
            session.add(case)
            session.flush()

            def _audit(actor: str, action: str):
                e = AuditEvent(
                    case_id=case.id,
                    actor=actor,
                    action=action,
                    timestamp=datetime.now(timezone.utc),
                )
                session.add(e)

            _audit("seed_script", "ingested from seed")

            # Transition: ingested → diagnosed
            event = case.transition(CaseState.diagnosed, actor="diagnosis_agent", action_note=f"root_cause={root_cause}, score={score:.2f}")
            session.add(event)
            session.flush()

            diag = Diagnosis(
                case_id=case.id,
                root_cause=root_cause,
                winnability_score=score,
                expected_value=round(score * float(raw.get("billed_amt", 0)) * 0.75, 2),
                rationale=f"CARC {carc}: {raw.get('carc_description', '')}. Score {score:.2f} based on denial type.",
                model_version="rule_v1",
            )
            session.add(diag)
            session.flush()

            # diagnosed → approved
            event = case.transition(CaseState.approved, actor="coordinator", action_note="auto-approved for drafting")
            session.add(event)
            session.flush()

            # approved → drafted
            appeal_content = _mock_appeal(raw, practice.name)
            draft = Draft(
                case_id=case.id,
                type="appeal",
                content=appeal_content,
                attachments=json.dumps(["clinical_notes", "physician_letter"]),
                version=1,
            )
            session.add(draft)
            event = case.transition(CaseState.drafted, actor="drafting_agent", action_note="drafted appeal")
            session.add(event)
            session.flush()

            # drafted → awaiting_human_review
            event = case.transition(CaseState.awaiting_human_review, actor="coordinator", action_note="ready for review")
            session.add(event)
            session.flush()

            states_count[case.state.value] = states_count.get(case.state.value, 0) + 1

        session.commit()

    # Seed outcomes on some cases — mix of paid, denied, partially_paid
    import random as _rnd
    _rnd.seed(99)

    outcome_plan = (
        [("paid", 800)] * 3
        + [("paid", 1400)] * 2
        + [("paid", 500)] * 1
        + [("partially_paid", 300)] * 2
        + [("partially_paid", 150)] * 1
        + [("denied", 0)] * 4
    )
    # Leave last 2 cases with no outcome (still awaiting_human_review state)
    outcome_plan = outcome_plan[: max(0, len(raw_cases) - 2)]

    with Session(engine) as session:
        all_cases = session.execute(
            __import__("sqlalchemy").text("SELECT id FROM cases ORDER BY id")
        ).fetchall()
        case_ids = [row[0] for row in all_cases]

        outcomes_added = 0
        for i, (result, amount) in enumerate(outcome_plan):
            if i >= len(case_ids):
                break
            cid = case_ids[i]
            case = session.get(Case, cid)
            if case is None:
                continue

            # Advance state to submitted → pending_payer if still in awaiting_human_review
            transitions_needed = []
            if case.state == CaseState.awaiting_human_review:
                transitions_needed = [CaseState.submitted, CaseState.pending_payer]
            elif case.state == CaseState.drafted:
                transitions_needed = [CaseState.awaiting_human_review, CaseState.submitted, CaseState.pending_payer]

            for t in transitions_needed:
                try:
                    ev = case.transition(t, actor="seed_script")
                    session.add(ev)
                    session.flush()
                except ValueError:
                    break

            if case.state != CaseState.pending_payer:
                continue

            paid_dt = datetime.now(timezone.utc) if result != "denied" else None
            outcome = Outcome(
                case_id=cid,
                result=result,
                amount_recovered=float(amount),
                paid_date=paid_dt,
                notes="seeded",
            )
            session.add(outcome)

            if result != "denied":
                try:
                    ev = case.transition(CaseState.paid, actor="seed_script")
                    session.add(ev)
                except ValueError:
                    pass
            else:
                try:
                    ev = case.transition(CaseState.re_denied, actor="seed_script")
                    session.add(ev)
                except ValueError:
                    pass

            session.flush()
            outcomes_added += 1

        session.commit()

    print(f"\nSeeded {len(raw_cases)} cases into {db_path}")
    print(f"{'State':<30} {'Count':>5}")
    print("-" * 37)
    for state, cnt in sorted(states_count.items()):
        print(f"{state:<30} {cnt:>5}")
    print(f"\nOutcomes seeded: {outcomes_added}")
    print(f"\nAPI dev config: DATABASE_URL=sqlite:///{db_path}")


def main():
    parser = argparse.ArgumentParser(description="Seed DenialDesk dev SQLite DB")
    parser.add_argument("--db", default="data/dev.db", help="Path to SQLite DB file")
    parser.add_argument("--count", type=int, default=15, help="Number of cases to seed")
    args = parser.parse_args()

    db_path = args.db
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Remove existing DB for a clean seed
    if Path(db_path).exists():
        Path(db_path).unlink()

    seed(db_path, args.count)

    # Write .env.dev
    env_dev = Path(__file__).parent.parent / ".env.dev"
    env_dev.write_text(f"DATABASE_URL=sqlite:///{db_path}\n")
    print(f"Wrote {env_dev}")


if __name__ == "__main__":
    main()
