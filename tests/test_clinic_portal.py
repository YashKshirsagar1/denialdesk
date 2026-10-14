"""Tests for the clinic portal dashboard endpoint (Phase 2 Step 4)."""
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api import deps
from denialdesk.api.main import app
from denialdesk.auth.models import Role, UserClaims
from denialdesk.models.case import Batch, Case, CaseState, Outcome, Practice


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_practice(session: AsyncSession, name: str = "Test Clinic") -> Practice:
    p = Practice(name=name, specialty="Internal Medicine")
    session.add(p)
    await session.flush()
    return p


async def _seed_case(
    session: AsyncSession,
    practice: Practice,
    state: CaseState = CaseState.ingested,
    billed_amt: float = 1000.0,
) -> Case:
    batch = Batch(
        practice_id=practice.id,
        tenant_id=practice.id,
        uploaded_at=datetime.now(timezone.utc),
        source_files="test",
    )
    session.add(batch)
    await session.flush()

    case = Case(
        batch_id=batch.id,
        tenant_id=practice.id,
        payer="Aetna",
        patient_ref="PT-001",
        billed_amt=billed_amt,
        carc="16",
        state=CaseState.ingested,
    )
    session.add(case)
    await session.flush()

    step_map: dict[CaseState, list[CaseState]] = {
        CaseState.diagnosed: [CaseState.diagnosed],
        CaseState.paid: [
            CaseState.diagnosed, CaseState.approved, CaseState.drafted,
            CaseState.awaiting_human_review, CaseState.submitted,
            CaseState.pending_payer, CaseState.paid,
        ],
        CaseState.declined: [CaseState.diagnosed, CaseState.declined],
    }
    for target in step_map.get(state, []):
        event = case.transition(target, actor="test")
        session.add(event)
        await session.flush()

    return case


async def _seed_outcome(session: AsyncSession, case: Case, amount: float) -> Outcome:
    outcome = Outcome(
        case_id=case.id,
        tenant_id=case.tenant_id,
        result="paid",
        amount_recovered=amount,
        paid_date=datetime.now(timezone.utc),
    )
    session.add(outcome)
    await session.flush()
    return outcome


def _clinic_client_ctx(db_session: AsyncSession, tenant_id: int):
    async def override_session():
        yield db_session

    async def override_user():
        return UserClaims(
            user_id="clinic-user",
            email="clinic@test.local",
            tenant_id=tenant_id,
            role=Role.clinic_admin,
        )

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = override_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clinic_dashboard_requires_auth(api_client):
    """No token → 401."""
    saved = app.dependency_overrides.pop(deps.get_current_user, None)
    try:
        resp = await api_client.get("/api/clinic/dashboard")
        assert resp.status_code == 401
    finally:
        if saved:
            app.dependency_overrides[deps.get_current_user] = saved


@pytest.mark.asyncio
async def test_clinic_dashboard_returns_zeros_for_empty_tenant(db_session: AsyncSession):
    """Clinic with no cases → all zeros."""
    practice = await _seed_practice(db_session, "Empty Clinic")
    async with _clinic_client_ctx(db_session, practice.id) as client:
        resp = await client.get("/api/clinic/dashboard")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_cases"] == 0
    assert data["dollars_submitted"] == 0.0
    assert data["dollars_recovered"] == 0.0
    assert data["cases_in_progress"] == 0
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_clinic_dashboard_sums_correctly(db_session: AsyncSession):
    """Tenant A: 2 cases (1 diagnosed, 1 ingested). Tenant B: 1 case. Dashboard for A excludes B."""
    practice_a = await _seed_practice(db_session, "Clinic A")
    practice_b = await _seed_practice(db_session, "Clinic B")

    case1 = await _seed_case(db_session, practice_a, state=CaseState.diagnosed, billed_amt=500.0)
    case2 = await _seed_case(db_session, practice_a, state=CaseState.ingested, billed_amt=800.0)
    _case3 = await _seed_case(db_session, practice_b, state=CaseState.ingested, billed_amt=9999.0)

    await _seed_outcome(db_session, case1, amount=400.0)
    await db_session.flush()

    async with _clinic_client_ctx(db_session, practice_a.id) as client:
        resp = await client.get("/api/clinic/dashboard")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_cases"] == 2
    assert data["dollars_submitted"] == 1300.0
    assert data["dollars_recovered"] == 400.0
    assert data["cases_in_progress"] == 2    # diagnosed + ingested are both in-progress states
    assert data["cases_paid"] == 0
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ops_admin_without_tenant_gets_400(db_session: AsyncSession):
    """ops_admin token has no tenant_id → 400."""
    async def override_session():
        yield db_session

    async def override_ops():
        return UserClaims(
            user_id="ops",
            email="ops@test.local",
            tenant_id=None,
            role=Role.ops_admin,
        )

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = override_ops
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/clinic/dashboard")
    assert resp.status_code == 400
    assert "tenant" in resp.json()["detail"].lower()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cases_list_is_tenant_scoped(db_session: AsyncSession):
    """GET /api/cases returns only the requesting tenant's cases."""
    practice_x = await _seed_practice(db_session, "Clinic X")
    practice_y = await _seed_practice(db_session, "Clinic Y")

    case_x = await _seed_case(db_session, practice_x, billed_amt=100.0)
    case_y = await _seed_case(db_session, practice_y, billed_amt=200.0)
    await db_session.flush()

    async with _clinic_client_ctx(db_session, practice_x.id) as client:
        resp = await client.get("/api/cases")
    assert resp.status_code == 200, resp.text
    ids = [c["id"] for c in resp.json()]
    assert case_x.id in ids
    assert case_y.id not in ids
    app.dependency_overrides.clear()
