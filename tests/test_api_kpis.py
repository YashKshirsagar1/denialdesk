"""KPI endpoint tests."""
import json
from datetime import datetime, timezone

import pytest

from denialdesk.models.case import AuditEvent, CaseState, Diagnosis, Outcome
from tests.conftest import add_diagnosis, seed_case


@pytest.mark.asyncio
async def test_overview_empty(api_client):
    r = await api_client.get("/api/kpis/overview")
    assert r.status_code == 200
    data = r.json()
    assert data["total_cases"] == 0
    assert data["total_paid"] == 0
    assert data["recovery_rate"] == 0.0
    assert data["decline_rate"] == 0.0
    assert data["avg_winnability_score"] == 0.0
    assert data["avg_days_to_payment"] == 0.0


@pytest.mark.asyncio
async def test_pipeline_empty(api_client):
    r = await api_client.get("/api/kpis/pipeline")
    assert r.status_code == 200
    data = r.json()
    assert "stages" in data
    assert "total" in data
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_win_rates_empty(api_client):
    r = await api_client.get("/api/kpis/win-rates")
    assert r.status_code == 200
    data = r.json()
    assert data["rows"] == []
    assert data["total_rows"] == 0


@pytest.mark.asyncio
async def test_score_accuracy_empty(api_client):
    r = await api_client.get("/api/kpis/score-accuracy")
    assert r.status_code == 200
    data = r.json()
    assert data["rows"] == []
    assert "Based on 0 cases" in data["correlation_note"]


@pytest.mark.asyncio
async def test_overview_with_data(api_client, db_session):
    # Seed a paid case
    case1 = await seed_case(db_session, CaseState.ingested)
    # Transition to submitted → pending_payer
    for state in [CaseState.diagnosed, CaseState.approved, CaseState.drafted,
                  CaseState.awaiting_human_review, CaseState.submitted, CaseState.pending_payer]:
        ev = case1.transition(state, actor="test")
        db_session.add(ev)
        await db_session.flush()

    outcome = Outcome(
        case_id=case1.id,
        result="paid",
        amount_recovered=500.0,
        paid_date=datetime.now(timezone.utc),
        notes="",
    )
    db_session.add(outcome)
    ev = case1.transition(CaseState.paid, actor="test")
    db_session.add(ev)
    await db_session.flush()

    # Seed a declined case
    case2 = await seed_case(db_session, CaseState.ingested)
    ev = case2.transition(CaseState.diagnosed, actor="test")
    db_session.add(ev)
    await db_session.flush()
    ev = case2.transition(CaseState.declined, actor="test")
    db_session.add(ev)
    await db_session.flush()

    await db_session.commit()

    r = await api_client.get("/api/kpis/overview")
    assert r.status_code == 200
    data = r.json()
    assert data["total_cases"] == 2
    assert data["total_paid"] == 1
    assert data["total_declined"] == 1
    # 1 paid out of 1 attempted (case1 reached submitted+)
    assert data["recovery_rate"] == 1.0


@pytest.mark.asyncio
async def test_pipeline_with_data(api_client, db_session):
    case1 = await seed_case(db_session, CaseState.ingested)
    case2 = await seed_case(db_session, CaseState.ingested)
    ev = case2.transition(CaseState.diagnosed, actor="test")
    db_session.add(ev)
    await db_session.flush()
    await db_session.commit()

    r = await api_client.get("/api/kpis/pipeline")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    states_in_result = {s["state"] for s in data["stages"]}
    assert "ingested" in states_in_result or "diagnosed" in states_in_result


@pytest.mark.asyncio
async def test_score_accuracy_with_data(api_client, db_session):
    case1 = await seed_case(db_session, CaseState.ingested)
    diag = await add_diagnosis(db_session, case1)  # score=0.7

    for state in [CaseState.diagnosed, CaseState.approved, CaseState.drafted,
                  CaseState.awaiting_human_review, CaseState.submitted, CaseState.pending_payer]:
        ev = case1.transition(state, actor="test")
        db_session.add(ev)
        await db_session.flush()

    outcome = Outcome(
        case_id=case1.id,
        result="paid",
        amount_recovered=300.0,
        paid_date=datetime.now(timezone.utc),
        notes="",
    )
    db_session.add(outcome)
    await db_session.flush()
    await db_session.commit()

    r = await api_client.get("/api/kpis/score-accuracy")
    assert r.status_code == 200
    data = r.json()
    assert "Based on 1 cases" in data["correlation_note"]
    # Score 0.7 falls in 0.6–0.8 bucket
    buckets = {row["score_bucket"]: row for row in data["rows"]}
    assert "0.6–0.8" in buckets
    assert buckets["0.6–0.8"]["actual_win_rate"] == 1.0
