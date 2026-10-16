"""Built-in login, signup gating, team management, and tenant isolation on the new endpoints."""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from denialdesk.api import deps
from denialdesk.api.main import app
from denialdesk.auth.jwt import create_dev_token, verify_token
from denialdesk.auth.models import Role
from denialdesk.auth.passwords import hash_password
from denialdesk.models.case import Case, CaseState, Outcome, Practice, User

PASSWORD = "Correct-Horse-9"
CSV = b"""claim_number,patient_ref,dos,cpt,icd10,billed_amt,allowed_amt,payer,carc,rarc,denial_date
CLM-001,PT-001,2026-06-01,99213,I10,500.00,0.00,Aetna Health Inc,16,MA01,2026-07-01
"""


@pytest_asyncio.fixture
async def client(db_session):
    """Real JWT auth path: only get_session is overridden."""

    async def override_session():
        yield db_session

    app.dependency_overrides.pop(deps.get_current_user, None)  # drop the autouse ops override
    app.dependency_overrides[deps.get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _practice(session, name, status="active") -> Practice:
    p = Practice(name=name, specialty="Family Medicine", onboarding_status=status)
    session.add(p)
    await session.flush()
    return p


async def _user(session, email, role, tenant_id=None, password=PASSWORD) -> User:
    u = User(email=email, password_hash=hash_password(password), full_name=email.split("@")[0],
             role=role.value, tenant_id=tenant_id)
    session.add(u)
    await session.commit()
    return u


async def _login(client, email, password=PASSWORD) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --------------------------------------------------------------------------- login


async def test_login_success_returns_user_and_working_token(client, db_session):
    p = await _practice(db_session, "Alpha")
    await _user(db_session, "a@alpha.com", Role.clinic_admin, p.id)

    r = await client.post("/api/auth/login", json={"email": "A@Alpha.com ", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "clinic_admin"
    assert body["user"]["practice_name"] == "Alpha"

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "a@alpha.com"


async def test_login_wrong_password_and_unknown_email_look_identical(client, db_session):
    p = await _practice(db_session, "Alpha")
    await _user(db_session, "a@alpha.com", Role.clinic_admin, p.id)
    bad_pw = await client.post("/api/auth/login", json={"email": "a@alpha.com", "password": "nope"})
    unknown = await client.post("/api/auth/login", json={"email": "ghost@x.com", "password": "nope"})
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json() == unknown.json()


async def test_account_locks_after_repeated_failures(client, db_session):
    p = await _practice(db_session, "Alpha")
    await _user(db_session, "a@alpha.com", Role.clinic_admin, p.id)
    for _ in range(5):
        r = await client.post("/api/auth/login", json={"email": "a@alpha.com", "password": "wrong"})
        assert r.status_code == 401
    # Even the correct password is refused while locked.
    r = await client.post("/api/auth/login", json={"email": "a@alpha.com", "password": PASSWORD})
    assert r.status_code == 429


async def test_disabled_user_cannot_log_in(client, db_session):
    p = await _practice(db_session, "Alpha")
    u = await _user(db_session, "a@alpha.com", Role.clinic_staff, p.id)
    u.is_active = False
    await db_session.commit()
    r = await client.post("/api/auth/login", json={"email": "a@alpha.com", "password": PASSWORD})
    assert r.status_code == 401


def test_clinic_token_without_tenant_is_rejected():
    token = create_dev_token("1", "x@y.com", None, Role.clinic_admin)
    with pytest.raises(HTTPException) as exc:
        verify_token(token)
    assert exc.value.status_code == 401


# --------------------------------------------------------------------------- signup


async def test_signup_creates_locked_clinic_that_cannot_upload(client, db_session):
    r = await client.post("/api/auth/signup", json={
        "practice_name": "New Clinic", "specialty": "Cardiology", "full_name": "Pat Doe",
        "email": "pat@newclinic.com", "password": PASSWORD,
    })
    assert r.status_code == 201
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert r.json()["user"]["role"] == "clinic_admin"

    practice = await db_session.get(Practice, r.json()["user"]["tenant_id"])
    assert practice.onboarding_status == "pending_agreements"

    up = await client.post("/api/upload", files={"file": ("c.csv", CSV, "text/csv")}, headers=headers)
    assert up.status_code == 403  # locked until ops activates


async def test_signup_rejects_weak_password_and_duplicate_email(client, db_session):
    base = {"practice_name": "New Clinic", "specialty": "Cardiology", "full_name": "Pat Doe",
            "email": "pat@newclinic.com"}
    assert (await client.post("/api/auth/signup", json={**base, "password": "short"})).status_code == 422
    assert (await client.post("/api/auth/signup", json={**base, "password": PASSWORD})).status_code == 201
    assert (await client.post("/api/auth/signup", json={**base, "password": PASSWORD})).status_code == 409


# --------------------------------------------------------------------------- isolation


async def _two_clinics(client, db_session):
    a = await _practice(db_session, "Alpha")
    b = await _practice(db_session, "Beta")
    await _user(db_session, "a@alpha.com", Role.clinic_admin, a.id)
    await _user(db_session, "b@beta.com", Role.clinic_admin, b.id)
    return a, b, await _login(client, "a@alpha.com"), await _login(client, "b@beta.com")


async def test_clinic_cannot_upload_into_another_clinic(client, db_session):
    a, b, ha, _ = await _two_clinics(client, db_session)
    # Alpha's user claims to upload for Beta.
    r = await client.post("/api/upload", data={"practice_id": str(b.id)},
                          files={"file": ("c.csv", CSV, "text/csv")}, headers=ha)
    assert r.status_code == 201
    assert r.json()["practice_id"] == a.id
    cases = (await db_session.execute(Case.__table__.select())).all()
    assert {c.tenant_id for c in cases} == {a.id}


async def test_clinic_cannot_see_or_process_another_clinics_batch(client, db_session):
    a, b, ha, hb = await _two_clinics(client, db_session)
    up = await client.post("/api/upload", files={"file": ("c.csv", CSV, "text/csv")}, headers=hb)
    batch_id = up.json()["batch_id"]

    assert (await client.get(f"/api/batches/{batch_id}", headers=ha)).status_code == 404
    assert (await client.post(f"/api/batches/{batch_id}/process", headers=ha)).status_code == 404
    assert (await client.get("/api/batches", headers=ha)).json() == []
    assert len((await client.get("/api/batches", headers=hb)).json()) == 1


async def test_practice_list_requires_internal_role(client, db_session):
    a, _, ha, _ = await _two_clinics(client, db_session)
    assert (await client.get("/api/practices")).status_code == 401
    assert (await client.get("/api/practices", headers=ha)).status_code == 403


async def test_outcome_read_is_tenant_scoped(client, db_session):
    a, b, ha, hb = await _two_clinics(client, db_session)
    up = await client.post("/api/upload", files={"file": ("c.csv", CSV, "text/csv")}, headers=hb)
    case = (await db_session.execute(Case.__table__.select())).first()
    db_session.add(Outcome(case_id=case.id, tenant_id=b.id, result="paid", amount_recovered=100))
    await db_session.commit()

    assert (await client.get(f"/api/cases/{case.id}/outcome", headers=ha)).status_code == 404
    assert (await client.get(f"/api/cases/{case.id}/outcome", headers=hb)).status_code == 200
    assert (await client.get(f"/api/cases/{case.id}/outcome")).status_code == 401


async def test_case_detail_hides_staff_identity_from_clinic(client, db_session):
    a, _, ha, _ = await _two_clinics(client, db_session)
    await client.post("/api/upload", files={"file": ("c.csv", CSV, "text/csv")}, headers=ha)
    case = (await db_session.execute(Case.__table__.select())).first()
    from denialdesk.models.case import AuditEvent
    db_session.add(AuditEvent(case_id=case.id, tenant_id=a.id, actor="reviewer@denialdesk.com",
                              action="review:approved"))
    await db_session.commit()

    detail = (await client.get(f"/api/cases/{case.id}", headers=ha)).json()
    actors = {e["actor"] for e in detail["timeline"]}
    assert "reviewer@denialdesk.com" not in str(detail)
    assert actors <= {"DenialDesk AI", "DenialDesk team", "Clinic"}


# --------------------------------------------------------------------------- team management


async def test_clinic_admin_manages_only_own_team(client, db_session):
    a, b, ha, hb = await _two_clinics(client, db_session)
    other = await _user(db_session, "staff@beta.com", Role.clinic_staff, b.id)

    listed = (await client.get("/api/users", headers=ha)).json()
    assert {u["email"] for u in listed} == {"a@alpha.com"}

    # Can't touch another clinic's user.
    assert (await client.patch(f"/api/users/{other.id}", json={"is_active": False}, headers=ha)).status_code == 404

    # Can add own staff, always into own clinic even if tenant_id is supplied.
    r = await client.post("/api/users", headers=ha, json={
        "email": "new@alpha.com", "full_name": "New Person", "role": "clinic_staff",
        "temp_password": PASSWORD, "tenant_id": b.id})
    assert r.status_code == 201 and r.json()["tenant_id"] == a.id

    # Can't mint internal staff.
    r = await client.post("/api/users", headers=ha, json={
        "email": "evil@alpha.com", "full_name": "Evil Admin", "role": "ops_admin", "temp_password": PASSWORD})
    assert r.status_code == 403


async def test_staff_cannot_manage_users_and_cannot_demote_self(client, db_session):
    a, _, ha, _ = await _two_clinics(client, db_session)
    await _user(db_session, "s@alpha.com", Role.clinic_staff, a.id)
    hs = await _login(client, "s@alpha.com")
    assert (await client.get("/api/users", headers=hs)).status_code == 403
    me = (await client.get("/api/auth/me", headers=ha)).json()
    r = await client.patch(f"/api/users/{me['id']}", json={"is_active": False}, headers=ha)
    assert r.status_code == 400


async def test_change_password(client, db_session):
    p = await _practice(db_session, "Alpha")
    await _user(db_session, "a@alpha.com", Role.clinic_admin, p.id)
    h = await _login(client, "a@alpha.com")
    bad = await client.post("/api/auth/change-password", headers=h,
                            json={"current_password": "wrong", "new_password": "Another-Pass-1"})
    assert bad.status_code == 400
    ok = await client.post("/api/auth/change-password", headers=h,
                           json={"current_password": PASSWORD, "new_password": "Another-Pass-1"})
    assert ok.status_code == 204
    await _login(client, "a@alpha.com", "Another-Pass-1")
