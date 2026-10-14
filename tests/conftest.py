"""Shared pytest fixtures for API tests."""
import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from denialdesk.api.main import app
from denialdesk.api import deps
from denialdesk.models.case import AuditEvent, Base, Batch, Case, CaseState, Diagnosis, Draft, Practice


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite session with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession):
    """AsyncClient with get_session overridden to use the test SQLite session."""

    async def override_get_session():
        yield db_session

    app.dependency_overrides[deps.get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def seed_case(session: AsyncSession, state: CaseState = CaseState.ingested) -> Case:
    practice = Practice(name="Test Practice", specialty="Internal Medicine")
    session.add(practice)
    await session.flush()

    batch = Batch(practice_id=practice.id, uploaded_at=datetime.now(timezone.utc), source_files="test")
    session.add(batch)
    await session.flush()

    case = Case(
        batch_id=batch.id,
        payer="Aetna Health Inc",
        patient_ref="PT-TEST-001",
        cpt_hcpcs="99213",
        icd10="I10",
        billed_amt=500.0,
        allowed_amt=350.0,
        carc="16",
        rarc="MA01",
        denial_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        state=CaseState.ingested,
    )
    session.add(case)
    await session.flush()

    transitions = {
        CaseState.ingested: [],
        CaseState.diagnosed: [CaseState.diagnosed],
        CaseState.approved: [CaseState.diagnosed, CaseState.approved],
        CaseState.drafted: [CaseState.diagnosed, CaseState.approved, CaseState.drafted],
        CaseState.awaiting_human_review: [
            CaseState.diagnosed, CaseState.approved, CaseState.drafted, CaseState.awaiting_human_review
        ],
    }

    for target in transitions.get(state, []):
        event = case.transition(target, actor="test")
        session.add(event)
        await session.flush()

    return case


async def add_diagnosis(session: AsyncSession, case: Case) -> Diagnosis:
    diag = Diagnosis(
        case_id=case.id,
        root_cause="missing_info",
        winnability_score=0.7,
        expected_value=350.0,
        rationale="Test rationale",
        model_version="rule_v1",
    )
    session.add(diag)
    await session.flush()
    return diag


async def add_draft(session: AsyncSession, case: Case, content: str = "Appeal letter content", draft_type: str = "appeal") -> Draft:
    draft = Draft(
        case_id=case.id,
        type=draft_type,
        content=content,
        attachments=json.dumps(["clinical_notes"]),
        version=1,
    )
    session.add(draft)
    await session.flush()
    return draft
