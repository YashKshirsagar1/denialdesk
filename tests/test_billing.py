"""Tests for fee calculation, outcome verification, and statement generation."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from denialdesk.api import deps
from denialdesk.api.main import app
from denialdesk.auth.models import Role, UserClaims
from denialdesk.billing.fees import calculate_fee, is_aged
from denialdesk.billing.statement_service import StatementService
from denialdesk.models.case import Batch, Case, CaseState, Outcome, Practice, Statement

from tests.conftest import api_client, db_session, seed_case


# ---------------------------------------------------------------------------
# Pure unit tests — no DB
# ---------------------------------------------------------------------------

def test_fee_calculation_standard():
    denial = date.today() - timedelta(days=30)
    fee, aged, rate = calculate_fee(Decimal("1000"), denial, Decimal("0.22"), Decimal("0.32"), 180)
    assert not aged
    assert rate == Decimal("0.22")
    assert fee == Decimal("220.00")


def test_fee_calculation_aged():
    denial = date.today() - timedelta(days=200)
    fee, aged, rate = calculate_fee(Decimal("1000"), denial, Decimal("0.22"), Decimal("0.32"), 180)
    assert aged
    assert rate == Decimal("0.32")
    assert fee == Decimal("320.00")


def test_fee_calculation_none_denial_date():
    fee, aged, rate = calculate_fee(Decimal("500"), None, Decimal("0.22"), Decimal("0.32"), 180)
    assert not aged
    assert fee == Decimal("110.00")


# ---------------------------------------------------------------------------
# API tests — use db_session / api_client fixtures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_outcome_requires_existing_outcome(api_client: AsyncClient, db_session):
    case = await seed_case(db_session)
    await db_session.commit()

    resp = await api_client.post(
        f"/api/cases/{case.id}/outcome/verify",
        json={"verification_method": "clinic_confirmation", "verified_by": "alice"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_verify_outcome_sets_billable_amount(api_client: AsyncClient, db_session):
    practice = Practice(
        name="Fee Test Practice",
        specialty="IM",
        onboarding_status="active",
        fee_rate_standard=0.2200,
        fee_rate_aged=0.3200,
        aged_threshold_days=180,
    )
    db_session.add(practice)
    await db_session.flush()

    batch = Batch(practice_id=practice.id, uploaded_at=datetime.now(timezone.utc))
    db_session.add(batch)
    await db_session.flush()

    case = Case(
        batch_id=batch.id,
        tenant_id=practice.id,
        payer="Aetna",
        cpt_hcpcs="99213",
        denial_date=datetime.now(timezone.utc) - timedelta(days=30),
        state=CaseState.paid,
    )
    db_session.add(case)
    await db_session.flush()

    outcome = Outcome(
        case_id=case.id,
        tenant_id=practice.id,
        result="paid",
        amount_recovered=1000.0,
        paid_date=datetime.now(timezone.utc),
    )
    db_session.add(outcome)
    await db_session.commit()

    resp = await api_client.post(
        f"/api/cases/{case.id}/outcome/verify",
        json={"verification_method": "clinic_confirmation", "verified_by": "alice"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert data["billable_amount"] == pytest.approx(220.0, abs=0.01)


@pytest.mark.asyncio
async def test_generate_statement_sums_correctly(api_client: AsyncClient, db_session):
    practice = Practice(
        name="Stmt Practice",
        specialty="FM",
        onboarding_status="active",
        fee_rate_standard=0.2200,
        fee_rate_aged=0.3200,
        aged_threshold_days=180,
    )
    db_session.add(practice)
    await db_session.flush()

    batch = Batch(practice_id=practice.id, uploaded_at=datetime.now(timezone.utc))
    db_session.add(batch)
    await db_session.flush()

    period_start = date(2026, 9, 1)
    period_end = date(2026, 9, 30)
    paid_date = datetime(2026, 9, 15, tzinfo=timezone.utc)

    for i in range(2):
        case = Case(
            batch_id=batch.id,
            tenant_id=practice.id,
            payer="BCBS",
            cpt_hcpcs="99213",
            denial_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
            state=CaseState.paid,
        )
        db_session.add(case)
        await db_session.flush()
        outcome = Outcome(
            case_id=case.id,
            tenant_id=practice.id,
            result="paid",
            amount_recovered=500.0,
            paid_date=paid_date,
            verified=True,
        )
        db_session.add(outcome)
    await db_session.commit()

    resp = await api_client.post(
        "/api/ops/statements/generate",
        json={"practice_id": practice.id, "period_start": "2026-09-01", "period_end": "2026-09-30"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_recovered"] == pytest.approx(1000.0)
    assert data["fee_amount"] == pytest.approx(220.0)


@pytest.mark.asyncio
async def test_generate_statement_excludes_unverified(api_client: AsyncClient, db_session):
    practice = Practice(
        name="Unverified Practice",
        specialty="FM",
        onboarding_status="active",
        fee_rate_standard=0.2200,
        fee_rate_aged=0.3200,
        aged_threshold_days=180,
    )
    db_session.add(practice)
    await db_session.flush()
    batch = Batch(practice_id=practice.id, uploaded_at=datetime.now(timezone.utc))
    db_session.add(batch)
    await db_session.flush()

    paid_date = datetime(2026, 9, 15, tzinfo=timezone.utc)

    # verified outcome
    case1 = Case(batch_id=batch.id, tenant_id=practice.id, payer="Aetna", cpt_hcpcs="99213", state=CaseState.paid)
    db_session.add(case1)
    await db_session.flush()
    o1 = Outcome(case_id=case1.id, tenant_id=practice.id, result="paid", amount_recovered=400.0, paid_date=paid_date, verified=True)
    db_session.add(o1)

    # unverified outcome
    case2 = Case(batch_id=batch.id, tenant_id=practice.id, payer="Aetna", cpt_hcpcs="99213", state=CaseState.paid)
    db_session.add(case2)
    await db_session.flush()
    o2 = Outcome(case_id=case2.id, tenant_id=practice.id, result="paid", amount_recovered=600.0, paid_date=paid_date, verified=False)
    db_session.add(o2)

    await db_session.commit()

    resp = await api_client.post(
        "/api/ops/statements/generate",
        json={"practice_id": practice.id, "period_start": "2026-09-01", "period_end": "2026-09-30"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_recovered"] == pytest.approx(400.0)


@pytest.mark.asyncio
async def test_generate_statement_excludes_other_tenant(api_client: AsyncClient, db_session):
    p1 = Practice(name="P1", specialty="FM", onboarding_status="active", fee_rate_standard=0.22, fee_rate_aged=0.32, aged_threshold_days=180)
    p2 = Practice(name="P2", specialty="FM", onboarding_status="active", fee_rate_standard=0.22, fee_rate_aged=0.32, aged_threshold_days=180)
    db_session.add_all([p1, p2])
    await db_session.flush()

    for practice in [p1, p2]:
        batch = Batch(practice_id=practice.id, uploaded_at=datetime.now(timezone.utc))
        db_session.add(batch)
        await db_session.flush()
        case = Case(batch_id=batch.id, tenant_id=practice.id, payer="UHC", cpt_hcpcs="99213", state=CaseState.paid)
        db_session.add(case)
        await db_session.flush()
        outcome = Outcome(
            case_id=case.id, tenant_id=practice.id, result="paid",
            amount_recovered=800.0, paid_date=datetime(2026, 9, 10, tzinfo=timezone.utc), verified=True,
        )
        db_session.add(outcome)
    await db_session.commit()

    resp = await api_client.post(
        "/api/ops/statements/generate",
        json={"practice_id": p1.id, "period_start": "2026-09-01", "period_end": "2026-09-30"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Only p1's outcome should be included
    assert data["total_recovered"] == pytest.approx(800.0)
    items = json.loads(data.get("line_items") or "[]") if "line_items" in data else []


@pytest.mark.asyncio
async def test_statement_pdf_endpoint_returns_pdf(api_client: AsyncClient, db_session):
    practice = Practice(
        name="PDF Practice",
        specialty="FM",
        onboarding_status="active",
        fee_rate_standard=0.22,
        fee_rate_aged=0.32,
        aged_threshold_days=180,
    )
    db_session.add(practice)
    await db_session.flush()
    batch = Batch(practice_id=practice.id, uploaded_at=datetime.now(timezone.utc))
    db_session.add(batch)
    await db_session.flush()
    case = Case(batch_id=batch.id, tenant_id=practice.id, payer="Aetna", cpt_hcpcs="99213", state=CaseState.paid)
    db_session.add(case)
    await db_session.flush()
    outcome = Outcome(
        case_id=case.id, tenant_id=practice.id, result="paid",
        amount_recovered=300.0, paid_date=datetime(2026, 9, 5, tzinfo=timezone.utc), verified=True,
    )
    db_session.add(outcome)
    await db_session.commit()

    gen_resp = await api_client.post(
        "/api/ops/statements/generate",
        json={"practice_id": practice.id, "period_start": "2026-09-01", "period_end": "2026-09-30"},
    )
    assert gen_resp.status_code == 200
    stmt_id = gen_resp.json()["id"]

    pdf_resp = await api_client.get(f"/api/statements/{stmt_id}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_clinic_cannot_see_other_practice_statement(db_session):
    """Clinic admin for practice 1 cannot access a statement for practice 2."""
    p1 = Practice(name="P1", specialty="FM", onboarding_status="active", fee_rate_standard=0.22, fee_rate_aged=0.32, aged_threshold_days=180)
    p2 = Practice(name="P2", specialty="FM", onboarding_status="active", fee_rate_standard=0.22, fee_rate_aged=0.32, aged_threshold_days=180)
    db_session.add_all([p1, p2])
    await db_session.flush()

    from denialdesk.export.statement_pdf import generate_statement_pdf
    stmt = Statement(
        practice_id=p2.id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        total_recovered=500,
        fee_amount=110,
        status="draft",
        line_items="[]",
        generated_at=datetime.now(timezone.utc),
    )
    db_session.add(stmt)
    await db_session.commit()

    # Override auth to be clinic_admin for p1
    async def clinic_user():
        return UserClaims(user_id="clinic1", email="c@p1.com", tenant_id=p1.id, role=Role.clinic_admin)

    async def override_session():
        yield db_session

    app.dependency_overrides[deps.get_session] = override_session
    app.dependency_overrides[deps.get_current_user] = clinic_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/statements/{stmt.id}/pdf")
        assert resp.status_code in (403, 404)

    app.dependency_overrides.clear()
