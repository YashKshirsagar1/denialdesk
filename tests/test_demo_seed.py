"""Smoke tests: seed_demo creates the expected practice, cases, and states."""
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent))

from denialdesk.models.case import (
    Base,
    Batch,
    Case,
    CaseState,
    Diagnosis,
    Outcome,
    Practice,
    Statement,
)

# Import the seed function directly (not main()) so we can target a temp DB
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "seed_demo", Path(__file__).parent.parent / "scripts" / "seed_demo.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
seed = _mod.seed


@pytest.fixture(scope="module")
def seeded_session(tmp_path_factory):
    """Run seed() once into a temp SQLite DB; yield a Session for inspection."""
    db_path = str(tmp_path_factory.mktemp("demo") / "demo_test.db")
    seed(db_path)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_demo_practice_created(seeded_session):
    practice = seeded_session.execute(
        select(Practice).where(Practice.name == "Lakeside Family Practice")
    ).scalar_one_or_none()
    assert practice is not None
    assert practice.onboarding_status == "active"
    assert practice.baa_signed_at is not None
    assert practice.service_agreement_signed_at is not None
    assert practice.npi == "1234567890"


def test_demo_10_cases_created(seeded_session):
    practice = seeded_session.execute(
        select(Practice).where(Practice.name == "Lakeside Family Practice")
    ).scalar_one()
    batch = seeded_session.execute(
        select(Batch).where(Batch.practice_id == practice.id)
    ).scalar_one()
    cases = seeded_session.execute(
        select(Case).where(Case.batch_id == batch.id)
    ).scalars().all()
    assert len(cases) == 10


def test_demo_3_declined(seeded_session):
    practice = seeded_session.execute(
        select(Practice).where(Practice.name == "Lakeside Family Practice")
    ).scalar_one()
    declined = seeded_session.execute(
        select(Case).where(
            Case.tenant_id == practice.id,
            Case.state == CaseState.declined,
        )
    ).scalars().all()
    assert len(declined) == 3
    refs = {c.patient_ref for c in declined}
    assert refs == {"PT-LAK-007", "PT-LAK-008", "PT-LAK-009"}


def test_demo_6_awaiting_review_or_later(seeded_session):
    practice = seeded_session.execute(
        select(Practice).where(Practice.name == "Lakeside Family Practice")
    ).scalar_one()
    active_states = [
        CaseState.awaiting_human_review,
        CaseState.submitted,
        CaseState.pending_payer,
        CaseState.paid,
    ]
    cases = seeded_session.execute(
        select(Case).where(
            Case.tenant_id == practice.id,
            Case.state.in_(active_states),
        )
    ).scalars().all()
    assert len(cases) >= 6


def test_demo_paid_outcome_exists(seeded_session):
    practice = seeded_session.execute(
        select(Practice).where(Practice.name == "Lakeside Family Practice")
    ).scalar_one()
    paid_case = seeded_session.execute(
        select(Case).where(
            Case.tenant_id == practice.id,
            Case.patient_ref == "PT-LAK-001",
        )
    ).scalar_one()
    assert paid_case.state == CaseState.paid

    outcome = seeded_session.execute(
        select(Outcome).where(Outcome.case_id == paid_case.id)
    ).scalar_one_or_none()
    assert outcome is not None
    assert outcome.result == "paid"
    assert float(outcome.amount_recovered) == 185.00
    assert outcome.verified is True
    assert float(outcome.billable_amount) == pytest.approx(40.70, abs=0.01)


def test_demo_statement_created(seeded_session):
    practice = seeded_session.execute(
        select(Practice).where(Practice.name == "Lakeside Family Practice")
    ).scalar_one()
    statement = seeded_session.execute(
        select(Statement).where(Statement.practice_id == practice.id)
    ).scalar_one_or_none()
    assert statement is not None
    assert float(statement.total_recovered) == pytest.approx(185.00, abs=0.01)
    assert float(statement.fee_amount) == pytest.approx(40.70, abs=0.01)
    assert statement.status == "sent"


def test_demo_declined_have_low_scores(seeded_session):
    practice = seeded_session.execute(
        select(Practice).where(Practice.name == "Lakeside Family Practice")
    ).scalar_one()
    declined_cases = seeded_session.execute(
        select(Case).where(
            Case.tenant_id == practice.id,
            Case.state == CaseState.declined,
        )
    ).scalars().all()
    for case in declined_cases:
        diag = seeded_session.execute(
            select(Diagnosis).where(Diagnosis.case_id == case.id)
        ).scalar_one_or_none()
        assert diag is not None
        assert diag.winnability_score < 0.20, (
            f"{case.patient_ref} should have score < 0.20, got {diag.winnability_score}"
        )


def test_demo_winnable_have_appeal_drafts(seeded_session):
    from denialdesk.models.case import Draft
    practice = seeded_session.execute(
        select(Practice).where(Practice.name == "Lakeside Family Practice")
    ).scalar_one()
    awaiting = seeded_session.execute(
        select(Case).where(
            Case.tenant_id == practice.id,
            Case.state == CaseState.awaiting_human_review,
        )
    ).scalars().all()
    assert len(awaiting) >= 5
    for case in awaiting:
        drafts = seeded_session.execute(
            select(Draft).where(Draft.case_id == case.id, Draft.type == "appeal")
        ).scalars().all()
        assert len(drafts) >= 1, f"{case.patient_ref} missing appeal draft"
