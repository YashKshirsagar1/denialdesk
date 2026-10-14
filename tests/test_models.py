import pytest

from denialdesk.models.case import (
    AuditEvent,
    Batch,
    Base,
    Case,
    CaseState,
    Diagnosis,
    Draft,
    Outcome,
    PayerPlaybook,
    Practice,
    Review,
    Submission,
)


def _make_case(state: CaseState = CaseState.ingested) -> Case:
    c = Case(batch_id=1, payer="Test Payer", state=state)
    c.id = 1
    c.audit_events = []
    return c


def test_valid_transition():
    case = _make_case(CaseState.ingested)
    event = case.transition(CaseState.diagnosed)
    assert case.state == CaseState.diagnosed
    assert isinstance(event, AuditEvent)
    assert "ingested->diagnosed" in event.action


def test_invalid_transition():
    case = _make_case(CaseState.ingested)
    with pytest.raises(ValueError, match="Invalid transition"):
        case.transition(CaseState.paid)


def test_closed_state_is_terminal():
    case = _make_case(CaseState.closed)
    with pytest.raises(ValueError):
        case.transition(CaseState.ingested)


def test_transition_returns_audit_event():
    case = _make_case(CaseState.ingested)
    event1 = case.transition(CaseState.diagnosed)
    event2 = case.transition(CaseState.approved)
    assert isinstance(event1, AuditEvent)
    assert isinstance(event2, AuditEvent)
    assert "ingested->diagnosed" in event1.action
    assert "diagnosed->approved" in event2.action


def test_all_models_have_timestamps():
    models_with_timestamps = [Practice, Batch, Case, Diagnosis, Draft, Review, Submission, Outcome, PayerPlaybook, AuditEvent]
    for model in models_with_timestamps:
        assert hasattr(model, "created_at"), f"{model.__name__} missing created_at"
        assert hasattr(model, "updated_at"), f"{model.__name__} missing updated_at"


def test_case_state_enum_values():
    expected = {
        "ingested", "diagnosed", "declined", "approved", "drafted",
        "awaiting_human_review", "submitted", "pending_payer", "paid",
        "re_denied", "escalated", "closed",
    }
    actual = {s.value for s in CaseState}
    assert actual == expected
