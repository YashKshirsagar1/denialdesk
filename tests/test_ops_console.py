"""Tests for ops console upgrades: deadline view, practice name in queue, specialty in win rates."""
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from denialdesk.api import deps
from denialdesk.api.main import app
from denialdesk.auth.jwt import create_dev_token
from denialdesk.auth.models import Role, UserClaims
from denialdesk.models.case import Base, Batch, Case, CaseState, Outcome, PayerPlaybook, Practice


@pytest_asyncio.fixture
async def ops_client(db_session: AsyncSession):
    """Client with ops_admin auth and test DB."""
    async def _get_session():
        yield db_session

    async def _get_user():
        return UserClaims(user_id="ops", email="ops@test.local", tenant_id=None, role=Role.ops_admin)

    app.dependency_overrides[deps.get_session] = _get_session
    app.dependency_overrides[deps.get_current_user] = _get_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def clinic_client(db_session: AsyncSession):
    """Client with clinic_admin auth (tenant_id=1)."""
    async def _get_session():
        yield db_session

    async def _get_user():
        return UserClaims(user_id="clinic", email="clinic@test.local", tenant_id=1, role=Role.clinic_admin)

    app.dependency_overrides[deps.get_session] = _get_session
    app.dependency_overrides[deps.get_current_user] = _get_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _make_practice(session: AsyncSession, name: str = "Test Practice") -> Practice:
    p = Practice(name=name, specialty="Internal Medicine")
    session.add(p)
    await session.flush()
    return p


async def _make_case(
    session: AsyncSession,
    practice: Practice,
    state: CaseState = CaseState.approved,
    filing_deadline: date | None = None,
) -> Case:
    batch = Batch(practice_id=practice.id, tenant_id=practice.id, uploaded_at=datetime.now(timezone.utc))
    session.add(batch)
    await session.flush()
    deadline_dt = None
    if filing_deadline:
        deadline_dt = datetime.combine(filing_deadline, datetime.min.time()).replace(tzinfo=timezone.utc)
    case = Case(
        batch_id=batch.id,
        tenant_id=practice.id,
        payer="Aetna",
        patient_ref="PT-001",
        cpt_hcpcs="99213",
        billed_amt=500.0,
        carc="16",
        state=state,
        filing_deadline=deadline_dt,
    )
    session.add(case)
    await session.flush()
    return case


# ── Deadline endpoint ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deadlines_requires_ops_role(clinic_client: AsyncClient):
    r = await clinic_client.get("/api/ops/deadlines")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_deadlines_empty(ops_client: AsyncClient):
    r = await ops_client.get("/api/ops/deadlines")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_deadlines_urgency_tiers(ops_client: AsyncClient, db_session: AsyncSession):
    practice = await _make_practice(db_session, "Urgency Clinic")
    today = date.today()
    await _make_case(db_session, practice, filing_deadline=today - timedelta(days=1))   # overdue
    await _make_case(db_session, practice, filing_deadline=today + timedelta(days=2))   # critical
    await _make_case(db_session, practice, filing_deadline=today + timedelta(days=6))   # warning
    await _make_case(db_session, practice, filing_deadline=today + timedelta(days=20))  # ok
    await db_session.commit()

    r = await ops_client.get("/api/ops/deadlines")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 4
    urgencies = [i["urgency"] for i in items]
    assert urgencies[0] == "overdue"
    assert urgencies[1] == "critical"
    assert urgencies[2] == "warning"
    assert urgencies[3] == "ok"


@pytest.mark.asyncio
async def test_deadlines_excludes_closed_cases(ops_client: AsyncClient, db_session: AsyncSession):
    practice = await _make_practice(db_session, "Closed Clinic")
    today = date.today()
    await _make_case(db_session, practice, state=CaseState.closed, filing_deadline=today - timedelta(days=5))
    await _make_case(db_session, practice, state=CaseState.paid, filing_deadline=today + timedelta(days=2))
    await _make_case(db_session, practice, state=CaseState.declined, filing_deadline=today + timedelta(days=2))
    await db_session.commit()

    r = await ops_client.get("/api/ops/deadlines")
    assert r.status_code == 200
    assert r.json() == []


# ── Queue practice name ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_queue_includes_practice_name(ops_client: AsyncClient, db_session: AsyncSession):
    practice = await _make_practice(db_session, "Riverside Family Medicine")
    case = await _make_case(db_session, practice, state=CaseState.awaiting_human_review)
    await db_session.commit()

    r = await ops_client.get("/api/queue/cases?state=awaiting_human_review")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    match = next(c for c in data if c["id"] == case.id)
    assert match["practice_name"] == "Riverside Family Medicine"


# ── Win rates specialty ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_win_rates_includes_specialty(ops_client: AsyncClient, db_session: AsyncSession):
    db_session.add(PayerPlaybook(
        payer="Aetna", reason_code="16", specialty="Cardiology",
        success_count=3, attempt_count=5,
    ))
    db_session.add(PayerPlaybook(
        payer="BCBS", reason_code="96", specialty="Orthopedics",
        success_count=2, attempt_count=4,
    ))
    await db_session.commit()

    r = await ops_client.get("/api/kpis/win-rates?min_attempts=1")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 2
    specialties = {row["specialty"] for row in rows}
    assert "Cardiology" in specialties
    assert "Orthopedics" in specialties
