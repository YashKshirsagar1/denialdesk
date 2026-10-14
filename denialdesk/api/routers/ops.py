from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_role
from denialdesk.api.schemas.ops import DeadlineItem
from denialdesk.auth.models import Role, UserClaims
from denialdesk.models.case import Case, CaseState, Practice

router = APIRouter(prefix="/ops", tags=["ops"])

_EXCLUDED_STATES = {CaseState.paid, CaseState.declined, CaseState.closed}

_reviewer_or_ops = require_role(Role.ops_admin, Role.reviewer)


def _urgency(days: int) -> str:
    if days < 0:
        return "overdue"
    if days <= 3:
        return "critical"
    if days <= 7:
        return "warning"
    if days <= 14:
        return "upcoming"
    return "ok"


@router.get("/deadlines", response_model=list[DeadlineItem])
async def get_deadlines(
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_reviewer_or_ops),
):
    """Return all non-terminal cases with a filing_deadline, sorted most-urgent first."""
    stmt = (
        select(Case, Practice)
        .outerjoin(Practice, Practice.id == Case.tenant_id)
        .where(Case.filing_deadline.is_not(None))
        .where(Case.state.not_in(list(_EXCLUDED_STATES)))
        .order_by(Case.filing_deadline.asc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    today = date.today()
    items: list[DeadlineItem] = []
    for case, practice in rows:
        deadline_date = case.filing_deadline.date() if hasattr(case.filing_deadline, "date") else case.filing_deadline
        days = (deadline_date - today).days
        items.append(
            DeadlineItem(
                case_id=case.id,
                practice_name=practice.name if practice else None,
                payer=case.payer or "",
                patient_ref=case.patient_ref,
                cpt=case.cpt_hcpcs or "",
                billed_amt=float(case.billed_amt or 0),
                state=case.state.value,
                filing_deadline=deadline_date,
                days_until_deadline=days,
                urgency=_urgency(days),
            )
        )
    return items
