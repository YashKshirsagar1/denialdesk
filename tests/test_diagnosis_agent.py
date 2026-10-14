"""Tests for DiagnosisAgent — all LLM calls are mocked."""
import pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from denialdesk.agents.diagnosis_agent import (
    CARC_ROOT_CAUSE,
    DiagnosisAgent,
    RootCause,
)
from denialdesk.llm.base import LLMMessage, LLMProvider, LLMResponse


def _make_case(
    carc: str = "16",
    rarc: str = "MA01",
    cpt: str = "99213",
    icd10: str = "I10",
    payer: str = "Aetna Health Inc",
    billed_amt: float = 300.0,
    denial_date: datetime | None = None,
    filing_deadline: datetime | None = None,
    case_id: int = 1,
):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=case_id,
        carc=carc,
        rarc=rarc,
        cpt_hcpcs=cpt,
        icd10=icd10,
        billed_amt=billed_amt,
        allowed_amt=0.0,
        payer=payer,
        denial_date=denial_date or (now - timedelta(days=30)),
        filing_deadline=filing_deadline or (now + timedelta(days=60)),
        state="ingested",
    )


class MockLLMProvider(LLMProvider):
    def __init__(self, response_dict: dict | None = None, raise_exc: Exception | None = None):
        self._response = response_dict
        self._raise = raise_exc

    async def complete(self, messages, system=None, max_tokens=2048):
        return LLMResponse(content="{}", input_tokens=0, output_tokens=0, model="mock")

    async def complete_json(self, messages, system=None, max_tokens=2048):
        if self._raise:
            raise self._raise
        return self._response if self._response is not None else {}


# ---------------------------------------------------------------------------
# Rule-based scoring tests
# ---------------------------------------------------------------------------

def test_rule_based_score_carc_29_expired():
    agent = DiagnosisAgent(MockLLMProvider())
    past = datetime.now(timezone.utc) - timedelta(days=5)
    case = _make_case(carc="29", filing_deadline=past)
    cause, score = agent._rule_based_score(case)
    assert cause == RootCause.timely_filing
    assert score < 0.2


def test_rule_based_score_carc_29_active():
    agent = DiagnosisAgent(MockLLMProvider())
    future = datetime.now(timezone.utc) + timedelta(days=60)
    case = _make_case(carc="29", filing_deadline=future)
    cause, score = agent._rule_based_score(case)
    assert cause == RootCause.timely_filing
    assert score > 0.5


def test_rule_based_score_carc_16():
    agent = DiagnosisAgent(MockLLMProvider())
    case = _make_case(carc="16")
    cause, score = agent._rule_based_score(case)
    assert cause == RootCause.missing_info
    assert score > 0.6


def test_rule_based_score_carc_4():
    agent = DiagnosisAgent(MockLLMProvider())
    case = _make_case(carc="4")
    cause, score = agent._rule_based_score(case)
    assert cause == RootCause.not_covered
    assert score < 0.3


def test_unknown_carc_falls_back_to_other():
    agent = DiagnosisAgent(MockLLMProvider())
    case = _make_case(carc="999")
    cause, score = agent._rule_based_score(case)
    assert cause == RootCause.other
    # Score should be base 0.5 with no adjustment
    assert 0.45 <= score <= 0.55


# ---------------------------------------------------------------------------
# LLM integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_diagnose_uses_llm_result():
    llm_payload = {
        "root_cause": "coding_error",
        "confidence": 0.9,
        "rationale": "The CPT and ICD-10 codes are mismatched.",
        "winnable": True,
        "winnability_score": 0.75,
        "expected_value_pct": 0.8,
        "decline_reason": None,
    }
    agent = DiagnosisAgent(MockLLMProvider(response_dict=llm_payload), model_version="test-model")
    case = _make_case(carc="11")
    diagnosis = await agent.diagnose(case)
    assert diagnosis.root_cause == "coding_error"
    assert abs(diagnosis.winnability_score - 0.75) < 0.01
    assert "mismatched" in diagnosis.rationale


@pytest.mark.asyncio
async def test_diagnose_falls_back_on_llm_error():
    agent = DiagnosisAgent(
        MockLLMProvider(raise_exc=Exception("API timeout")),
        model_version="test-model",
    )
    case = _make_case(carc="16")
    # Should not raise — falls back to rule-based
    diagnosis = await agent.diagnose(case)
    assert diagnosis.root_cause == RootCause.missing_info.value
    assert diagnosis.winnability_score > 0.6


@pytest.mark.asyncio
async def test_diagnose_batch_runs_concurrently():
    agent = DiagnosisAgent(MockLLMProvider(), model_version="test-model")
    cases = [_make_case(carc="16", case_id=i) for i in range(1, 4)]
    diagnoses = await agent.diagnose_batch(cases)
    assert len(diagnoses) == 3


@pytest.mark.asyncio
async def test_diagnosis_orm_fields():
    agent = DiagnosisAgent(MockLLMProvider(), model_version="v-test")
    case = _make_case(carc="50", case_id=42)
    diagnosis = await agent.diagnose(case)
    assert diagnosis.case_id == 42
    assert diagnosis.root_cause is not None
    assert diagnosis.winnability_score is not None
    assert 0.0 <= diagnosis.winnability_score <= 1.0
    assert diagnosis.expected_value is not None
    assert diagnosis.rationale is not None
    assert diagnosis.model_version == "v-test"


@pytest.mark.asyncio
async def test_diagnose_unknown_llm_root_cause_falls_back():
    """If LLM returns a root_cause value not in the enum, use rule-based."""
    llm_payload = {
        "root_cause": "totally_made_up_value",
        "confidence": 0.9,
        "rationale": "Some rationale.",
        "winnable": True,
        "winnability_score": 0.8,
        "expected_value_pct": 0.7,
        "decline_reason": None,
    }
    agent = DiagnosisAgent(MockLLMProvider(response_dict=llm_payload))
    case = _make_case(carc="16")
    diagnosis = await agent.diagnose(case)
    # Should have fallen back to rule-based root cause
    assert diagnosis.root_cause == RootCause.missing_info.value
