"""Integration tests for the Coordinator — uses in-memory SQLite."""
import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from denialdesk.coordinator import DECLINE_THRESHOLD, Coordinator
from denialdesk.llm.base import LLMMessage, LLMProvider, LLMResponse
from denialdesk.models.case import Base, Batch, Case, CaseState, Practice


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
    await engine.dispose()


@pytest.fixture
async def seeded(session: AsyncSession):
    practice = Practice(name="Test Practice", specialty="Internal Medicine")
    session.add(practice)
    await session.flush()

    batch = Batch(practice_id=practice.id, source_files="test.csv")
    session.add(batch)
    await session.flush()

    now = datetime.now(timezone.utc)
    case = Case(
        batch_id=batch.id,
        payer="Aetna Health Inc",
        patient_ref="PT-001",
        cpt_hcpcs="99213",
        icd10="I10",
        billed_amt=500.0,
        allowed_amt=0.0,
        carc="16",
        rarc="MA01",
        denial_date=now - timedelta(days=30),
        filing_deadline=now + timedelta(days=60),
        state=CaseState.ingested,
    )
    session.add(case)
    await session.flush()
    return practice, batch, case


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

class _MockLLM(LLMProvider):
    def __init__(self, score: float = 0.70, root_cause: str = "missing_info"):
        self._score = score
        self._root_cause = root_cause

    async def complete(self, messages, system=None, max_tokens=2048):
        return LLMResponse(content="Appeal letter content.", input_tokens=10, output_tokens=50, model="mock")

    async def complete_json(self, messages, system=None, max_tokens=2048):
        return {
            "root_cause": self._root_cause,
            "winnability_score": self._score,
            "rationale": "Mock rationale.",
            "expected_value_pct": 0.7,
            "confidence": 0.8,
        }


# ---------------------------------------------------------------------------
# Tests: process_case
# ---------------------------------------------------------------------------

async def test_process_case_approve_and_draft(session, seeded):
    _, _, case = seeded
    llm = _MockLLM(score=0.70)
    coord = Coordinator(session, llm, practice_name="Test Practice")

    result = await coord.process_case(case)

    assert result.error is None
    assert result.final_state == CaseState.awaiting_human_review.value
    await session.refresh(case)
    assert case.state == CaseState.awaiting_human_review


async def test_process_case_auto_decline_low_score(session, seeded):
    _, _, case = seeded
    # Score just below threshold
    llm = _MockLLM(score=DECLINE_THRESHOLD - 0.01)
    coord = Coordinator(session, llm, practice_name="Test Practice")

    result = await coord.process_case(case)

    assert result.error is None
    assert result.final_state == CaseState.declined.value
    await session.refresh(case)
    assert case.state == CaseState.declined


async def test_process_case_at_threshold_not_declined(session, seeded):
    _, _, case = seeded
    # Score exactly at threshold — should NOT be declined
    llm = _MockLLM(score=DECLINE_THRESHOLD)
    coord = Coordinator(session, llm, practice_name="Test Practice")

    result = await coord.process_case(case)

    assert result.final_state != CaseState.declined.value


async def test_process_case_drafts_saved(session, seeded):
    from sqlalchemy import select
    from denialdesk.models.case import Draft

    _, _, case = seeded
    llm = _MockLLM(score=0.75)
    coord = Coordinator(session, llm, practice_name="Test Practice")

    await coord.process_case(case)

    drafts = (await session.execute(select(Draft).where(Draft.case_id == case.id))).scalars().all()
    assert len(drafts) >= 1
    types = {d.type for d in drafts}
    assert "appeal" in types


async def test_process_case_diagnosis_saved(session, seeded):
    from sqlalchemy import select
    from denialdesk.models.case import Diagnosis

    _, _, case = seeded
    llm = _MockLLM(score=0.60)
    coord = Coordinator(session, llm)

    await coord.process_case(case)

    diag = (await session.execute(
        select(Diagnosis).where(Diagnosis.case_id == case.id)
    )).scalar_one_or_none()
    assert diag is not None
    assert diag.winnability_score == pytest.approx(0.60)


# ---------------------------------------------------------------------------
# Tests: process_batch
# ---------------------------------------------------------------------------

async def test_process_batch_counts(session: AsyncSession):
    practice = Practice(name="Batch Practice", specialty="Cardiology")
    session.add(practice)
    await session.flush()

    batch = Batch(practice_id=practice.id, source_files="batch.csv")
    session.add(batch)
    await session.flush()

    now = datetime.now(timezone.utc)
    cases = []
    for i in range(3):
        c = Case(
            batch_id=batch.id,
            payer="UnitedHealthcare",
            patient_ref=f"PT-{i:03d}",
            cpt_hcpcs="99213",
            icd10="I10",
            billed_amt=400.0,
            allowed_amt=0.0,
            carc="16",
            denial_date=now - timedelta(days=10),
            state=CaseState.ingested,
        )
        session.add(c)
        cases.append(c)
    await session.flush()

    llm = _MockLLM(score=0.65)
    coord = Coordinator(session, llm)
    br = await coord.process_batch(batch.id)

    assert br.batch_id == batch.id
    assert br.processed == 3
    assert br.declined == 0
    assert br.awaiting_review == 3
    assert br.errors == []


async def test_process_batch_empty_batch(session: AsyncSession):
    practice = Practice(name="Empty Practice", specialty="General")
    session.add(practice)
    await session.flush()
    batch = Batch(practice_id=practice.id, source_files="empty.csv")
    session.add(batch)
    await session.flush()

    llm = _MockLLM()
    coord = Coordinator(session, llm)
    br = await coord.process_batch(batch.id)

    assert br.processed == 0
    assert br.errors == []


async def test_process_batch_all_declined(session: AsyncSession):
    """All cases below threshold → all declined."""
    practice = Practice(name="Decline Practice", specialty="Orthopedics")
    session.add(practice)
    await session.flush()
    batch = Batch(practice_id=practice.id, source_files="low.csv")
    session.add(batch)
    await session.flush()

    now = datetime.now(timezone.utc)
    for i in range(2):
        c = Case(
            batch_id=batch.id, payer="Aetna", patient_ref=f"PT-LOW-{i}",
            cpt_hcpcs="99213", icd10="I10", billed_amt=500.0, allowed_amt=0.0,
            carc="16", denial_date=now - timedelta(days=5), state=CaseState.ingested,
        )
        session.add(c)
    await session.flush()

    llm = _MockLLM(score=DECLINE_THRESHOLD - 0.01)
    coord = Coordinator(session, llm)
    br = await coord.process_batch(batch.id)

    assert br.processed == 2
    assert br.declined == 2
    assert br.awaiting_review == 0
    assert br.errors == []
