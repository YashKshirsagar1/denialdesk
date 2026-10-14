"""API integration tests using in-memory SQLite + ASGI test client."""
import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from denialdesk.api.main import app
from denialdesk.api import deps
from denialdesk.models.case import AuditEvent, Base, Batch, Case, CaseState, Diagnosis, Draft, Practice


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_case(session: AsyncSession, state: CaseState = CaseState.ingested) -> Case:
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


async def _add_diagnosis(session: AsyncSession, case: Case) -> Diagnosis:
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


async def _add_draft(session: AsyncSession, case: Case, content: str = "Appeal letter content") -> Draft:
    draft = Draft(
        case_id=case.id,
        type="appeal",
        content=content,
        attachments=json.dumps(["clinical_notes"]),
        version=1,
    )
    session.add(draft)
    await session.flush()
    return draft


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_health(api_client: AsyncClient):
    res = await api_client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


async def test_queue_empty(api_client: AsyncClient):
    res = await api_client.get("/api/queue")
    assert res.status_code == 200
    data = res.json()
    assert data["awaiting_review"] == 0
    assert data["drafted"] == 0
    assert data["submitted"] == 0
    assert data["paid"] == 0
    assert data["declined"] == 0
    assert data["total_active"] == 0


async def test_queue_cases_empty(api_client: AsyncClient):
    res = await api_client.get("/api/queue/cases")
    assert res.status_code == 200
    assert res.json() == []


async def test_create_and_fetch_case(api_client: AsyncClient, db_session: AsyncSession):
    case = await _seed_case(db_session, CaseState.ingested)
    await db_session.commit()

    res = await api_client.get(f"/api/cases/{case.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["payer"] == "Aetna Health Inc"
    assert data["carc"] == "16"
    assert data["state"] == "ingested"


async def test_queue_counts_awaiting_review(api_client: AsyncClient, db_session: AsyncSession):
    case = await _seed_case(db_session, CaseState.awaiting_human_review)
    await db_session.commit()

    res = await api_client.get("/api/queue")
    assert res.status_code == 200
    data = res.json()
    assert data["awaiting_review"] == 1


async def test_review_approve(api_client: AsyncClient, db_session: AsyncSession):
    case = await _seed_case(db_session, CaseState.awaiting_human_review)
    await _add_draft(db_session, case)
    await db_session.commit()

    res = await api_client.post(
        f"/api/cases/{case.id}/review",
        json={"decision": "approve", "reviewer": "dr_smith"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["new_state"] == "submitted"
    assert data["case_id"] == case.id


async def test_review_reject(api_client: AsyncClient, db_session: AsyncSession):
    case = await _seed_case(db_session, CaseState.awaiting_human_review)
    await _add_draft(db_session, case)
    await db_session.commit()

    res = await api_client.post(
        f"/api/cases/{case.id}/review",
        json={"decision": "reject", "reviewer": "dr_smith"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["new_state"] == "drafted"


async def test_review_edit(api_client: AsyncClient, db_session: AsyncSession):
    case = await _seed_case(db_session, CaseState.awaiting_human_review)
    draft = await _add_draft(db_session, case, content="Original appeal content here.")
    await db_session.commit()

    res = await api_client.post(
        f"/api/cases/{case.id}/review",
        json={
            "decision": "edit",
            "reviewer": "dr_smith",
            "edits": "Edited appeal content here with corrections.",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["new_state"] == "submitted"
    # new draft should have a different id from original
    assert data["draft_id"] != draft.id


async def test_case_not_found(api_client: AsyncClient):
    res = await api_client.get("/api/cases/99999")
    assert res.status_code == 404


async def test_get_case_with_diagnosis(api_client: AsyncClient, db_session: AsyncSession):
    case = await _seed_case(db_session, CaseState.diagnosed)
    await _add_diagnosis(db_session, case)
    await db_session.commit()

    res = await api_client.get(f"/api/cases/{case.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["diagnosis"] is not None
    assert data["diagnosis"]["root_cause"] == "missing_info"
    assert data["diagnosis"]["winnability_score"] == pytest.approx(0.7)
