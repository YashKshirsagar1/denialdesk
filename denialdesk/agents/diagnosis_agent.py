import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum

from denialdesk.agents.prompts.diagnosis import (
    build_diagnosis_system_prompt,
    build_diagnosis_user_prompt,
)
from denialdesk.data.carc_descriptions import CARC_DESCRIPTIONS
from denialdesk.llm.base import LLMMessage, LLMProvider
from denialdesk.models.case import Case, Diagnosis

logger = logging.getLogger(__name__)


class RootCause(str, Enum):
    missing_prior_auth = "missing_prior_auth"
    coding_error       = "coding_error"
    eligibility        = "eligibility"
    medical_necessity  = "medical_necessity"
    timely_filing      = "timely_filing"
    bundling_ncci      = "bundling_ncci"
    duplicate          = "duplicate"
    missing_info       = "missing_info"
    not_covered        = "not_covered"
    other              = "other"


CARC_ROOT_CAUSE: dict[str, RootCause] = {
    "4":   RootCause.not_covered,
    "11":  RootCause.coding_error,
    "16":  RootCause.missing_info,
    "18":  RootCause.duplicate,
    "22":  RootCause.eligibility,
    "29":  RootCause.timely_filing,
    "45":  RootCause.coding_error,
    "50":  RootCause.medical_necessity,
    "96":  RootCause.not_covered,
    "97":  RootCause.bundling_ncci,
    "167": RootCause.not_covered,
    "170": RootCause.missing_prior_auth,
    "171": RootCause.missing_prior_auth,
    "172": RootCause.missing_prior_auth,
    "197": RootCause.missing_prior_auth,
}

# CARC score adjustments for rule-based scoring
_CARC_SCORE_DELTA: dict[str, float] = {
    "4":   -0.30,
    "11":  +0.15,
    "16":  +0.20,
    "18":  -0.10,
    "22":  -0.20,
    "45":  -0.05,
    "50":  +0.10,
    "96":  -0.30,
    "97":  +0.05,
    "167": -0.30,
    "170": +0.10,
    "171": +0.05,
    "172": -0.10,
    "197": +0.10,
}


class DiagnosisAgent:
    def __init__(self, llm_provider: LLMProvider, model_version: str = "claude-sonnet-4-6") -> None:
        self.llm = llm_provider
        self.model_version = model_version

    def _rule_based_score(self, case: Case) -> tuple[RootCause, float]:
        """Pure function: returns (root_cause, winnability_score) from rule-based logic only."""
        carc = case.carc or ""
        root_cause = CARC_ROOT_CAUSE.get(carc, RootCause.other)
        score = 0.5

        if carc == "29":
            now = datetime.now(timezone.utc)
            deadline = case.filing_deadline
            if deadline is not None:
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                if deadline < now:
                    score -= 0.40
                else:
                    score += 0.10
            else:
                score -= 0.20
        else:
            score += _CARC_SCORE_DELTA.get(carc, 0.0)

        return root_cause, max(0.05, min(0.95, score))

    async def diagnose(self, case: Case) -> Diagnosis:
        """Diagnose a single case. Returns an unsaved Diagnosis ORM object."""
        rule_cause, rule_score = self._rule_based_score(case)

        carc = case.carc or ""
        carc_desc = CARC_DESCRIPTIONS.get(carc, f"CARC code {carc}")

        icd10_list: list[str] = []
        if case.icd10:
            icd10_list = [c.strip() for c in case.icd10.split(",") if c.strip()]

        denial_str = ""
        if case.denial_date:
            d = case.denial_date
            denial_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)

        deadline_str = ""
        if case.filing_deadline:
            dl = case.filing_deadline
            deadline_str = dl.strftime("%Y-%m-%d") if hasattr(dl, "strftime") else str(dl)

        root_cause = rule_cause
        winnability_score = rule_score
        rationale = f"Rule-based classification: CARC {carc} maps to {rule_cause.value}."
        expected_value_pct = 0.7 if winnability_score >= 0.5 else 0.3
        confidence = 0.6

        try:
            system = build_diagnosis_system_prompt()
            user_msg = build_diagnosis_user_prompt(
                carc=carc,
                rarc=case.rarc or "",
                cpt=case.cpt_hcpcs or "",
                icd10=icd10_list,
                payer=case.payer or "",
                billed_amt=float(case.billed_amt or 0),
                denial_date=denial_str,
                filing_deadline=deadline_str,
                carc_description=carc_desc,
            )
            result = await self.llm.complete_json(
                messages=[LLMMessage(role="user", content=user_msg)],
                system=system,
                max_tokens=800,
            )

            llm_root_cause_str = result.get("root_cause", "")
            try:
                root_cause = RootCause(llm_root_cause_str)
            except ValueError:
                logger.warning("LLM returned unknown root_cause '%s', falling back to rule-based", llm_root_cause_str)
                root_cause = rule_cause

            winnability_score = float(result.get("winnability_score", rule_score))
            winnability_score = max(0.05, min(0.95, winnability_score))
            rationale = result.get("rationale", rationale)
            expected_value_pct = float(result.get("expected_value_pct", expected_value_pct))
            expected_value_pct = max(0.0, min(1.0, expected_value_pct))
            confidence = float(result.get("confidence", confidence))

        except Exception as exc:
            logger.warning("LLM diagnosis failed for case %s, using rule-based fallback: %s", case.id, exc)

        expected_value = winnability_score * float(case.billed_amt or 0) * expected_value_pct

        return Diagnosis(
            case_id=case.id,
            root_cause=root_cause.value,
            winnability_score=winnability_score,
            expected_value=expected_value,
            rationale=rationale,
            model_version=self.model_version,
        )

    def get_missing_document_requests(self, case: Case) -> list[dict]:
        """Return document requests the agent needs based on CARC/root-cause.

        Called by the coordinator after diagnosis. The coordinator creates
        DocumentRequest rows; this method is a pure data function.
        """
        carc = case.carc or ""
        root_cause = CARC_ROOT_CAUSE.get(carc, RootCause.other)
        requests: list[dict] = []

        if root_cause == RootCause.missing_prior_auth:
            requests.append({
                "document_type": "prior_auth",
                "description": (
                    f"Please upload the prior authorization for CPT {case.cpt_hcpcs or 'unknown'} "
                    f"from {case.payer}."
                ),
                "requested_by": "diagnosis_agent",
            })
        elif root_cause == RootCause.missing_info:
            requests.append({
                "document_type": "chart_note",
                "description": (
                    f"Please upload the chart note or clinical documentation for the "
                    f"service on {case.dos.date() if case.dos else 'DOS unknown'} (CPT {case.cpt_hcpcs or 'unknown'})."
                ),
                "requested_by": "diagnosis_agent",
            })
        elif root_cause == RootCause.medical_necessity:
            requests.append({
                "document_type": "medical_records",
                "description": (
                    f"Please upload supporting medical records documenting medical necessity "
                    f"for CPT {case.cpt_hcpcs or 'unknown'} billed to {case.payer}."
                ),
                "requested_by": "diagnosis_agent",
            })

        return requests

    async def diagnose_batch(self, cases: list[Case]) -> list[Diagnosis]:
        """Diagnose a list of cases concurrently."""
        return list(await asyncio.gather(*[self.diagnose(c) for c in cases]))
