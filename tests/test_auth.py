"""Tests for JWT auth, roles, and token endpoint."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from denialdesk.api.main import app
from denialdesk.api import deps
from denialdesk.auth.jwt import create_dev_token, verify_token
from denialdesk.auth.models import Role, UserClaims
from denialdesk.config import settings
from denialdesk.models.case import Base, Batch, Case, CaseState, Practice
from datetime import datetime as dt, timezone as tz


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token(role: str = "ops_admin", tenant_id=None, exp_delta_hours: float = 8) -> str:
    payload = {
        "sub": "test-user",
        "email": "test@test.com",
        "tenant_id": tenant_id,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=exp_delta_hours),
    }
    return jwt.encode(payload, settings.dev_jwt_secret, algorithm="HS256")


@pytest.fixture
def auth_base_url():
    return "http://test"


@pytest.fixture
def raw_client():
    """Client with NO dependency overrides — tests real JWT path."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Token creation + verification (unit tests — no HTTP)
# ---------------------------------------------------------------------------


def test_verify_token_valid():
    token = create_dev_token("u1", "u1@test.com", 1, Role.clinic_admin)
    claims = verify_token(token)
    assert claims.user_id == "u1"
    assert claims.email == "u1@test.com"
    assert claims.tenant_id == 1
    assert claims.role == Role.clinic_admin


def test_verify_token_ops_admin_no_tenant():
    token = create_dev_token("ops", "ops@dd.com", None, Role.ops_admin)
    claims = verify_token(token)
    assert claims.tenant_id is None
    assert claims.is_ops is True


def test_verify_token_expired():
    payload = {
        "sub": "u",
        "email": "u@test.com",
        "tenant_id": 1,
        "role": "clinic_staff",
        "iat": datetime.now(timezone.utc) - timedelta(hours=10),
        "exp": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    token = jwt.encode(payload, settings.dev_jwt_secret, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        verify_token(token)
    assert exc.value.status_code == 401


def test_verify_token_bad_signature():
    token = create_dev_token("u", "u@test.com", 1, Role.reviewer)
    tampered = token[:-4] + "XXXX"
    with pytest.raises(HTTPException) as exc:
        verify_token(tampered)
    assert exc.value.status_code == 401


def test_user_claims_to_tenant_context():
    claims = UserClaims(user_id="u", email="e", tenant_id=5, role=Role.clinic_admin)
    ctx = claims.to_tenant_context()
    assert ctx is not None
    assert ctx.tenant_id == 5


def test_user_claims_ops_no_tenant_context():
    claims = UserClaims(user_id="u", email="e", tenant_id=None, role=Role.ops_admin)
    ctx = claims.to_tenant_context()
    assert ctx is None


# ---------------------------------------------------------------------------
# Dev token endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dev_token_endpoint_returns_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/dev-token", json={"role": "ops_admin", "tenant_id": None})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert len(data["access_token"]) > 20
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_dev_token_invalid_role():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/dev-token", json={"role": "superuser"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Endpoint protection via HTTP
# ---------------------------------------------------------------------------


@pytest.fixture
async def authed_db_client():
    """Client with fresh in-memory DB and real JWT auth (no get_current_user override).

    The conftest autouse fixture adds a default ops_admin override for all tests.
    We pop it here so this client exercises the actual JWT verification path.
    """
    # Clear the autouse default so real JWT auth applies
    app.dependency_overrides.pop(deps.get_current_user, None)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[deps.get_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, engine

    app.dependency_overrides.pop(deps.get_session, None)
    await engine.dispose()


@pytest.mark.asyncio
async def test_require_auth_no_token(authed_db_client):
    client, _ = authed_db_client
    resp = await client.get("/api/queue")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_require_auth_valid_token(authed_db_client):
    client, _ = authed_db_client
    token = _make_token("ops_admin")
    resp = await client.get("/api/queue", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_role_clinic_staff_cannot_access_kpis(authed_db_client):
    client, _ = authed_db_client
    token = _make_token("clinic_staff", tenant_id=1)
    resp = await client.get("/api/kpis/overview", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_role_ops_admin_can_access_kpis(authed_db_client):
    client, _ = authed_db_client
    token = _make_token("ops_admin")
    resp = await client.get("/api/kpis/overview", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tenant_scoped_via_jwt(authed_db_client):
    """clinic_admin with tenant_id=1 cannot see a case belonging to tenant_id=2."""
    client, engine = authed_db_client
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Create a case owned by tenant 2
    async with factory() as session:
        p1 = Practice(name="Clinic 1", specialty="IM")
        p2 = Practice(name="Clinic 2", specialty="IM")
        session.add_all([p1, p2])
        await session.flush()

        batch = Batch(
            practice_id=p2.id,
            tenant_id=p2.id,
            uploaded_at=datetime.now(timezone.utc),
            source_files="test.csv",
        )
        session.add(batch)
        await session.flush()

        case = Case(
            batch_id=batch.id,
            tenant_id=p2.id,
            payer="Aetna",
            patient_ref="PT-001",
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
        await session.commit()
        case_id = case.id
        tenant1_id = p1.id

    # clinic_admin for tenant 1 tries to access tenant 2's case
    token = _make_token("clinic_admin", tenant_id=tenant1_id)
    resp = await client.get(f"/api/cases/{case_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
