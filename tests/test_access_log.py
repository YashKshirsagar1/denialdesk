"""Tests for PHI-safe logging and access audit (Phase 2 Step 7)."""
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from denialdesk.api.main import app
from denialdesk.api import deps
from denialdesk.auth.models import Role, UserClaims
from denialdesk.logging import _scrub, hash_email
from denialdesk.models.case import AccessLog, Base


# ---------------------------------------------------------------------------
# Unit tests — PHI scrubbing and email hashing
# ---------------------------------------------------------------------------

def test_phi_scrub_redacts_patient_ref():
    result = _scrub('"patient_ref": "PT-001"')
    assert "PT-001" not in result
    assert "[REDACTED]" in result


def test_phi_scrub_redacts_patient_name():
    result = _scrub('"name": "John Smith"')
    assert "John Smith" not in result
    assert "[REDACTED]" in result


def test_phi_scrub_redacts_email_key():
    result = _scrub('"email": "patient@example.com"')
    assert "patient@example.com" not in result
    assert "[REDACTED]" in result


def test_phi_scrub_leaves_payer_intact():
    text = '"payer": "Aetna"'
    assert _scrub(text) == text


def test_phi_scrub_leaves_cpt_intact():
    text = '"cpt": "99213"'
    assert _scrub(text) == text


def test_hash_email_is_deterministic():
    assert hash_email("a@b.com") == hash_email("a@b.com")


def test_hash_email_is_not_reversible():
    result = hash_email("a@b.com")
    assert len(result) == 64  # SHA-256 hex
    assert "a@b.com" not in result
    assert all(c in "0123456789abcdef" for c in result)


# ---------------------------------------------------------------------------
# API tests — access log endpoint
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def clean_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def clinic_admin_client(clean_db):
    """AsyncClient authenticated as clinic_admin with tenant_id=1."""

    async def override_session():
        yield clean_db

    async def clinic_admin_user():
        return UserClaims(
            user_id="clinic-admin-1",
            email="admin@clinic.local",
            tenant_id=1,
            role=Role.clinic_admin,
        )

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = clinic_admin_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def clinic_staff_client(clean_db):
    """AsyncClient authenticated as clinic_staff — should not access access-log."""

    async def override_session():
        yield clean_db

    async def clinic_staff_user():
        return UserClaims(
            user_id="staff-1",
            email="staff@clinic.local",
            tenant_id=1,
            role=Role.clinic_staff,
        )

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = clinic_staff_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def ops_client(clean_db):
    """AsyncClient authenticated as ops_admin."""

    async def override_session():
        yield clean_db

    async def ops_user():
        return UserClaims(
            user_id="ops-1",
            email="ops@denialdesk.local",
            tenant_id=None,
            role=Role.ops_admin,
        )

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = ops_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_access_log_requires_clinic_admin_or_ops(clinic_staff_client):
    resp = await clinic_staff_client.get("/api/clinic/access-log")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_access_log_empty_for_new_tenant(clinic_admin_client):
    resp = await clinic_admin_client.get("/api/clinic/access-log")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_ops_admin_can_view_access_log(ops_client):
    resp = await ops_client.get("/api/clinic/access-log")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_access_log_tenant_isolation(clean_db: AsyncSession):
    """Clinic admin for tenant 1 only sees their own log entries."""
    # Seed log entries for two tenants
    now = datetime.now(timezone.utc)
    for tid, actor in [(1, "user-t1"), (2, "user-t2"), (1, "user-t1b")]:
        entry = AccessLog(
            tenant_id=tid,
            actor_id=actor,
            actor_role="clinic_staff",
            resource="case:1",
            action="read",
            http_method="GET",
            path="/api/cases/1",
            timestamp=now,
        )
        clean_db.add(entry)
    await clean_db.flush()

    async def override_session():
        yield clean_db

    async def clinic_admin_t1():
        return UserClaims(
            user_id="admin-t1",
            email="admin@t1.local",
            tenant_id=1,
            role=Role.clinic_admin,
        )

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = clinic_admin_t1
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/clinic/access-log")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    entries = resp.json()
    # Should only see tenant 1's entries (2 of them)
    assert len(entries) == 2
    for e in entries:
        assert e["actor_id"] in ("user-t1", "user-t1b")


@pytest.mark.asyncio
async def test_ops_sees_all_log_entries(clean_db: AsyncSession):
    """Ops admin without tenant filter sees all entries."""
    now = datetime.now(timezone.utc)
    for tid, actor in [(1, "user-t1"), (2, "user-t2")]:
        entry = AccessLog(
            tenant_id=tid,
            actor_id=actor,
            actor_role="clinic_staff",
            resource="case:1",
            action="read",
            http_method="GET",
            path="/api/cases/1",
            timestamp=now,
        )
        clean_db.add(entry)
    await clean_db.flush()

    async def override_session():
        yield clean_db

    async def ops_user():
        return UserClaims(
            user_id="ops-1",
            email="ops@denialdesk.local",
            tenant_id=None,
            role=Role.ops_admin,
        )

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = ops_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/clinic/access-log")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert len(resp.json()) == 2
