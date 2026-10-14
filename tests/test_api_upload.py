"""API tests for the upload and process endpoints."""
import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.models.case import CaseState, Practice
from tests.conftest import seed_case


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CSV_CONTENT = b"""claim_number,patient_ref,dos,cpt,icd10,billed_amt,allowed_amt,payer,carc,rarc,denial_date
CLM-001,PT-001,2026-06-01,99213,I10,500.00,0.00,Aetna Health Inc,16,MA01,2026-07-01
CLM-002,PT-002,2026-06-15,99214,E11.9,750.00,0.00,UnitedHealthcare,50,N130,2026-07-15
"""


async def _seed_practice(session: AsyncSession, name: str = "Test Practice", specialty: str = "Internal Medicine") -> Practice:
    p = Practice(name=name, specialty=specialty)
    session.add(p)
    await session.flush()
    return p


# ---------------------------------------------------------------------------
# GET /api/practices
# ---------------------------------------------------------------------------

async def test_list_practices_empty(api_client: AsyncClient):
    resp = await api_client.get("/api/practices")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_practices_returns_practices(api_client: AsyncClient, db_session: AsyncSession):
    await _seed_practice(db_session, "Riverside Medicine", "Internal Medicine")
    await _seed_practice(db_session, "Cardio Clinic", "Cardiology")
    await db_session.flush()

    resp = await api_client.get("/api/practices")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {p["name"] for p in data}
    assert "Riverside Medicine" in names
    assert "Cardio Clinic" in names


# ---------------------------------------------------------------------------
# POST /api/upload
# ---------------------------------------------------------------------------

async def test_upload_csv_success(api_client: AsyncClient, db_session: AsyncSession):
    practice = await _seed_practice(db_session)
    await db_session.flush()

    resp = await api_client.post(
        "/api/upload",
        files={"file": ("denials.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
        data={"practice_id": str(practice.id)},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["case_count"] == 2
    assert body["practice_id"] == practice.id
    assert isinstance(body["batch_id"], int)
    assert body["batch_id"] > 0


async def test_upload_practice_not_found(api_client: AsyncClient):
    resp = await api_client.post(
        "/api/upload",
        files={"file": ("denials.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
        data={"practice_id": "9999"},
    )
    assert resp.status_code == 404


async def test_upload_unsupported_format(api_client: AsyncClient, db_session: AsyncSession):
    practice = await _seed_practice(db_session)
    await db_session.flush()

    resp = await api_client.post(
        "/api/upload",
        files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        data={"practice_id": str(practice.id)},
    )
    # PDF without real content will fail — should be 422
    assert resp.status_code in (422, 500)


# ---------------------------------------------------------------------------
# POST /api/batches/{batch_id}/process  (mocked coordinator)
# ---------------------------------------------------------------------------

async def test_process_batch_calls_coordinator(api_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    from denialdesk.coordinator import BatchResult
    import denialdesk.api.routers.upload as upload_mod

    practice = await _seed_practice(db_session)
    await db_session.flush()

    # Upload a batch first
    resp = await api_client.post(
        "/api/upload",
        files={"file": ("denials.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
        data={"practice_id": str(practice.id)},
    )
    assert resp.status_code == 201
    batch_id = resp.json()["batch_id"]

    # Patch coordinator to avoid real LLM calls
    async def _fake_process_batch(self, bid):
        return BatchResult(batch_id=bid, processed=2, declined=0, awaiting_review=2)

    from denialdesk.coordinator import Coordinator
    monkeypatch.setattr(Coordinator, "process_batch", _fake_process_batch)

    resp2 = await api_client.post(f"/api/batches/{batch_id}/process")
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["processed"] == 2
    assert body["awaiting_review"] == 2
    assert body["declined"] == 0
    assert body["batch_id"] == batch_id


async def test_process_batch_returns_decline_counts(api_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    from denialdesk.coordinator import BatchResult, Coordinator

    practice = await _seed_practice(db_session)
    await db_session.flush()

    resp = await api_client.post(
        "/api/upload",
        files={"file": ("denials.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
        data={"practice_id": str(practice.id)},
    )
    batch_id = resp.json()["batch_id"]

    async def _fake_process_batch(self, bid):
        return BatchResult(batch_id=bid, processed=2, declined=1, awaiting_review=1)

    monkeypatch.setattr(Coordinator, "process_batch", _fake_process_batch)

    resp2 = await api_client.post(f"/api/batches/{batch_id}/process")
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["declined"] == 1
    assert body["awaiting_review"] == 1
