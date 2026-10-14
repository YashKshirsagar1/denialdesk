"""Tests for PDF export — no DB needed."""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from denialdesk.export.call_packet_generator import CallPacketData, generate_call_packet_pdf
from denialdesk.export.pdf_generator import LetterMetadata, generate_appeal_pdf
from denialdesk.export.packet_builder import PacketBuilder
from denialdesk.models.case import Case, CaseState, Diagnosis, Draft


def _make_metadata() -> LetterMetadata:
    return LetterMetadata(
        practice_name="Riverside Internal Medicine",
        practice_address="123 Main St, Springfield, CA 90001",
        practice_phone="(555) 123-4567",
        practice_npi="1234567890",
        payer_name="Aetna Health Inc",
        payer_address="P.O. Box 14463, Lexington, KY 40512",
        date="October 14, 2026",
        re_line="RE: Appeal – Claim #42, Patient: PT-001, DOS: 08/01/2026",
        subject="FORMAL APPEAL OF CLAIM DENIAL",
    )


def _make_call_data() -> CallPacketData:
    return CallPacketData(
        payer_name="Aetna Health Inc",
        payer_phone="1-800-872-3862",
        phone_tree="Press 1 for Providers, then 2 for Claims, then 1 for Appeals",
        claim_number="42",
        patient_ref="PT-001",
        dos="08/01/2026",
        cpt="99213",
        billed_amt=500.0,
        denial_reason="Missing information on claim",
        the_ask="Request reconsideration with corrected claim form attached",
        talking_points=[
            "Claim was denied for missing info (CARC 16).",
            "We have corrected the missing fields and are resubmitting.",
            "Please confirm receipt and provide a reference number.",
        ],
        escalation_trigger="Rep cannot confirm they received the corrected claim.",
        reference_numbers=["Claim #42", "Auth #XYZ123"],
        prepared_date="October 14, 2026",
    )


def _make_case() -> Case:
    case = MagicMock(spec=Case)
    case.id = 42
    case.payer = "Aetna Health Inc"
    case.patient_ref = "PT-001"
    case.dos = datetime(2026, 8, 1, tzinfo=timezone.utc)
    case.denial_date = datetime(2026, 9, 1, tzinfo=timezone.utc)
    case.cpt_hcpcs = "99213"
    case.icd10 = "I10"
    case.billed_amt = 500.0
    case.allowed_amt = 0.0
    case.carc = "16"
    case.rarc = "MA01"
    case.state = CaseState.awaiting_human_review
    return case


def _make_diagnosis() -> Diagnosis:
    diag = MagicMock(spec=Diagnosis)
    diag.root_cause = "missing_info"
    diag.winnability_score = 0.7
    diag.expected_value = 350.0
    diag.rationale = "Missing info on claim — fixable."
    diag.model_version = "rule_v1"
    return diag


def _make_draft(content: str = "We are writing to appeal...", draft_type: str = "appeal") -> Draft:
    draft = MagicMock(spec=Draft)
    draft.type = draft_type
    draft.content = content
    draft.attachments = json.dumps(["clinical_notes", "physician_letter"])
    draft.version = 1
    return draft


# ---------------------------------------------------------------------------
# appeal PDF tests
# ---------------------------------------------------------------------------

def test_generate_appeal_pdf_returns_bytes():
    result = generate_appeal_pdf(_make_metadata(), "Appeal body text.", ["clinical_notes"])
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


def test_appeal_pdf_nonzero_size():
    result = generate_appeal_pdf(_make_metadata(), "Appeal body text.", ["clinical_notes"])
    assert len(result) > 1000


def test_appeal_pdf_multiple_paragraphs():
    body = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    result = generate_appeal_pdf(_make_metadata(), body, [])
    assert isinstance(result, bytes)
    assert len(result) > 1000


def test_appeal_pdf_no_attachments():
    result = generate_appeal_pdf(_make_metadata(), "Body text.", [])
    assert result[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# call packet PDF tests
# ---------------------------------------------------------------------------

def test_generate_call_packet_pdf_returns_bytes():
    result = generate_call_packet_pdf(_make_call_data())
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


def test_call_packet_pdf_nonzero_size():
    result = generate_call_packet_pdf(_make_call_data())
    assert len(result) > 1000


def test_call_packet_pdf_no_reference_numbers():
    data = _make_call_data()
    data.reference_numbers = []
    result = generate_call_packet_pdf(data)
    assert result[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# PacketBuilder tests
# ---------------------------------------------------------------------------

def test_packet_builder_returns_both_pdfs():
    builder = PacketBuilder()
    packet = builder.build_packet(
        case=_make_case(),
        diagnosis=_make_diagnosis(),
        draft=_make_draft(),
    )
    assert isinstance(packet.appeal_pdf, bytes)
    assert len(packet.appeal_pdf) > 1000
    assert packet.appeal_pdf[:4] == b"%PDF"
    assert isinstance(packet.call_packet_pdf, bytes)
    assert len(packet.call_packet_pdf) > 1000
    assert packet.call_packet_pdf[:4] == b"%PDF"


def test_packet_builder_no_practice():
    builder = PacketBuilder()
    # Should not raise; uses placeholder values
    packet = builder.build_packet(
        case=_make_case(),
        diagnosis=_make_diagnosis(),
        draft=_make_draft(),
        practice=None,
    )
    assert packet.appeal_pdf[:4] == b"%PDF"
    assert packet.call_packet_pdf[:4] == b"%PDF"


def test_packet_builder_no_diagnosis():
    builder = PacketBuilder()
    packet = builder.build_packet(
        case=_make_case(),
        diagnosis=None,
        draft=_make_draft(),
    )
    assert packet.appeal_pdf[:4] == b"%PDF"


def test_packet_builder_call_packet_draft_parsed():
    """If the draft is a call_packet type with JSON content, it should be used."""
    cp_content = json.dumps({
        "denial_reason": "Timely filing exceeded",
        "the_ask": "Request timely filing exception",
        "talking_points": ["Point A", "Point B"],
        "escalation_trigger": "They refuse to grant exception.",
        "reference_numbers": ["CLM-999"],
    })
    draft = _make_draft(content=cp_content, draft_type="call_packet")
    builder = PacketBuilder()
    packet = builder.build_packet(case=_make_case(), diagnosis=_make_diagnosis(), draft=draft)
    assert packet.call_packet_pdf[:4] == b"%PDF"


def test_packet_builder_attachments_checklist():
    builder = PacketBuilder()
    packet = builder.build_packet(
        case=_make_case(),
        diagnosis=_make_diagnosis(),
        draft=_make_draft(),
    )
    assert "clinical_notes" in packet.attachments_checklist
    assert "physician_letter" in packet.attachments_checklist


def test_packet_builder_bad_attachments_json():
    """Malformed attachments JSON should not raise."""
    draft = _make_draft()
    draft.attachments = "not-json"
    builder = PacketBuilder()
    packet = builder.build_packet(case=_make_case(), diagnosis=_make_diagnosis(), draft=draft)
    assert packet.appeal_pdf[:4] == b"%PDF"
    assert packet.attachments_checklist == []
