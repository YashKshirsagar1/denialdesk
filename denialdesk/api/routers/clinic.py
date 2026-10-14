from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_role
from denialdesk.api.schemas.case import ClinicDashboard
from denialdesk.auth.models import Role, UserClaims
from denialdesk.models.case import AccessLog, Case, CaseState, Outcome

router = APIRouter(prefix="/clinic", tags=["clinic"])

class AccessLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: str
    actor_role: str
    resource: str
    action: str
    http_method: str
    path: str
    timestamp: datetime


_IN_PROGRESS_STATES = {
    CaseState.ingested,
    CaseState.diagnosed,
    CaseState.approved,
    CaseState.drafted,
    CaseState.awaiting_human_review,
    CaseState.submitted,
    CaseState.pending_payer,
    CaseState.re_denied,
    CaseState.escalated,
}


@router.get("/access-log", response_model=list[AccessLogEntry])
async def get_access_log(
    tenant_id: Optional[int] = Query(default=None, description="Filter by tenant (ops_admin only)"),
    limit: int = Query(default=200, le=500),
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_role(Role.clinic_admin, Role.ops_admin)),
):
    """Return access log entries scoped to the caller's tenant.

    clinic_admin: sees only their own tenant's log.
    ops_admin: sees all tenants, optionally filtered by ?tenant_id=N.
    actor_email is not returned (it's a one-way hash stored for audit purposes).
    """
    stmt = select(AccessLog).order_by(AccessLog.timestamp.desc()).limit(limit)

    if user.role == Role.clinic_admin:
        if user.tenant_id is None:
            return []
        stmt = stmt.where(AccessLog.tenant_id == user.tenant_id)
    elif tenant_id is not None:
        stmt = stmt.where(AccessLog.tenant_id == tenant_id)

    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/dashboard", response_model=ClinicDashboard)
async def get_clinic_dashboard(
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_role(Role.clinic_admin, Role.clinic_staff, Role.ops_admin)),
):
    """Clinic-scoped dashboard: dollars submitted, recovered, cases in progress.

    Requires JWT with a tenant_id. Ops users without a tenant get 400.
    """
    tenant_ctx = user.to_tenant_context()
    if tenant_ctx is None:
        raise HTTPException(
            status_code=400,
            detail="This endpoint requires a tenant-scoped token (tenant_id must be set in JWT).",
        )

    tid = tenant_ctx.tenant_id

    # All cases for this tenant
    cases_r = await session.execute(
        select(Case.id, Case.billed_amt, Case.state).where(Case.tenant_id == tid)
    )
    cases = cases_r.all()

    total_cases = len(cases)
    cases_in_progress = sum(1 for c in cases if c.state in _IN_PROGRESS_STATES)
    cases_paid = sum(1 for c in cases if c.state == CaseState.paid)
    cases_declined = sum(1 for c in cases if c.state == CaseState.declined)
    dollars_submitted = sum(float(c.billed_amt or 0) for c in cases)

    # Sum recovered amounts from outcomes
    outcome_r = await session.execute(
        select(func.sum(Outcome.amount_recovered)).where(
            Outcome.tenant_id == tid,
            Outcome.result.in_(["paid", "partially_paid"]),
        )
    )
    dollars_recovered = float(outcome_r.scalar_one() or 0)

    return ClinicDashboard(
        dollars_submitted=round(dollars_submitted, 2),
        dollars_recovered=round(dollars_recovered, 2),
        cases_in_progress=cases_in_progress,
        cases_paid=cases_paid,
        cases_declined=cases_declined,
        total_cases=total_cases,
    )
