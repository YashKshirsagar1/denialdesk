import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from denialdesk.agents.drafting_agent import DraftResult, DraftingAgent
from denialdesk.agents.diagnosis_agent import RootCause
from denialdesk.llm.base import LLMProvider, LLMResponse
from denialdesk.models.case import Case, CaseState, Diagnosis
from denialdesk.templates.payer_templates import (
    DraftType,
    REQUIRED_DOCS_BY_ROOT_CAUSE,
    get_payer_info,
)


def _make_case(carc: str = "50", payer: str = "Aetna Health Inc") -> Case:
    case = Case(
        batch_id=1,
        payer=payer,
        patient_ref="CLM-12345",
        cpt_hcpcs="99213",
        icd10="I10",
        billed_amt=250.0,
        carc=carc,
        state=CaseState.approved,
    )
    case.id = 1
    return case


def _make_diagnosis(root_cause: str = "medical_necessity") -> Diagnosis:
    d = Diagnosis(
        case_id=1,
        root_cause=root_cause,
        winnability_score=0.65,
        expected_value=110.0,
        rationale="Service is medically necessary per clinical guidelines.",
        model_version="claude-sonnet-4-6",
    )
    return d


def _mock_llm(text_response: str = "Dear Payer,\n\nWe appeal this claim.\n\nSincerely, Practice") -> LLMProvider:
    mock = AsyncMock(spec=LLMProvider)
    mock.complete.return_value = LLMResponse(
        content=text_response,
        input_tokens=100,
        output_tokens=50,
        model="claude-sonnet-4-6",
    )
    mock.complete_json.return_value = {
        "claim_summary": "Claim CLM-12345 was denied.",
        "denial_reason": "Medical necessity not established.",
        "the_ask": "Please reconsider and approve for payment.",
        "phone_tree": "Press 1 for Providers, then 2 for Claims.",
        "talking_points": ["Point 1", "Point 2", "Point 3"],
        "escalation_trigger": "Ask for supervisor if rep cannot approve.",
        "reference_numbers": ["CLM-12345"],
    }
    return mock


async def test_draft_appeal_returns_draft_result():
    agent = DraftingAgent(_mock_llm(), practice_name="Test Practice")
    case = _make_case()
    diagnosis = _make_diagnosis()
    result = await agent.draft_appeal(case, diagnosis)
    assert result.draft_type == DraftType.appeal
    assert len(result.content) > 0
    assert len(result.attachments) > 0


async def test_draft_call_packet_returns_structured():
    agent = DraftingAgent(_mock_llm(), practice_name="Test Practice")
    case = _make_case()
    diagnosis = _make_diagnosis()
    result = await agent.draft_call_packet(case, diagnosis)
    assert result.draft_type == DraftType.call_packet
    parsed = json.loads(result.content)
    assert "talking_points" in parsed
    assert isinstance(parsed["talking_points"], list)


async def test_draft_fallback_on_llm_error():
    mock = AsyncMock(spec=LLMProvider)
    mock.complete.side_effect = Exception("LLM unavailable")
    mock.complete_json.side_effect = Exception("LLM unavailable")

    agent = DraftingAgent(mock, practice_name="Test Practice")
    case = _make_case()
    diagnosis = _make_diagnosis()
    result = await agent.draft_appeal(case, diagnosis)

    assert result.draft_type == DraftType.appeal
    assert "CLM-12345" in result.content


async def test_draft_all_coding_error():
    agent = DraftingAgent(_mock_llm(), practice_name="Test Practice")
    case = _make_case(carc="11")
    diagnosis = _make_diagnosis(root_cause="coding_error")
    results = await agent.draft_all(case, diagnosis)
    types = {r.draft_type for r in results}
    assert DraftType.appeal in types
    assert DraftType.corrected_claim in types
    assert DraftType.call_packet in types
    assert len(results) == 3


async def test_draft_all_medical_necessity():
    agent = DraftingAgent(_mock_llm(), practice_name="Test Practice")
    case = _make_case(carc="50")
    diagnosis = _make_diagnosis(root_cause="medical_necessity")
    results = await agent.draft_all(case, diagnosis)
    types = {r.draft_type for r in results}
    assert DraftType.appeal in types
    assert DraftType.call_packet in types
    assert DraftType.corrected_claim not in types
    assert len(results) == 2


def test_select_draft_types_coding_error():
    agent = DraftingAgent(_mock_llm())
    types = agent._select_draft_types(RootCause.coding_error)
    assert DraftType.corrected_claim in types
    assert DraftType.appeal in types
    assert DraftType.call_packet in types


def test_required_docs_by_root_cause():
    for rc in RootCause:
        assert rc in REQUIRED_DOCS_BY_ROOT_CAUSE, f"Missing docs for {rc}"
        assert len(REQUIRED_DOCS_BY_ROOT_CAUSE[rc]) > 0


def test_get_payer_info_known():
    info = get_payer_info("BlueCross BlueShield of California")
    assert "appeal_phone" in info
    assert info["appeal_phone"] == "1-800-676-2583"


def test_get_payer_info_unknown():
    info = get_payer_info("Random Payer Inc")
    assert "appeal_phone" in info
    assert "deadline_days" in info
