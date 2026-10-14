import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import timezone

from denialdesk.agents.diagnosis_agent import RootCause
from denialdesk.agents.prompts.drafting import (
    build_appeal_system_prompt,
    build_appeal_user_prompt,
    build_call_packet_system_prompt,
    build_call_packet_user_prompt,
    build_corrected_claim_system_prompt,
    build_corrected_claim_user_prompt,
)
from denialdesk.data.carc_descriptions import CARC_DESCRIPTIONS
from denialdesk.llm.base import LLMMessage, LLMProvider
from denialdesk.models.case import Case, Diagnosis
from denialdesk.templates.payer_templates import (
    DraftType,
    REQUIRED_DOCS_BY_ROOT_CAUSE,
    get_payer_info,
)

logger = logging.getLogger(__name__)


@dataclass
class DraftResult:
    draft_type: DraftType
    content: str
    attachments: list[str]
    payer_info: dict
    version: int = 1


def _fallback_appeal(payer: str, claim_number: str, carc: str, patient_ref: str) -> str:
    carc_desc = CARC_DESCRIPTIONS.get(carc, f"CARC {carc}")
    return (
        f"RE: Appeal for Claim Number {claim_number}\n"
        f"Patient Reference: {patient_ref}\n\n"
        f"Dear {payer} Appeals Department,\n\n"
        f"We are writing to formally appeal the denial of the above-referenced claim. "
        f"The claim was denied with reason code CARC {carc}: {carc_desc}.\n\n"
        f"We respectfully request reconsideration of this claim and full payment of the "
        f"billed amount. Supporting documentation is enclosed.\n\n"
        f"Please contact our billing department with any questions.\n\n"
        f"Sincerely,\n[Practice Billing Department]"
    )


def _fallback_call_packet(payer: str, claim_number: str, carc: str, phone_tree: str) -> str:
    carc_desc = CARC_DESCRIPTIONS.get(carc, f"CARC {carc}")
    packet = {
        "claim_summary": f"Claim {claim_number} was denied by {payer} with CARC {carc}: {carc_desc}.",
        "denial_reason": carc_desc,
        "the_ask": "Please reconsider this claim and process for payment.",
        "phone_tree": phone_tree,
        "talking_points": [
            f"Claim number: {claim_number}",
            f"Denial reason: CARC {carc} — {carc_desc}",
            "Request immediate reconsideration",
            "Ask for reference number for this call",
        ],
        "escalation_trigger": "If representative cannot approve reconsideration, ask for a supervisor.",
        "reference_numbers": [claim_number],
    }
    return json.dumps(packet)


def _fallback_corrected_claim(payer: str, claim_number: str, carc: str, patient_ref: str) -> str:
    carc_desc = CARC_DESCRIPTIONS.get(carc, f"CARC {carc}")
    return (
        f"RE: Corrected Claim for Original Claim Number {claim_number}\n"
        f"Patient Reference: {patient_ref}\n\n"
        f"Dear {payer} Claims Department,\n\n"
        f"Please find enclosed a corrected claim for the above-referenced account. "
        f"The original claim was denied due to: {carc_desc}. "
        f"We have corrected the identified issue and resubmit herewith for processing.\n\n"
        f"Please process this corrected claim at your earliest convenience.\n\n"
        f"Sincerely,\n[Practice Billing Department]"
    )


class DraftingAgent:
    def __init__(self, llm_provider: LLMProvider, practice_name: str = "Unknown Practice") -> None:
        self.llm = llm_provider
        self.practice_name = practice_name

    def _select_draft_types(self, root_cause: RootCause) -> list[DraftType]:
        if root_cause == RootCause.coding_error:
            return [DraftType.appeal, DraftType.corrected_claim, DraftType.call_packet]
        return [DraftType.appeal, DraftType.call_packet]

    def _case_dos_str(self, case: Case) -> str:
        if case.dos:
            d = case.dos
            if hasattr(d, "strftime"):
                return d.strftime("%Y-%m-%d")
        return "Unknown"

    def _case_deadline_str(self, case: Case, payer_info: dict) -> str:
        if case.filing_deadline:
            d = case.filing_deadline
            if hasattr(d, "strftime"):
                return d.strftime("%Y-%m-%d")
        return f"{payer_info.get('deadline_days', 180)} days from denial date"

    def _attachments(self, case: Case) -> list[str]:
        try:
            rc = RootCause(case.diagnosis.root_cause if case.diagnosis else "other")
        except (ValueError, AttributeError):
            rc = RootCause.other
        return REQUIRED_DOCS_BY_ROOT_CAUSE.get(rc, ["supporting_documentation"])

    def _root_cause_from_diagnosis(self, diagnosis: Diagnosis) -> RootCause:
        try:
            return RootCause(diagnosis.root_cause or "other")
        except ValueError:
            return RootCause.other

    async def draft_appeal(self, case: Case, diagnosis: Diagnosis) -> DraftResult:
        payer_info = get_payer_info(case.payer or "")
        root_cause = self._root_cause_from_diagnosis(diagnosis)
        attachments = REQUIRED_DOCS_BY_ROOT_CAUSE.get(root_cause, ["supporting_documentation"])
        carc = case.carc or ""
        icd10 = [c.strip() for c in (case.icd10 or "").split(",") if c.strip()]

        try:
            system = build_appeal_system_prompt()
            user_msg = build_appeal_user_prompt(
                practice_name=self.practice_name,
                payer=case.payer or "",
                claim_number=case.patient_ref or str(case.id),
                patient_ref=case.patient_ref or "Unknown",
                dos=self._case_dos_str(case),
                cpt=case.cpt_hcpcs or "",
                icd10=icd10,
                billed_amt=float(case.billed_amt or 0),
                carc=carc,
                carc_description=CARC_DESCRIPTIONS.get(carc, f"CARC {carc}"),
                root_cause=root_cause.value,
                rationale=diagnosis.rationale or "",
                required_docs=attachments,
                payer_address=payer_info.get("appeal_address", ""),
                appeal_deadline=self._case_deadline_str(case, payer_info),
            )
            response = await self.llm.complete(
                messages=[LLMMessage(role="user", content=user_msg)],
                system=system,
                max_tokens=1500,
            )
            content = response.content
        except Exception as exc:
            logger.warning("LLM appeal draft failed for case %s: %s", case.id, exc)
            content = _fallback_appeal(
                payer=case.payer or "",
                claim_number=case.patient_ref or str(case.id),
                carc=carc,
                patient_ref=case.patient_ref or "Unknown",
            )

        return DraftResult(
            draft_type=DraftType.appeal,
            content=content,
            attachments=attachments,
            payer_info=payer_info,
        )

    async def draft_call_packet(self, case: Case, diagnosis: Diagnosis) -> DraftResult:
        payer_info = get_payer_info(case.payer or "")
        root_cause = self._root_cause_from_diagnosis(diagnosis)
        attachments = REQUIRED_DOCS_BY_ROOT_CAUSE.get(root_cause, ["supporting_documentation"])
        carc = case.carc or ""

        try:
            system = build_call_packet_system_prompt()
            user_msg = build_call_packet_user_prompt(
                payer=case.payer or "",
                claim_number=case.patient_ref or str(case.id),
                patient_ref=case.patient_ref or "Unknown",
                dos=self._case_dos_str(case),
                cpt=case.cpt_hcpcs or "",
                billed_amt=float(case.billed_amt or 0),
                carc=carc,
                root_cause=root_cause.value,
                rationale=diagnosis.rationale or "",
                phone_tree=payer_info.get("phone_tree", ""),
            )
            result_dict = await self.llm.complete_json(
                messages=[LLMMessage(role="user", content=user_msg)],
                system=system,
                max_tokens=800,
            )
            content = json.dumps(result_dict)
        except Exception as exc:
            logger.warning("LLM call packet draft failed for case %s: %s", case.id, exc)
            content = _fallback_call_packet(
                payer=case.payer or "",
                claim_number=case.patient_ref or str(case.id),
                carc=carc,
                phone_tree=payer_info.get("phone_tree", ""),
            )

        return DraftResult(
            draft_type=DraftType.call_packet,
            content=content,
            attachments=attachments,
            payer_info=payer_info,
        )

    async def draft_corrected_claim(self, case: Case, diagnosis: Diagnosis) -> DraftResult:
        payer_info = get_payer_info(case.payer or "")
        root_cause = self._root_cause_from_diagnosis(diagnosis)
        attachments = REQUIRED_DOCS_BY_ROOT_CAUSE.get(root_cause, ["supporting_documentation"])
        carc = case.carc or ""
        icd10 = [c.strip() for c in (case.icd10 or "").split(",") if c.strip()]

        try:
            system = build_corrected_claim_system_prompt()
            user_msg = build_corrected_claim_user_prompt(
                payer=case.payer or "",
                claim_number=case.patient_ref or str(case.id),
                patient_ref=case.patient_ref or "Unknown",
                dos=self._case_dos_str(case),
                cpt=case.cpt_hcpcs or "",
                icd10=icd10,
                billed_amt=float(case.billed_amt or 0),
                root_cause=root_cause.value,
                rationale=diagnosis.rationale or "",
            )
            response = await self.llm.complete(
                messages=[LLMMessage(role="user", content=user_msg)],
                system=system,
                max_tokens=1000,
            )
            content = response.content
        except Exception as exc:
            logger.warning("LLM corrected claim draft failed for case %s: %s", case.id, exc)
            content = _fallback_corrected_claim(
                payer=case.payer or "",
                claim_number=case.patient_ref or str(case.id),
                carc=carc,
                patient_ref=case.patient_ref or "Unknown",
            )

        return DraftResult(
            draft_type=DraftType.corrected_claim,
            content=content,
            attachments=attachments,
            payer_info=payer_info,
        )

    async def draft_all(self, case: Case, diagnosis: Diagnosis) -> list[DraftResult]:
        root_cause = self._root_cause_from_diagnosis(diagnosis)
        draft_types = self._select_draft_types(root_cause)

        tasks = []
        for dt in draft_types:
            if dt == DraftType.appeal:
                tasks.append(self.draft_appeal(case, diagnosis))
            elif dt == DraftType.corrected_claim:
                tasks.append(self.draft_corrected_claim(case, diagnosis))
            elif dt == DraftType.call_packet:
                tasks.append(self.draft_call_packet(case, diagnosis))

        return list(await asyncio.gather(*tasks))
