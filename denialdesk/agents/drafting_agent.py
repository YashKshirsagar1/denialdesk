import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import date, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.agents.diagnosis_agent import RootCause
from denialdesk.agents.prompts.drafting import (
    build_appeal_system_prompt,
    build_appeal_user_prompt,
    build_call_packet_system_prompt,
    build_call_packet_user_prompt,
    build_corrected_claim_system_prompt,
    build_corrected_claim_user_prompt,
)
from denialdesk.agents.rarc_codes import get_rarc_description
from denialdesk.data.carc_descriptions import CARC_DESCRIPTIONS
from denialdesk.llm.base import LLMMessage, LLMProvider
from denialdesk.models.case import Case, Diagnosis
from denialdesk.repositories.playbook_repository import PlaybookRepository
from denialdesk.templates.payer_templates import (
    DraftType,
    REQUIRED_DOCS_BY_ROOT_CAUSE,
    get_payer_info,
    normalize_payer_name,
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
        f"RE: Appeal for Claim {claim_number}\n"
        f"Patient Reference: {patient_ref}\n\n"
        f"Dear {payer} Appeals Department,\n\n"
        f"We are formally appealing the denial of the above-referenced claim. "
        f"The claim was denied with reason code CARC {carc}: {carc_desc}.\n\n"
        f"We respectfully request reconsideration and full payment of the billed amount. "
        f"Supporting documentation is enclosed.\n\n"
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
        f"RE: Corrected Claim for Original Claim {claim_number}\n"
        f"Patient Reference: {patient_ref}\n\n"
        f"Dear {payer} Claims Department,\n\n"
        f"Please find enclosed a corrected claim. "
        f"The original claim was denied due to: {carc_desc}. "
        f"We have corrected the identified issue and resubmit herewith.\n\n"
        f"Sincerely,\n[Practice Billing Department]"
    )


class DraftingAgent:
    def __init__(
        self,
        llm_provider: LLMProvider,
        practice_name: str = "Unknown Practice",
        session: AsyncSession | None = None,
    ) -> None:
        self.llm = llm_provider
        self.practice_name = practice_name
        self._session = session

    def _select_draft_types(self, root_cause: RootCause) -> list[DraftType]:
        if root_cause == RootCause.coding_error:
            return [DraftType.appeal, DraftType.corrected_claim, DraftType.call_packet]
        return [DraftType.appeal, DraftType.call_packet]

    def _case_dos_str(self, case: Case) -> str:
        if case.dos and hasattr(case.dos, "strftime"):
            return case.dos.strftime("%Y-%m-%d")
        return "[MISSING: date of service]"

    def _case_deadline_str(self, case: Case, payer_info: dict) -> str:
        if case.filing_deadline and hasattr(case.filing_deadline, "strftime"):
            return case.filing_deadline.strftime("%Y-%m-%d")
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

    async def _get_playbook_strategy(self, payer: str, carc: str, specialty: str) -> str:
        """Fetch winning strategy from the playbook, if any prior wins exist."""
        if self._session is None:
            return ""
        try:
            repo = PlaybookRepository(self._session)
            canonical_payer = normalize_payer_name(payer)
            entry = await repo.get_strategy(canonical_payer, carc, specialty or None)
            if entry and entry.success_count > 0 and entry.winning_strategy:
                rate = entry.success_count / max(entry.attempt_count, 1)
                return (
                    f"Prior win rate for {canonical_payer} + CARC {carc}: "
                    f"{entry.success_count}/{entry.attempt_count} ({rate:.0%}). "
                    f"Winning approach: {entry.winning_strategy}"
                )
        except Exception as exc:
            logger.debug("Playbook lookup failed: %s", exc)
        return ""

    async def draft_appeal(
        self,
        case: Case,
        diagnosis: Diagnosis,
        specialty: str = "",
    ) -> DraftResult:
        payer_info = get_payer_info(case.payer or "")
        root_cause = self._root_cause_from_diagnosis(diagnosis)
        attachments = REQUIRED_DOCS_BY_ROOT_CAUSE.get(root_cause, ["supporting_documentation"])
        carc = case.carc or ""
        rarc = getattr(case, "rarc", "") or ""
        icd10 = [c.strip() for c in (case.icd10 or "").split(",") if c.strip()]
        today = date.today().strftime("%B %d, %Y")

        claim_number = getattr(case, "claim_number", None) or case.patient_ref or str(case.id)
        modifier = getattr(case, "modifier", "") or ""
        rendering_npi = getattr(case, "rendering_provider_npi", "") or ""
        billing_tin = getattr(case, "billing_provider_tin", "") or ""

        playbook_strategy = await self._get_playbook_strategy(case.payer or "", carc, specialty)

        try:
            system = build_appeal_system_prompt()
            user_msg = build_appeal_user_prompt(
                practice_name=self.practice_name,
                payer=case.payer or "",
                payer_address=payer_info.get("appeal_address", ""),
                appeal_form=payer_info.get("appeal_form", "Provider Claim Appeal Form"),
                claim_number=claim_number,
                patient_ref=case.patient_ref or "[MISSING: patient reference]",
                dos=self._case_dos_str(case),
                cpt=case.cpt_hcpcs or "[MISSING: CPT code]",
                modifier=modifier,
                icd10=icd10,
                billed_amt=float(case.billed_amt or 0),
                carc=carc,
                carc_description=CARC_DESCRIPTIONS.get(carc, f"CARC {carc}"),
                rarc=rarc,
                rarc_description=get_rarc_description(rarc),
                rendering_npi=rendering_npi,
                billing_tin=billing_tin,
                root_cause=root_cause.value,
                rationale=diagnosis.rationale or "",
                required_docs=attachments,
                appeal_deadline=self._case_deadline_str(case, payer_info),
                playbook_strategy=playbook_strategy,
                today=today,
            )
            response = await self.llm.complete(
                messages=[LLMMessage(role="user", content=user_msg)],
                system=system,
                max_tokens=2000,
            )
            content = response.content
        except Exception as exc:
            logger.warning("LLM appeal draft failed for case %s: %s", case.id, exc)
            content = _fallback_appeal(
                payer=case.payer or "",
                claim_number=claim_number,
                carc=carc,
                patient_ref=case.patient_ref or "Unknown",
            )

        return DraftResult(
            draft_type=DraftType.appeal,
            content=content,
            attachments=attachments,
            payer_info=payer_info,
        )

    async def draft_call_packet(
        self,
        case: Case,
        diagnosis: Diagnosis,
        specialty: str = "",
    ) -> DraftResult:
        payer_info = get_payer_info(case.payer or "")
        root_cause = self._root_cause_from_diagnosis(diagnosis)
        attachments = REQUIRED_DOCS_BY_ROOT_CAUSE.get(root_cause, ["supporting_documentation"])
        carc = case.carc or ""
        claim_number = getattr(case, "claim_number", None) or case.patient_ref or str(case.id)

        try:
            system = build_call_packet_system_prompt()
            user_msg = build_call_packet_user_prompt(
                payer=case.payer or "",
                claim_number=claim_number,
                patient_ref=case.patient_ref or "Unknown",
                dos=self._case_dos_str(case),
                cpt=case.cpt_hcpcs or "",
                billed_amt=float(case.billed_amt or 0),
                carc=carc,
                carc_description=CARC_DESCRIPTIONS.get(carc, f"CARC {carc}"),
                root_cause=root_cause.value,
                rationale=diagnosis.rationale or "",
                phone_tree=payer_info.get("phone_tree", ""),
            )
            result_dict = await self.llm.complete_json(
                messages=[LLMMessage(role="user", content=user_msg)],
                system=system,
                max_tokens=1500,  # 800 truncated the JSON mid-string and silently triggered the generic fallback
            )
            content = json.dumps(result_dict)
        except Exception as exc:
            logger.warning("LLM call packet draft failed for case %s: %s", case.id, exc)
            content = _fallback_call_packet(
                payer=case.payer or "",
                claim_number=claim_number,
                carc=carc,
                phone_tree=payer_info.get("phone_tree", ""),
            )

        return DraftResult(
            draft_type=DraftType.call_packet,
            content=content,
            attachments=attachments,
            payer_info=payer_info,
        )

    async def draft_corrected_claim(
        self,
        case: Case,
        diagnosis: Diagnosis,
        specialty: str = "",
    ) -> DraftResult:
        payer_info = get_payer_info(case.payer or "")
        root_cause = self._root_cause_from_diagnosis(diagnosis)
        attachments = REQUIRED_DOCS_BY_ROOT_CAUSE.get(root_cause, ["supporting_documentation"])
        carc = case.carc or ""
        icd10 = [c.strip() for c in (case.icd10 or "").split(",") if c.strip()]
        claim_number = getattr(case, "claim_number", None) or case.patient_ref or str(case.id)

        try:
            system = build_corrected_claim_system_prompt()
            user_msg = build_corrected_claim_user_prompt(
                payer=case.payer or "",
                claim_number=claim_number,
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
                claim_number=claim_number,
                carc=carc,
                patient_ref=case.patient_ref or "Unknown",
            )

        return DraftResult(
            draft_type=DraftType.corrected_claim,
            content=content,
            attachments=attachments,
            payer_info=payer_info,
        )

    async def draft_all(
        self,
        case: Case,
        diagnosis: Diagnosis,
        specialty: str = "",
    ) -> list[DraftResult]:
        root_cause = self._root_cause_from_diagnosis(diagnosis)
        draft_types = self._select_draft_types(root_cause)

        tasks = []
        for dt in draft_types:
            if dt == DraftType.appeal:
                tasks.append(self.draft_appeal(case, diagnosis, specialty))
            elif dt == DraftType.corrected_claim:
                tasks.append(self.draft_corrected_claim(case, diagnosis, specialty))
            elif dt == DraftType.call_packet:
                tasks.append(self.draft_call_packet(case, diagnosis, specialty))

        return list(await asyncio.gather(*tasks))
