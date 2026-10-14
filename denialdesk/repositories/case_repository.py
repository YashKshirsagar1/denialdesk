import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.models.case import AuditEvent, Batch, Case, CaseState, Diagnosis, Draft


class CaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_case(self, **kwargs) -> Case:
        case = Case(**kwargs)
        self._session.add(case)
        await self._session.flush()
        await self._session.refresh(case)
        return case

    async def get_case(self, case_id: int) -> Case | None:
        result = await self._session.execute(select(Case).where(Case.id == case_id))
        return result.scalar_one_or_none()

    async def list_cases(
        self,
        state: CaseState | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Case]:
        stmt = select(Case)
        if state is not None:
            stmt = stmt.where(Case.state == state)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def transition_case(
        self,
        case_id: int,
        new_state: CaseState,
        actor: str,
        note: str = "",
    ) -> tuple[Case, AuditEvent]:
        case = await self.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        event = case.transition(new_state, actor=actor, action_note=note)
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(case)
        await self._session.refresh(event)
        return case, event

    async def get_audit_trail(self, case_id: int) -> list[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.case_id == case_id)
            .order_by(AuditEvent.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_batch(
        self,
        practice_id: int,
        source_format: str,
        filename: str,
    ) -> Batch:
        batch = Batch(
            practice_id=practice_id,
            uploaded_at=datetime.now(timezone.utc),
            source_files=filename,
        )
        self._session.add(batch)
        await self._session.flush()
        await self._session.refresh(batch)
        return batch

    async def create_case_from_record(
        self,
        batch_id: int,
        record,  # ClaimRecord — avoid circular import by using duck typing
    ) -> tuple[Case, AuditEvent]:
        """Create a Case in 'ingested' state with an audit event."""
        case = Case(
            batch_id=batch_id,
            payer=record.payer,
            patient_ref=record.patient_ref,
            dos=datetime(record.dos.year, record.dos.month, record.dos.day, tzinfo=timezone.utc),
            cpt_hcpcs=record.cpt,
            icd10=",".join(record.icd10),
            billed_amt=float(record.billed_amt),
            allowed_amt=float(record.allowed_amt),
            carc=record.carc,
            rarc=record.rarc,
            denial_date=datetime(
                record.denial_date.year,
                record.denial_date.month,
                record.denial_date.day,
                tzinfo=timezone.utc,
            ),
            state=CaseState.ingested,
        )
        self._session.add(case)
        await self._session.flush()

        event = AuditEvent(
            case_id=case.id,
            actor="ingestion_pipeline",
            action=f"ingested from {record.source_format}",
            timestamp=datetime.now(timezone.utc),
        )
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(case)
        await self._session.refresh(event)
        return case, event

    async def save_diagnosis(self, diagnosis: Diagnosis) -> Diagnosis:
        """Persist a Diagnosis and transition the associated Case to 'diagnosed' state."""
        self._session.add(diagnosis)
        await self._session.flush()

        case = await self.get_case(diagnosis.case_id)
        if case is None:
            raise ValueError(f"Case {diagnosis.case_id} not found")

        event = case.transition(
            CaseState.diagnosed,
            actor="diagnosis_agent",
            action_note=f"root_cause={diagnosis.root_cause}, score={diagnosis.winnability_score:.2f}",
        )
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(diagnosis)
        return diagnosis

    async def save_draft(self, case_id: int, draft_result) -> Draft:
        """Persist a Draft and transition Case to 'drafted' state (from approved or awaiting_human_review)."""
        from denialdesk.templates.payer_templates import DraftType

        # Determine next version for this draft type
        existing = await self.get_drafts(case_id)
        same_type = [d for d in existing if d.type == draft_result.draft_type.value]
        version = (max((d.version for d in same_type), default=0) + 1)

        draft = Draft(
            case_id=case_id,
            type=draft_result.draft_type.value,
            content=draft_result.content,
            attachments=json.dumps(draft_result.attachments),
            version=version,
        )
        self._session.add(draft)
        await self._session.flush()

        case = await self.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")

        if case.state in (CaseState.approved, CaseState.awaiting_human_review):
            event = case.transition(
                CaseState.drafted,
                actor="drafting_agent",
                action_note=f"drafted {draft_result.draft_type.value}",
            )
            self._session.add(event)
            await self._session.flush()

        await self._session.refresh(draft)
        return draft

    async def get_drafts(self, case_id: int) -> list[Draft]:
        stmt = (
            select(Draft)
            .where(Draft.case_id == case_id)
            .order_by(Draft.version.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_draft(self, case_id: int, draft_type_value: str) -> Draft | None:
        stmt = (
            select(Draft)
            .where(Draft.case_id == case_id, Draft.type == draft_type_value)
            .order_by(Draft.version.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
