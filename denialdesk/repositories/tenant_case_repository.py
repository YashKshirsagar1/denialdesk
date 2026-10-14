from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.models.case import AuditEvent, Case, CaseState
from denialdesk.repositories.case_repository import CaseRepository
from denialdesk.repositories.tenant_scoped import TenantContext


class TenantCaseRepository(CaseRepository):
    """CaseRepository scoped to a single tenant (practice).

    Every read query adds a tenant_id predicate so one practice can never
    see another's cases, diagnoses, or audit trail.
    """

    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        super().__init__(session)
        self._tenant = tenant

    async def get_case(self, case_id: int) -> Case | None:
        result = await self._session.execute(
            select(Case).where(
                Case.id == case_id,
                Case.tenant_id == self._tenant.tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_cases(
        self,
        state: CaseState | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Case]:
        stmt = select(Case).where(Case.tenant_id == self._tenant.tenant_id)
        if state is not None:
            stmt = stmt.where(Case.state == state)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_audit_trail(self, case_id: int) -> list[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .where(
                AuditEvent.case_id == case_id,
                AuditEvent.tenant_id == self._tenant.tenant_id,
            )
            .order_by(AuditEvent.timestamp.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
