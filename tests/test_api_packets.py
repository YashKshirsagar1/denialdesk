"""API tests for PDF packet download endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.models.case import CaseState
from tests.conftest import add_diagnosis, add_draft, seed_case


async def test_appeal_pdf_endpoint(api_client: AsyncClient, db_session: AsyncSession):
    case = await seed_case(db_session, CaseState.awaiting_human_review)
    await add_diagnosis(db_session, case)
    await add_draft(db_session, case, content="We appeal this denial because...", draft_type="appeal")
    await db_session.commit()

    res = await api_client.get(f"/api/cases/{case.id}/packet/appeal.pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"


async def test_call_packet_pdf_endpoint(api_client: AsyncClient, db_session: AsyncSession):
    case = await seed_case(db_session, CaseState.awaiting_human_review)
    await add_diagnosis(db_session, case)
    await add_draft(db_session, case, content="Appeal content here.", draft_type="appeal")
    await db_session.commit()

    res = await api_client.get(f"/api/cases/{case.id}/packet/call-packet.pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"


async def test_attachments_endpoint(api_client: AsyncClient, db_session: AsyncSession):
    case = await seed_case(db_session, CaseState.awaiting_human_review)
    await add_draft(db_session, case, content="Appeal.", draft_type="appeal")
    await db_session.commit()

    res = await api_client.get(f"/api/cases/{case.id}/packet/attachments")
    assert res.status_code == 200
    data = res.json()
    assert "attachments" in data
    assert "clinical_notes" in data["attachments"]


async def test_pdf_404_no_draft(api_client: AsyncClient, db_session: AsyncSession):
    case = await seed_case(db_session, CaseState.awaiting_human_review)
    await db_session.commit()

    res = await api_client.get(f"/api/cases/{case.id}/packet/appeal.pdf")
    assert res.status_code == 404


async def test_pdf_404_case_not_found(api_client: AsyncClient):
    res = await api_client.get("/api/cases/99999/packet/appeal.pdf")
    assert res.status_code == 404


async def test_attachments_empty_when_no_draft(api_client: AsyncClient, db_session: AsyncSession):
    case = await seed_case(db_session, CaseState.awaiting_human_review)
    await db_session.commit()

    res = await api_client.get(f"/api/cases/{case.id}/packet/attachments")
    assert res.status_code == 200
    assert res.json()["attachments"] == []


async def test_call_packet_uses_call_packet_draft(api_client: AsyncClient, db_session: AsyncSession):
    import json
    case = await seed_case(db_session, CaseState.awaiting_human_review)
    await add_diagnosis(db_session, case)
    cp_content = json.dumps({
        "denial_reason": "Missing info",
        "the_ask": "Please reconsider",
        "talking_points": ["Point 1"],
        "escalation_trigger": "No response within 10 days.",
    })
    await add_draft(db_session, case, content=cp_content, draft_type="call_packet")
    await db_session.commit()

    res = await api_client.get(f"/api/cases/{case.id}/packet/call-packet.pdf")
    assert res.status_code == 200
    assert res.content[:4] == b"%PDF"
