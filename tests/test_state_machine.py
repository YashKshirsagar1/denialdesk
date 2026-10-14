import pytest

from denialdesk.models.case import AuditEvent, Case, CaseState


def _make_case(state: CaseState = CaseState.ingested) -> Case:
    c = Case(batch_id=1, payer="Test Payer", state=state)
    c.id = 1
    c.audit_events = []
    return c


def test_full_lifecycle_happy_path():
    case = _make_case(CaseState.ingested)
    path = [
        CaseState.diagnosed,
        CaseState.approved,
        CaseState.drafted,
        CaseState.awaiting_human_review,
        CaseState.submitted,
        CaseState.pending_payer,
        CaseState.paid,
        CaseState.closed,
    ]
    for state in path:
        case.transition(state, actor="system")
    assert case.state == CaseState.closed


def test_decline_path():
    case = _make_case(CaseState.diagnosed)
    case.transition(CaseState.declined, actor="system")
    assert case.state == CaseState.declined
    case.transition(CaseState.closed, actor="system")
    assert case.state == CaseState.closed


def test_re_denial_path():
    case = _make_case(CaseState.pending_payer)
    case.transition(CaseState.re_denied, actor="payer")
    assert case.state == CaseState.re_denied
    case.transition(CaseState.escalated, actor="system")
    assert case.state == CaseState.escalated
    case.transition(CaseState.closed, actor="system")
    assert case.state == CaseState.closed


def test_escalated_to_pending_payer():
    case = _make_case(CaseState.escalated)
    case.transition(CaseState.pending_payer, actor="system")
    assert case.state == CaseState.pending_payer


def test_awaiting_review_back_to_drafted():
    case = _make_case(CaseState.awaiting_human_review)
    case.transition(CaseState.drafted, actor="reviewer", action_note="needs revision")
    assert case.state == CaseState.drafted


def test_invalid_transition_raises_value_error():
    case = _make_case(CaseState.ingested)
    with pytest.raises(ValueError, match="Invalid transition"):
        case.transition(CaseState.paid)


def test_invalid_transition_from_closed_raises():
    case = _make_case(CaseState.closed)
    with pytest.raises(ValueError, match="Invalid transition"):
        case.transition(CaseState.ingested)


def test_invalid_transition_skip_states():
    case = _make_case(CaseState.ingested)
    with pytest.raises(ValueError):
        case.transition(CaseState.submitted)


def test_is_terminal_true_for_terminal_states():
    for terminal in (CaseState.paid, CaseState.closed, CaseState.declined):
        case = _make_case(terminal)
        assert case.is_terminal is True, f"Expected {terminal.value} to be terminal"


def test_is_terminal_false_for_active_states():
    active = [
        CaseState.ingested, CaseState.diagnosed, CaseState.approved,
        CaseState.drafted, CaseState.awaiting_human_review,
        CaseState.submitted, CaseState.pending_payer, CaseState.re_denied,
        CaseState.escalated,
    ]
    for state in active:
        case = _make_case(state)
        assert case.is_terminal is False, f"Expected {state.value} to not be terminal"


def test_transition_returns_audit_event_with_correct_fields():
    case = _make_case(CaseState.ingested)
    event = case.transition(CaseState.diagnosed, actor="agent:diagnosis", action_note="scored 0.7")
    assert isinstance(event, AuditEvent)
    assert event.actor == "agent:diagnosis"
    assert "ingested->diagnosed" in event.action
    assert "scored 0.7" in event.action
    assert event.case_id == case.id


def test_transition_updates_state():
    case = _make_case(CaseState.ingested)
    assert case.state == CaseState.ingested
    case.transition(CaseState.diagnosed)
    assert case.state == CaseState.diagnosed


def test_transition_updates_updated_at():
    from datetime import datetime, timezone
    case = _make_case(CaseState.ingested)
    before = case.updated_at if hasattr(case, "updated_at") and case.updated_at else None
    case.transition(CaseState.diagnosed)
    assert case.updated_at is not None
    if before:
        assert case.updated_at >= before


def test_valid_transitions_dict_is_complete():
    for state in CaseState:
        assert state in Case.VALID_TRANSITIONS, f"{state.value} missing from VALID_TRANSITIONS"


def test_transition_without_note():
    case = _make_case(CaseState.ingested)
    event = case.transition(CaseState.diagnosed, actor="system")
    assert "ingested->diagnosed" in event.action
    assert "|" not in event.action
