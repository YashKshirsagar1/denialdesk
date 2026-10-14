from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_role
from denialdesk.api.schemas.outcome import OutcomeRequest, OutcomeResponse, OutcomeSummary
from denialdesk.auth.models import Role, UserClaims
from denialdesk.learning.outcome_processor import OutcomeInput, OutcomeProcessor, OutcomeResult
from denialdesk.models.case import Outcome
from denialdesk.repositories.case_repository import CaseRepository

router = APIRouter(tags=["outcomes"])

_outcome_roles = require_role(Role.reviewer, Role.ops_admin)


@router.post("/cases/{case_id}/outcome", response_model=OutcomeResponse)
async def record_outcome(
    case_id: int,
    body: OutcomeRequest,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_outcome_roles),
):
    processor = OutcomeProcessor(session)
    try:
        outcome, case = await processor.record_outcome(
            case_id,
            OutcomeInput(
                result=OutcomeResult(body.result),
                amount_recovered=Decimal(str(body.amount_recovered)),
                paid_date=body.paid_date,
                notes=body.notes,
            ),
        )
        await session.commit()
        return OutcomeResponse(
            case_id=case_id,
            outcome_id=outcome.id,
            new_state=case.state.value,
            amount_recovered=float(outcome.amount_recovered or 0),
            playbook_updated=True,
            message=f"Outcome recorded: {body.result}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cases/{case_id}/outcome")
async def get_outcome(
    case_id: int,
    session: AsyncSession = Depends(get_session),
):
    repo = CaseRepository(session)
    outcome = await repo.get_outcome(case_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="No outcome recorded")
    return {
        "case_id": case_id,
        "result": outcome.result,
        "amount_recovered": float(outcome.amount_recovered or 0),
        "paid_date": str(outcome.paid_date) if outcome.paid_date else None,
        "notes": outcome.notes,
    }


@router.get("/outcomes/summary", response_model=OutcomeSummary)
async def outcomes_summary(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Outcome))
    outcomes = result.scalars().all()
    total = len(outcomes)
    paid = [o for o in outcomes if o.result in ("paid", "partially_paid")]
    denied = [o for o in outcomes if o.result == "denied"]
    total_recovered = sum(float(o.amount_recovered or 0) for o in paid)
    return OutcomeSummary(
        total_cases_with_outcomes=total,
        total_paid=len(paid),
        total_denied=len(denied),
        total_amount_recovered=total_recovered,
        win_rate=len(paid) / total if total > 0 else 0.0,
        avg_amount_recovered=total_recovered / len(paid) if paid else 0.0,
    )
