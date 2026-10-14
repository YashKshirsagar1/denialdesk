"""Integration tests for OutcomeProcessor using in-memory SQLite."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

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
from denialdesk.learning.outcome_processor import OutcomeInput, OutcomeProcessor, OutcomeResult
from denialdesk.repositories.case_repository import CaseRepository
from denialdesk.repositories.playbook_repository import PlaybookRepository


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sess = AsyncSession(engine, expire_on_commit=False)
    try:
        yield sess
    finally:
        await sess.close()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def _seed_submitted_case(session: AsyncSession) -> Case:
    """Create a case all the way to submitted state."""
    practice = Practice(name="Test Practice", specialty="Internal Medicine")
    session.add(practice)
    await session.flush()

    batch = Batch(practice_id=practice.id, source_files="test.csv")
    session.add(batch)
    await session.flush()

    case = Case(
        batch_id=batch.id,
        payer="Aetna Health Inc",
        patient_ref="PT-001",
        cpt_hcpcs="99213",
        icd10="I10",
        billed_amt=500.0,
        carc="16",
        state=CaseState.ingested,
    )
    session.add(case)
    await session.flush()

    # Walk through all required transitions to reach submitted
    for target in [
        CaseState.diagnosed,
        CaseState.approved,
        CaseState.drafted,
        CaseState.awaiting_human_review,
        CaseState.submitted,
    ]:
        event = case.transition(target, actor="test")
        session.add(event)
        await session.flush()

    return case


async def _add_draft(session: AsyncSession, case: Case) -> Draft:
    draft = Draft(
        case_id=case.id,
        type="appeal",
        content="Appeal letter body content here.",
        attachments='["clinical_notes", "physician_letter"]',
        version=1,
    )
    session.add(draft)
    await session.flush()
    return draft


async def test_record_paid_outcome_transitions_to_paid(session: AsyncSession):
    case = await _seed_submitted_case(session)
    processor = OutcomeProcessor(session)
    outcome, updated_case = await processor.record_outcome(
        case.id,
        OutcomeInput(result=OutcomeResult.paid, amount_recovered=Decimal("450.00"), paid_date=None),
    )
    assert updated_case.state == CaseState.paid


async def test_record_denied_outcome_transitions_to_re_denied(session: AsyncSession):
    case = await _seed_submitted_case(session)
    processor = OutcomeProcessor(session)
    _, updated_case = await processor.record_outcome(
        case.id,
        OutcomeInput(result=OutcomeResult.denied, amount_recovered=Decimal("0"), paid_date=None),
    )
    assert updated_case.state == CaseState.re_denied


async def test_record_outcome_creates_outcome_row(session: AsyncSession):
    case = await _seed_submitted_case(session)
    processor = OutcomeProcessor(session)
    outcome, _ = await processor.record_outcome(
        case.id,
        OutcomeInput(result=OutcomeResult.paid, amount_recovered=Decimal("300.00"), paid_date=None),
    )
    assert outcome.id is not None
    assert outcome.result == "paid"
    assert outcome.amount_recovered == 300.0


async def test_paid_outcome_increments_playbook_attempts(session: AsyncSession):
    case = await _seed_submitted_case(session)
    processor = OutcomeProcessor(session)
    await processor.record_outcome(
        case.id,
        OutcomeInput(result=OutcomeResult.paid, amount_recovered=Decimal("300"), paid_date=None),
    )
    repo = PlaybookRepository(session)
    entry = await repo.get_strategy("Aetna Health Inc", "16", "unknown")
    assert entry is not None
    assert entry.attempt_count == 1


async def test_paid_outcome_increments_playbook_wins(session: AsyncSession):
    case = await _seed_submitted_case(session)
    processor = OutcomeProcessor(session)
    await processor.record_outcome(
        case.id,
        OutcomeInput(result=OutcomeResult.paid, amount_recovered=Decimal("300"), paid_date=None),
    )
    repo = PlaybookRepository(session)
    entry = await repo.get_strategy("Aetna Health Inc", "16", "unknown")
    assert entry is not None
    assert entry.success_count == 1


async def test_denied_outcome_no_playbook_win(session: AsyncSession):
    case = await _seed_submitted_case(session)
    processor = OutcomeProcessor(session)
    await processor.record_outcome(
        case.id,
        OutcomeInput(result=OutcomeResult.denied, amount_recovered=Decimal("0"), paid_date=None),
    )
    repo = PlaybookRepository(session)
    entry = await repo.get_strategy("Aetna Health Inc", "16", "unknown")
    assert entry is not None
    assert entry.attempt_count == 1
    assert entry.success_count == 0


async def test_paid_updates_winning_strategy(session: AsyncSession):
    case = await _seed_submitted_case(session)
    await _add_draft(session, case)
    processor = OutcomeProcessor(session)
    await processor.record_outcome(
        case.id,
        OutcomeInput(result=OutcomeResult.paid, amount_recovered=Decimal("300"), paid_date=None),
    )
    repo = PlaybookRepository(session)
    entry = await repo.get_strategy("Aetna Health Inc", "16", "unknown")
    assert entry is not None
    assert entry.winning_strategy  # non-empty


async def test_duplicate_outcome_raises_value_error(session: AsyncSession):
    case = await _seed_submitted_case(session)
    processor = OutcomeProcessor(session)
    await processor.record_outcome(
        case.id,
        OutcomeInput(result=OutcomeResult.paid, amount_recovered=Decimal("300"), paid_date=None),
    )
    with pytest.raises(ValueError, match="already recorded"):
        await processor.record_outcome(
            case.id,
            OutcomeInput(result=OutcomeResult.paid, amount_recovered=Decimal("300"), paid_date=None),
        )
