"""API tests for the outcomes endpoints."""
import pytest
from httpx import AsyncClient

from denialdesk.models.case import CaseState
from tests.conftest import add_draft, seed_case


async def _advance_to_submitted(session, api_client) -> int:
    """Seed a case at awaiting_human_review, approve it to reach submitted."""
    case = await seed_case(session, CaseState.awaiting_human_review)
    await add_draft(session, case)
    # Approve via review endpoint to reach submitted
    resp = await api_client.post(
        f"/api/cases/{case.id}/review",
        json={"decision": "approve", "reviewer": "tester"},
    )
    assert resp.status_code == 200
    return case.id


async def test_post_outcome_paid(api_client: AsyncClient, db_session):
    case_id = await _advance_to_submitted(db_session, api_client)
    resp = await api_client.post(
        f"/api/cases/{case_id}/outcome",
        json={"result": "paid", "amount_recovered": 450.0, "notes": "paid in full"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["new_state"] == "paid"
    assert data["amount_recovered"] == 450.0


async def test_post_outcome_denied(api_client: AsyncClient, db_session):
    case_id = await _advance_to_submitted(db_session, api_client)
    resp = await api_client.post(
        f"/api/cases/{case_id}/outcome",
        json={"result": "denied", "amount_recovered": 0},
    )
    assert resp.status_code == 200
    assert resp.json()["new_state"] == "re_denied"


async def test_get_outcome_exists(api_client: AsyncClient, db_session):
    case_id = await _advance_to_submitted(db_session, api_client)
    await api_client.post(
        f"/api/cases/{case_id}/outcome",
        json={"result": "paid", "amount_recovered": 300.0},
    )
    resp = await api_client.get(f"/api/cases/{case_id}/outcome")
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "paid"
    assert data["amount_recovered"] == 300.0


async def test_get_outcome_not_found(api_client: AsyncClient, db_session):
    case = await seed_case(db_session, CaseState.ingested)
    resp = await api_client.get(f"/api/cases/{case.id}/outcome")
    assert resp.status_code == 404


async def test_outcomes_summary_empty(api_client: AsyncClient, db_session):
    resp = await api_client.get("/api/outcomes/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_cases_with_outcomes"] == 0
    assert data["win_rate"] == 0.0
