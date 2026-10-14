import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from denialdesk.export.call_packet_generator import CallPacketData, generate_call_packet_pdf
from denialdesk.export.pdf_generator import LetterMetadata, generate_appeal_pdf
from denialdesk.models.case import Case, Diagnosis, Draft, Practice
from denialdesk.templates.payer_templates import get_payer_info


@dataclass
class SubmissionPacket:
    case_id: int
    appeal_pdf: bytes
    call_packet_pdf: bytes
    attachments_checklist: list[str]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PacketBuilder:
    def build_packet(
        self,
        case: Case,
        diagnosis: Diagnosis | None,
        draft: Draft,
        practice: Practice | None = None,
    ) -> SubmissionPacket:
        """Build appeal + call packet PDFs and return a SubmissionPacket."""
        # Practice defaults
        practice_name = practice.name if practice else "Your Practice Name"
        practice_address = "Address on file"
        practice_phone = "Phone on file"
        practice_npi = "NPI on file"
        if practice and practice.contact:
            try:
                contact = json.loads(practice.contact)
                practice_address = contact.get("address", practice_address)
                practice_phone = contact.get("phone", practice_phone)
                practice_npi = contact.get("npi", practice_npi)
            except (json.JSONDecodeError, TypeError):
                pass

        payer_info = get_payer_info(case.payer or "")
        payer_address = payer_info.get("appeal_address", "Appeals Department")

        # Attachments
        raw_attachments = draft.attachments or "[]"
        if isinstance(raw_attachments, str):
            try:
                attachments = json.loads(raw_attachments)
            except (json.JSONDecodeError, ValueError):
                attachments = []
        else:
            attachments = list(raw_attachments)

        # Dates
        denial_date = case.denial_date
        dos_str = case.dos.strftime("%m/%d/%Y") if case.dos else "Unknown"
        denial_date_str = denial_date.strftime("%m/%d/%Y") if denial_date else "Unknown"
        today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

        claim_number = str(case.id)
        patient_ref = case.patient_ref or "N/A"
        payer_name = case.payer or "Unknown Payer"
        cpt = case.cpt_hcpcs or "Unknown"
        billed_amt = float(case.billed_amt or 0)
        carc = case.carc or "Unknown"
        root_cause = diagnosis.root_cause if diagnosis else "unknown"
        rationale = diagnosis.rationale if diagnosis else "See claim details."

        # Build appeal PDF
        metadata = LetterMetadata(
            practice_name=practice_name,
            practice_address=practice_address,
            practice_phone=practice_phone,
            practice_npi=practice_npi,
            payer_name=payer_name,
            payer_address=payer_address,
            date=today_str,
            re_line=f"RE: Appeal – Claim #{claim_number}, Patient: {patient_ref}, DOS: {dos_str}",
            subject="FORMAL APPEAL OF CLAIM DENIAL",
        )
        appeal_body = draft.content or self._default_appeal_body(
            payer_name, claim_number, carc, rationale
        )
        appeal_pdf = generate_appeal_pdf(metadata, appeal_body, attachments)

        # Build call packet PDF
        # Try to parse call packet JSON from a call_packet draft; fall back to case fields
        call_data = self._build_call_packet_data(
            case=case,
            diagnosis=diagnosis,
            payer_info=payer_info,
            claim_number=claim_number,
            patient_ref=patient_ref,
            dos_str=dos_str,
            cpt=cpt,
            billed_amt=billed_amt,
            carc=carc,
            root_cause=root_cause,
            today_str=today_str,
            draft=draft,
        )
        call_pdf = generate_call_packet_pdf(call_data)

        return SubmissionPacket(
            case_id=case.id,
            appeal_pdf=appeal_pdf,
            call_packet_pdf=call_pdf,
            attachments_checklist=attachments,
        )

    def _build_call_packet_data(
        self, *, case, diagnosis, payer_info, claim_number, patient_ref,
        dos_str, cpt, billed_amt, carc, root_cause, today_str, draft,
    ) -> CallPacketData:
        # Try to parse call packet JSON if draft is a call_packet type
        parsed = {}
        if draft.type == "call_packet" and draft.content:
            try:
                parsed = json.loads(draft.content)
            except (json.JSONDecodeError, ValueError):
                parsed = {}

        denial_reason = parsed.get(
            "denial_reason",
            f"CARC {carc}: {root_cause.replace('_', ' ').title()}"
        )
        the_ask = parsed.get(
            "the_ask",
            f"Request reconsideration of claim #{claim_number} denied under CARC {carc}."
        )
        talking_points = parsed.get("talking_points") or [
            f"Claim #{claim_number} was denied with CARC code {carc}.",
            f"The denial reason is: {denial_reason}.",
            "We believe this denial is incorrect and request reconsideration.",
            "Please confirm receipt and provide a reference number.",
        ]
        escalation_trigger = parsed.get(
            "escalation_trigger",
            "Representative cannot confirm reconsideration or provides no timeline."
        )
        reference_numbers = parsed.get("reference_numbers") or [f"Claim #{claim_number}"]
        phone_tree = payer_info.get("phone_tree", "Ask for Provider Services / Appeals")
        payer_phone = payer_info.get("appeal_phone", "See insurance card")

        return CallPacketData(
            payer_name=case.payer or "Unknown Payer",
            payer_phone=payer_phone,
            phone_tree=phone_tree,
            claim_number=claim_number,
            patient_ref=patient_ref,
            dos=dos_str,
            cpt=cpt,
            billed_amt=billed_amt,
            denial_reason=denial_reason,
            the_ask=the_ask,
            talking_points=talking_points,
            escalation_trigger=escalation_trigger,
            reference_numbers=reference_numbers,
            prepared_date=today_str,
        )

    def _default_appeal_body(self, payer: str, claim_number: str, carc: str, rationale: str) -> str:
        return (
            f"We are writing to formally appeal the denial of claim #{claim_number} "
            f"submitted to {payer}. The claim was denied under CARC code {carc}.\n\n"
            f"Our review of this denial indicates the following: {rationale}\n\n"
            "We respectfully request that you reconsider this claim in light of the "
            "supporting documentation enclosed with this appeal. The services rendered "
            "were medically necessary and covered under the patient's benefit plan.\n\n"
            "Please contact our office at your earliest convenience to confirm receipt "
            "of this appeal and provide a reference number for tracking purposes. "
            "We expect a determination within the timeframe specified by your appeals policy."
        )
