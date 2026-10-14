import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.models.case import (
    AuditEvent,
    Case,
    CaseState,
    Diagnosis,
    Draft,
    Outcome,
    Practice,
)
from denialdesk.repositories.case_repository import CaseRepository
from denialdesk.repositories.playbook_repository import PlaybookRepository


class OutcomeResult(str, Enum):
    paid = "paid"
    partially_paid = "partially_paid"
    denied = "denied"


@dataclass
class OutcomeInput:
    result: OutcomeResult
    amount_recovered: Decimal
    paid_date: Optional[date]
    notes: str = ""


class OutcomeProcessor:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.case_repo = CaseRepository(session)
        self.playbook_repo = PlaybookRepository(session)

    async def record_outcome(
        self, case_id: int, outcome_input: OutcomeInput
    ) -> tuple[Outcome, Case]:
        # Guard: no duplicate outcomes
        existing = await self.case_repo.get_outcome(case_id)
        if existing is not None:
            raise ValueError(f"Outcome already recorded for case {case_id}")

        case = await self.case_repo.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")

        outcome = Outcome(
            case_id=case_id,
            tenant_id=case.tenant_id,
            result=outcome_input.result.value,
            amount_recovered=float(outcome_input.amount_recovered),
            paid_date=outcome_input.paid_date,
            notes=outcome_input.notes,
        )
        self.session.add(outcome)
        await self.session.flush()

        # Transition through pending_payer if needed
        if case.state == CaseState.submitted:
            event = case.transition(CaseState.pending_payer, actor="outcome_processor", action_note="auto-advance on outcome entry")
            self.session.add(event)
            await self.session.flush()

        target_state = (
            CaseState.paid
            if outcome_input.result in (OutcomeResult.paid, OutcomeResult.partially_paid)
            else CaseState.re_denied
        )
        event = case.transition(target_state, actor="outcome_processor", action_note=f"result={outcome_input.result.value}")
        self.session.add(event)
        await self.session.flush()

        # Load diagnosis and latest draft for learning loop
        diagnosis = await self.case_repo.get_latest_diagnosis(case_id)
        draft = await self.case_repo.get_latest_draft(case_id, "appeal")

        await self._update_playbook(case, diagnosis, draft, outcome_input)

        await self.session.refresh(outcome)
        await self.session.refresh(case)
        return outcome, case

    async def _update_playbook(
        self,
        case: Case,
        diagnosis: Optional[Diagnosis],
        draft: Optional[Draft],
        outcome_input: OutcomeInput,
    ) -> None:
        payer = case.payer
        carc = case.carc or "unknown"
        # Look up the practice specialty so the playbook is keyed correctly
        specialty = "unknown"
        if case.tenant_id:
            practice = await self.session.get(Practice, case.tenant_id)
            if practice and practice.specialty:
                specialty = practice.specialty

        # Always record the attempt
        await self.playbook_repo.record_attempt(payer, carc, specialty, "", [])

        if outcome_input.result in (OutcomeResult.paid, OutcomeResult.partially_paid):
            await self.playbook_repo.record_win(payer, carc, specialty)

            winning_strategy = ""
            if draft and draft.content:
                winning_strategy = draft.content[:500]

            required_docs: list[str] = []
            if draft and draft.attachments:
                try:
                    required_docs = json.loads(draft.attachments)
                except (json.JSONDecodeError, TypeError):
                    required_docs = []

            await self.playbook_repo.update_winning_strategy(
                payer, carc, specialty, winning_strategy, required_docs
            )
