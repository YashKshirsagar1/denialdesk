"""Tenant isolation tests — proves that TenantCaseRepository enforces row-level scoping."""
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.models.case import Batch, Case, CaseState, AuditEvent, Practice
from denialdesk.repositories.case_repository import CaseRepository
from denialdesk.repositories.tenant_case_repository import TenantCaseRepository
from denialdesk.repositories.tenant_scoped import TenantContext

from tests.conftest import db_session  # re-export fixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_tenant(session: AsyncSession, name: str) -> Practice:
    p = Practice(name=name, specialty="Internal Medicine")
    session.add(p)
    await session.flush()
    return p


async def _make_batch(session: AsyncSession, practice: Practice) -> Batch:
    b = Batch(
        practice_id=practice.id,
        tenant_id=practice.id,
        uploaded_at=datetime.now(timezone.utc),
        source_files="test.csv",
    )
    session.add(b)
    await session.flush()
    return b


async def _make_case(session: AsyncSession, batch: Batch) -> Case:
    c = Case(
        batch_id=batch.id,
        tenant_id=batch.tenant_id,
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
    session.add(c)
    await session.flush()
    return c


async def _make_audit_event(session: AsyncSession, case: Case, actor: str = "agent") -> AuditEvent:
    e = AuditEvent(
        case_id=case.id,
        tenant_id=case.tenant_id,
        actor=actor,
        action="test_action",
        timestamp=datetime.now(timezone.utc),
    )
    session.add(e)
    await session.flush()
    return e


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_case_returns_own_tenant(db_session: AsyncSession):
    """TenantCaseRepository.get_case finds a case belonging to the same tenant."""
    practice = await _make_tenant(db_session, "Clinic A")
    batch = await _make_batch(db_session, practice)
    case = await _make_case(db_session, batch)

    repo = TenantCaseRepository(db_session, TenantContext(tenant_id=practice.id))
    found = await repo.get_case(case.id)
    assert found is not None
    assert found.id == case.id


@pytest.mark.asyncio
async def test_get_case_blocked_for_wrong_tenant(db_session: AsyncSession):
    """TenantCaseRepository.get_case returns None when the case belongs to a different tenant."""
    clinic_a = await _make_tenant(db_session, "Clinic A")
    clinic_b = await _make_tenant(db_session, "Clinic B")

    batch_a = await _make_batch(db_session, clinic_a)
    case_a = await _make_case(db_session, batch_a)

    # Tenant B tries to fetch tenant A's case
    repo_b = TenantCaseRepository(db_session, TenantContext(tenant_id=clinic_b.id))
    found = await repo_b.get_case(case_a.id)
    assert found is None, "Cross-tenant case access must return None"


@pytest.mark.asyncio
async def test_list_cases_scoped_to_tenant(db_session: AsyncSession):
    """list_cases only returns cases belonging to the requesting tenant."""
    clinic_a = await _make_tenant(db_session, "Clinic A")
    clinic_b = await _make_tenant(db_session, "Clinic B")

    batch_a = await _make_batch(db_session, clinic_a)
    batch_b = await _make_batch(db_session, clinic_b)

    case_a1 = await _make_case(db_session, batch_a)
    case_a2 = await _make_case(db_session, batch_a)
    case_b1 = await _make_case(db_session, batch_b)

    repo_a = TenantCaseRepository(db_session, TenantContext(tenant_id=clinic_a.id))
    cases_a = await repo_a.list_cases()
    ids_a = {c.id for c in cases_a}

    assert case_a1.id in ids_a
    assert case_a2.id in ids_a
    assert case_b1.id not in ids_a, "Clinic B's case must not appear in Clinic A's list"


@pytest.mark.asyncio
async def test_list_cases_empty_for_other_tenant(db_session: AsyncSession):
    """A tenant with no cases gets an empty list even though other tenants have cases."""
    clinic_a = await _make_tenant(db_session, "Clinic A")
    clinic_b = await _make_tenant(db_session, "Clinic B")

    batch_a = await _make_batch(db_session, clinic_a)
    await _make_case(db_session, batch_a)

    repo_b = TenantCaseRepository(db_session, TenantContext(tenant_id=clinic_b.id))
    cases_b = await repo_b.list_cases()
    assert cases_b == []


@pytest.mark.asyncio
async def test_get_audit_trail_scoped_to_tenant(db_session: AsyncSession):
    """get_audit_trail only returns events whose tenant_id matches."""
    clinic_a = await _make_tenant(db_session, "Clinic A")
    clinic_b = await _make_tenant(db_session, "Clinic B")

    batch_a = await _make_batch(db_session, clinic_a)
    batch_b = await _make_batch(db_session, clinic_b)
    case_a = await _make_case(db_session, batch_a)
    case_b = await _make_case(db_session, batch_b)

    event_a = await _make_audit_event(db_session, case_a)
    event_b = await _make_audit_event(db_session, case_b)

    repo_a = TenantCaseRepository(db_session, TenantContext(tenant_id=clinic_a.id))
    trail = await repo_a.get_audit_trail(case_a.id)
    event_ids = {e.id for e in trail}

    assert event_a.id in event_ids
    assert event_b.id not in event_ids


@pytest.mark.asyncio
async def test_create_batch_sets_tenant_id(db_session: AsyncSession):
    """CaseRepository.create_batch copies practice_id into tenant_id."""
    practice = await _make_tenant(db_session, "Clinic A")

    repo = CaseRepository(db_session)
    batch = await repo.create_batch(
        practice_id=practice.id,
        source_format="csv",
        filename="claims.csv",
    )
    assert batch.tenant_id == practice.id


@pytest.mark.asyncio
async def test_create_case_from_record_propagates_tenant_id(db_session: AsyncSession):
    """create_case_from_record sets case.tenant_id from the batch's tenant_id."""
    from decimal import Decimal
    from datetime import date

    practice = await _make_tenant(db_session, "Clinic A")
    repo = CaseRepository(db_session)
    batch = await repo.create_batch(
        practice_id=practice.id,
        source_format="csv",
        filename="claims.csv",
    )

    class FakeRecord:
        payer = "Aetna"
        patient_ref = "PT-001"
        dos = date(2026, 6, 1)
        cpt = "99213"
        icd10 = ["I10"]
        billed_amt = Decimal("500.00")
        allowed_amt = Decimal("350.00")
        carc = "16"
        rarc = "MA01"
        denial_date = date(2026, 7, 1)
        source_format = "csv"

    case, event = await repo.create_case_from_record(batch.id, FakeRecord())
    assert case.tenant_id == practice.id
    assert event.tenant_id == practice.id


@pytest.mark.asyncio
async def test_tenant_context_dep_parses_header():
    """get_tenant_context parses X-Tenant-ID into a TenantContext."""
    from denialdesk.api.deps import get_tenant_context

    ctx = get_tenant_context(x_tenant_id="42")
    assert ctx is not None
    assert ctx.tenant_id == 42


@pytest.mark.asyncio
async def test_tenant_context_dep_returns_none_without_header():
    """get_tenant_context returns None when the header is absent."""
    from denialdesk.api.deps import get_tenant_context

    ctx = get_tenant_context(x_tenant_id=None)
    assert ctx is None


@pytest.mark.asyncio
async def test_require_tenant_context_raises_without_header():
    """require_tenant_context raises HTTP 401 when tenant context is None."""
    from fastapi import HTTPException
    from denialdesk.api.deps import require_tenant_context

    with pytest.raises(HTTPException) as exc_info:
        require_tenant_context(tenant=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_tenant_context_raises_on_invalid_header():
    """get_tenant_context raises HTTP 400 for a non-integer X-Tenant-ID."""
    from fastapi import HTTPException
    from denialdesk.api.deps import get_tenant_context

    with pytest.raises(HTTPException) as exc_info:
        get_tenant_context(x_tenant_id="not-a-number")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_transition_audit_event_inherits_tenant_id(db_session: AsyncSession):
    """Case.transition() stamps the returned AuditEvent with the case's tenant_id."""
    practice = await _make_tenant(db_session, "Clinic A")
    batch = await _make_batch(db_session, practice)
    case = await _make_case(db_session, batch)

    event = case.transition(CaseState.diagnosed, actor="test")
    assert event.tenant_id == practice.id
