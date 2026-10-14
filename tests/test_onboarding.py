"""Tests for Phase 2 step 8 — onboarding flow and agreement lock."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api import deps
from denialdesk.api.main import app
from denialdesk.auth.models import Role, UserClaims
from denialdesk.models.case import OnboardingStatus, Practice


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clinic_user(tenant_id: int, role: Role = Role.clinic_admin) -> UserClaims:
    return UserClaims(
        user_id="clinic-user",
        email="clinic@test.local",
        tenant_id=tenant_id,
        role=role,
    )


def _ops_user() -> UserClaims:
    return UserClaims(user_id="ops-user", email="ops@test.local", tenant_id=None, role=Role.ops_admin)


@pytest_asyncio.fixture
async def ops_client(api_client: AsyncClient) -> AsyncClient:
    """api_client already has ops_admin injected via autouse fixture."""
    return api_client


@pytest_asyncio.fixture
async def clinic_client(db_session: AsyncSession):
    """AsyncClient with a clinic_admin user injected (tenant_id TBD — set per test)."""
    async def override_session():
        yield db_session

    async def override_user():
        return _clinic_user(tenant_id=1)

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Practice CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_practice_as_ops(ops_client: AsyncClient):
    resp = await ops_client.post("/api/ops/practices", json={"name": "Riverside Clinic", "specialty": "Family Medicine"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Riverside Clinic"
    assert data["onboarding_status"] == OnboardingStatus.pending_agreements.value
    assert data["baa_signed"] is False
    assert data["service_agreement_signed"] is False


@pytest.mark.asyncio
async def test_clinic_cannot_create_practice(db_session: AsyncSession):
    async def override_session():
        yield db_session

    async def override_user():
        return _clinic_user(tenant_id=1)

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/ops/practices", json={"name": "X", "specialty": "Y"})
    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_practices_as_ops(ops_client: AsyncClient):
    await ops_client.post("/api/ops/practices", json={"name": "P1", "specialty": "S1"})
    await ops_client.post("/api/ops/practices", json={"name": "P2", "specialty": "S2"})
    resp = await ops_client.get("/api/ops/practices")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


# ---------------------------------------------------------------------------
# Agreement signing and activation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_activate_requires_both_agreements(ops_client: AsyncClient):
    create_resp = await ops_client.post("/api/ops/practices", json={"name": "Acme Clinic", "specialty": "Internal Medicine"})
    pid = create_resp.json()["id"]

    # Activate without signing anything → 400
    resp = await ops_client.post(f"/api/ops/practices/{pid}/activate")
    assert resp.status_code == 400
    assert "BAA" in resp.json()["detail"]

    # Sign BAA only → still 400
    await ops_client.post(f"/api/ops/practices/{pid}/sign-baa")
    resp = await ops_client.post(f"/api/ops/practices/{pid}/activate")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_activate_succeeds_after_both_signed(ops_client: AsyncClient):
    create_resp = await ops_client.post("/api/ops/practices", json={"name": "Happy Clinic", "specialty": "Pediatrics"})
    pid = create_resp.json()["id"]

    await ops_client.post(f"/api/ops/practices/{pid}/sign-baa")
    await ops_client.post(f"/api/ops/practices/{pid}/sign-service-agreement")
    resp = await ops_client.post(f"/api/ops/practices/{pid}/activate")
    assert resp.status_code == 200
    assert resp.json()["onboarding_status"] == OnboardingStatus.active.value


@pytest.mark.asyncio
async def test_suspend_practice(ops_client: AsyncClient):
    create_resp = await ops_client.post("/api/ops/practices", json={"name": "Sunset Clinic", "specialty": "Oncology"})
    pid = create_resp.json()["id"]
    resp = await ops_client.post(f"/api/ops/practices/{pid}/suspend")
    assert resp.status_code == 200
    assert resp.json()["onboarding_status"] == OnboardingStatus.suspended.value


# ---------------------------------------------------------------------------
# Upload gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_blocked_when_pending(db_session: AsyncSession):
    """A clinic with pending_agreements status cannot upload files."""
    practice = Practice(name="Locked Clinic", specialty="Cardiology", onboarding_status="pending_agreements")
    db_session.add(practice)
    await db_session.flush()
    tid = practice.id

    async def override_session():
        yield db_session

    async def override_user():
        return _clinic_user(tenant_id=tid)

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/upload",
            data={"practice_id": str(tid)},
            files={"file": ("test.csv", b"data", "text/csv")},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 403
    assert "not yet active" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_allowed_when_active(db_session: AsyncSession):
    """An active practice can proceed past the onboarding gate (may fail for other reasons)."""
    practice = Practice(name="Active Clinic", specialty="Family Medicine", onboarding_status="active")
    db_session.add(practice)
    await db_session.flush()
    tid = practice.id

    async def override_session():
        yield db_session

    async def override_user():
        return _clinic_user(tenant_id=tid, role=Role.clinic_admin)

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/upload",
            data={"practice_id": str(tid)},
            files={"file": ("test.csv", b"payer,patient_ref\nAetna,PT-001\n", "text/csv")},
        )
    app.dependency_overrides.clear()
    # Not 403 — onboarding gate passed (may be 201 or 422 depending on file content)
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Onboarding checklist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_onboarding_checklist_fields(db_session: AsyncSession):
    """Checklist reflects actual practice fields."""
    practice = Practice(
        name="Checklist Clinic",
        specialty="Internal Medicine",
        onboarding_status="pending_agreements",
    )
    db_session.add(practice)
    await db_session.flush()
    tid = practice.id

    async def override_session():
        yield db_session

    async def override_user():
        return _clinic_user(tenant_id=tid)

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/clinic/onboarding")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["onboarding_status"] == "pending_agreements"
    checklist = data["checklist"]
    assert checklist["baa_signed"] is False
    assert checklist["service_agreement_signed"] is False
    assert checklist["practice_details"] is False
    assert checklist["specialties"] is False
    assert checklist["payers_billed"] is False
    assert checklist["payer_portal_access"] is False


@pytest.mark.asyncio
async def test_onboarding_checklist_partial(db_session: AsyncSession):
    """After signing BAA, baa_signed flips to True."""
    import json as _json
    practice = Practice(
        name="Partial Clinic",
        specialty="Family Medicine",
        onboarding_status="pending_agreements",
        address="123 Main St",
        phone="555-1234",
        npi="1234567890",
        specialties=_json.dumps(["Family Medicine"]),
        payers_billed=_json.dumps(["Aetna"]),
    )
    db_session.add(practice)
    await db_session.flush()
    from datetime import datetime, timezone
    practice.baa_signed_at = datetime.now(timezone.utc)
    practice.baa_signed_by = "ops-user"
    await db_session.flush()
    tid = practice.id

    async def override_session():
        yield db_session

    async def override_user():
        return _clinic_user(tenant_id=tid)

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/clinic/onboarding")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    checklist = data["checklist"]
    assert checklist["baa_signed"] is True
    assert checklist["service_agreement_signed"] is False
    assert checklist["practice_details"] is True
    assert checklist["specialties"] is True
    assert checklist["payers_billed"] is True
    assert checklist["payer_portal_access"] is False


# ---------------------------------------------------------------------------
# Payer portal access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_payer_portal_access_ops_only(db_session: AsyncSession):
    """Clinic users cannot add payer portal records."""
    practice = Practice(name="Portal Clinic", specialty="Oncology", onboarding_status="active")
    db_session.add(practice)
    await db_session.flush()
    tid = practice.id

    async def override_session():
        yield db_session

    async def override_user():
        return _clinic_user(tenant_id=tid)

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/ops/practices/{tid}/payer-portals",
            json={"payer": "Aetna", "portal_url": "https://portal.aetna.com", "our_username": "staff@denialdesk.com"},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_payer_portal_access_ops_creates(ops_client: AsyncClient):
    create_resp = await ops_client.post("/api/ops/practices", json={"name": "Portal Test", "specialty": "Surgery"})
    pid = create_resp.json()["id"]
    resp = await ops_client.post(
        f"/api/ops/practices/{pid}/payer-portals",
        json={"payer": "UHC", "portal_url": "https://uhcprovider.com", "our_username": "reviewer@denialdesk.com"},
    )
    assert resp.status_code == 201
    assert resp.json()["payer"] == "UHC"
