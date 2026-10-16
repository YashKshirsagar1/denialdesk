from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_auth
from denialdesk.api.schemas.case import CaseSummary, QueueStats
from denialdesk.auth.models import UserClaims
from denialdesk.models.case import Case, CaseState, Diagnosis, Practice

router = APIRouter()


@router.get("/queue", response_model=QueueStats)
async def get_queue_stats(
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
):
    tenant_ctx = user.to_tenant_context()

    async def _count(state: CaseState) -> int:
        stmt = select(func.count()).select_from(Case).where(Case.state == state)
        if tenant_ctx is not None:
            stmt = stmt.where(Case.tenant_id == tenant_ctx.tenant_id)
        result = await session.execute(stmt)
        return result.scalar_one()

    awaiting = await _count(CaseState.awaiting_human_review)
    drafted = await _count(CaseState.drafted)
    submitted = await _count(CaseState.submitted)
    paid = await _count(CaseState.paid)
    declined = await _count(CaseState.declined)

    return QueueStats(
        awaiting_review=awaiting,
        drafted=drafted,
        submitted=submitted,
        paid=paid,
        declined=declined,
        total_active=awaiting + drafted + submitted,
    )


@router.get("/queue/cases", response_model=list[CaseSummary])
async def list_queue_cases(
    state: str = Query(default="awaiting_human_review,drafted"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
):
    tenant_ctx = user.to_tenant_context()
    states = [s.strip() for s in state.split(",") if s.strip()]
    state_enums = []
    for s in states:
        try:
            state_enums.append(CaseState(s))
        except ValueError:
            pass

    stmt = (
        select(Case, Diagnosis, Practice)
        .outerjoin(Diagnosis, Diagnosis.case_id == Case.id)
        .outerjoin(Practice, Practice.id == Case.tenant_id)
        .where(Case.state.in_(state_enums))
        .order_by(Case.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if tenant_ctx is not None:
        stmt = stmt.where(Case.tenant_id == tenant_ctx.tenant_id)

    result = await session.execute(stmt)
    rows = result.all()

    summaries = []
    for case, diag, practice in rows:
        summaries.append(
            CaseSummary(
                id=case.id,
                payer=case.payer or "",
                cpt=case.cpt_hcpcs or "",
                billed_amt=float(case.billed_amt or 0),
                carc=case.carc or "",
                denial_date=case.denial_date.date() if case.denial_date else None,
                state=case.state.value,
                winnability_score=diag.winnability_score if diag else None,
                root_cause=diag.root_cause if diag else None,
                created_at=case.created_at,
                practice_name=practice.name if practice else None,
                patient_ref=case.patient_ref,
            )
        )
    return summaries
