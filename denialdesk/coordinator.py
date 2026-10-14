import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.agents.diagnosis_agent import DiagnosisAgent
from denialdesk.agents.drafting_agent import DraftingAgent
from denialdesk.llm.base import LLMProvider
from denialdesk.models.case import AuditEvent, Case, CaseState
from denialdesk.repositories import CaseRepository

logger = logging.getLogger(__name__)

DECLINE_THRESHOLD = 0.20


@dataclass
class ProcessResult:
    case_id: int
    final_state: str
    error: str | None = None


@dataclass
class BatchResult:
    batch_id: int
    processed: int = 0
    declined: int = 0
    awaiting_review: int = 0
    errors: list[dict] = field(default_factory=list)


class Coordinator:
    """Chains ingest → diagnose → auto-decline/approve → draft → awaiting_human_review."""

    def __init__(
        self,
        session: AsyncSession,
        llm_provider: LLMProvider,
        practice_name: str = "Unknown Practice",
    ) -> None:
        self._session = session
        self._diagnosis_agent = DiagnosisAgent(llm_provider)
        self._drafting_agent = DraftingAgent(llm_provider, practice_name=practice_name)
        self._case_repo = CaseRepository(session)

    async def process_case(self, case: Case) -> ProcessResult:
        """Run the full pipeline for one Case: diagnose → decline or draft → awaiting_review."""
        try:
            # 1. Diagnose — save_diagnosis also transitions case to CaseState.diagnosed
            diagnosis = await self._diagnosis_agent.diagnose(case)
            await self._case_repo.save_diagnosis(diagnosis)
            await self._session.refresh(case)

            score = diagnosis.winnability_score or 0.0

            # 2. Auto-decline if score is below threshold
            if score < DECLINE_THRESHOLD:
                event = case.transition(
                    CaseState.declined,
                    actor="coordinator",
                    action_note=f"auto_decline score={score:.2f} < {DECLINE_THRESHOLD}",
                )
                self._session.add(event)
                await self._session.flush()
                logger.info("Case %s auto-declined (score=%.2f)", case.id, score)
                return ProcessResult(case_id=case.id, final_state=CaseState.declined.value)

            # 3. Approve
            event = case.transition(CaseState.approved, actor="coordinator")
            self._session.add(event)
            await self._session.flush()

            # 4. Draft all document types — save_draft handles the drafted transition
            draft_results = await self._drafting_agent.draft_all(case, diagnosis)
            for dr in draft_results:
                await self._case_repo.save_draft(case.id, dr)
            await self._session.refresh(case)

            # 5. Move to awaiting_human_review
            if case.state == CaseState.drafted:
                event = case.transition(CaseState.awaiting_human_review, actor="coordinator")
                self._session.add(event)
                await self._session.flush()

            logger.info("Case %s → %s", case.id, case.state.value)
            return ProcessResult(case_id=case.id, final_state=case.state.value)

        except Exception as exc:
            logger.error("Coordinator error on case %s: %s", case.id, exc, exc_info=True)
            return ProcessResult(case_id=case.id, final_state=case.state.value, error=str(exc))

    async def process_batch(self, batch_id: int) -> BatchResult:
        """Process all ingested cases in a batch through the full pipeline."""
        stmt = select(Case).where(
            Case.batch_id == batch_id,
            Case.state == CaseState.ingested,
        )
        result = await self._session.execute(stmt)
        cases = list(result.scalars().all())

        batch_result = BatchResult(batch_id=batch_id)
        for case in cases:
            pr = await self.process_case(case)
            if pr.error:
                batch_result.errors.append({"case_id": pr.case_id, "error": pr.error})
            else:
                batch_result.processed += 1
                if pr.final_state == CaseState.declined.value:
                    batch_result.declined += 1
                elif pr.final_state == CaseState.awaiting_human_review.value:
                    batch_result.awaiting_review += 1

        return batch_result
