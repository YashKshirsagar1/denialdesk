import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.models.case import AuditEvent, Case, CaseState


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
