"""Tests for the document requests inbox."""
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from denialdesk.api import deps
from denialdesk.api.main import app
from denialdesk.auth.models import Role, UserClaims
from denialdesk.models.case import (
    Base,
    Batch,
    Case,
    CaseState,
    DocumentRequest,
    DocumentRequestStatus,
    Practice,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _make_client(db_session: AsyncSession, user: UserClaims):
    async def _override_session():
        yield db_session

    async def _override_user():
        return user

    app.dependency_overrides[deps.get_session] = _override_session
    app.dependency_overrides[deps.get_current_user] = _override_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_case(session: AsyncSession, tenant_id: int | None = None) -> Case:
    practice = Practice(name="Clinic A", specialty="FM")
    session.add(practice)
    await session.flush()
    batch = Batch(practice_id=practice.id, uploaded_at=datetime.now(timezone.utc), source_files="x")
    session.add(batch)
    await session.flush()
    case = Case(
        batch_id=batch.id,
        tenant_id=tenant_id,
        payer="Aetna",
        cpt_hcpcs="99213",
        billed_amt=500.0,
        carc="16",
        state=CaseState.ingested,
    )
    session.add(case)
    await session.flush()
    return case


async def _seed_doc_request(session: AsyncSession, case_id: int, tenant_id: int | None = None) -> DocumentRequest:
    req = DocumentRequest(
        case_id=case_id,
        tenant_id=tenant_id,
        requested_by="diagnosis_agent",
        document_type="chart_note",
        description="Please upload the chart note.",
        status=DocumentRequestStatus.pending,
        created_at=datetime.now(timezone.utc),
    )
    session.add(req)
    await session.flush()
    return req


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_document_request_requires_reviewer_role(db):
    case = await _seed_case(db, tenant_id=1)
    clinic_user = UserClaims(user_id="u1", email="e@x.com", tenant_id=1, role=Role.clinic_staff)
    async with _make_client(db, clinic_user) as client:
        resp = await client.post(
            f"/api/cases/{case.id}/document-requests",
            json={"document_type": "chart_note", "description": "Upload chart note."},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_document_request_as_reviewer(db):
    case = await _seed_case(db, tenant_id=1)
    reviewer = UserClaims(user_id="r1", email="r@x.com", tenant_id=None, role=Role.reviewer)
    async with _make_client(db, reviewer) as client:
        resp = await client.post(
            f"/api/cases/{case.id}/document-requests",
            json={"document_type": "prior_auth", "description": "Upload prior auth.", "requested_by": "reviewer"},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 201
    data = resp.json()
    assert data["document_type"] == "prior_auth"
    assert data["status"] == "pending"
    assert data["case_id"] == case.id


@pytest.mark.asyncio
async def test_list_requests_scoped_to_tenant(db):
    case1 = await _seed_case(db, tenant_id=1)
    case2 = await _seed_case(db, tenant_id=2)
    req1 = await _seed_doc_request(db, case1.id, tenant_id=1)
    req2 = await _seed_doc_request(db, case2.id, tenant_id=2)

    clinic1 = UserClaims(user_id="c1", email="c1@x.com", tenant_id=1, role=Role.clinic_admin)
    async with _make_client(db, clinic1) as client:
        resp = await client.get("/api/document-requests")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert req1.id in ids
    assert req2.id not in ids


@pytest.mark.asyncio
async def test_ops_sees_all_requests(db):
    case1 = await _seed_case(db, tenant_id=1)
    case2 = await _seed_case(db, tenant_id=2)
    req1 = await _seed_doc_request(db, case1.id, tenant_id=1)
    req2 = await _seed_doc_request(db, case2.id, tenant_id=2)

    ops = UserClaims(user_id="ops", email="ops@x.com", tenant_id=None, role=Role.ops_admin)
    async with _make_client(db, ops) as client:
        resp = await client.get("/api/document-requests")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert req1.id in ids
    assert req2.id in ids


@pytest.mark.asyncio
async def test_fulfill_request_as_clinic_staff(db):
    case = await _seed_case(db, tenant_id=1)
    req = await _seed_doc_request(db, case.id, tenant_id=1)

    clinic = UserClaims(user_id="c1", email="c1@x.com", tenant_id=1, role=Role.clinic_staff)
    async with _make_client(db, clinic) as client:
        resp = await client.post(f"/api/document-requests/{req.id}/fulfill")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "fulfilled"
    assert data["fulfilled_at"] is not None


@pytest.mark.asyncio
async def test_fulfill_requires_clinic_role(db):
    case = await _seed_case(db, tenant_id=1)
    req = await _seed_doc_request(db, case.id, tenant_id=1)

    reviewer = UserClaims(user_id="r1", email="r@x.com", tenant_id=None, role=Role.reviewer)
    async with _make_client(db, reviewer) as client:
        resp = await client.post(f"/api/document-requests/{req.id}/fulfill")
    app.dependency_overrides.clear()

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_document_request_requires_auth(db):
    case = await _seed_case(db)

    # Remove all overrides so no user is injected
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/cases/{case.id}/document-requests",
            json={"document_type": "chart_note", "description": "Upload."},
        )
    assert resp.status_code == 401
