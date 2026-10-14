from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_role
from denialdesk.api.schemas.outcome import OutcomeRequest, OutcomeResponse, OutcomeSummary
from denialdesk.auth.models import Role, UserClaims
from denialdesk.billing.fees import calculate_fee
from denialdesk.learning.outcome_processor import OutcomeInput, OutcomeProcessor, OutcomeResult
from denialdesk.models.case import Case, Outcome, Practice
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


class VerifyRequest(BaseModel):
    verification_method: str = "clinic_confirmation"
    verified_by: str = "user"


@router.post("/cases/{case_id}/outcome/verify")
async def verify_outcome(
    case_id: int,
    body: VerifyRequest,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_role(Role.clinic_admin, Role.reviewer, Role.ops_admin)),
):
    outcome = await CaseRepository(session).get_outcome(case_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail="No outcome recorded for this case")

    # Load the case to get denial_date and tenant_id
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    # Enforce tenant scoping for clinic roles
    if not user.is_ops and user.tenant_id is not None and case.tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Load practice for fee config
    practice = await session.get(Practice, case.tenant_id) if case.tenant_id else None
    fee_rate_standard = Decimal(str(practice.fee_rate_standard)) if practice else Decimal("0.2200")
    fee_rate_aged = Decimal(str(practice.fee_rate_aged)) if practice else Decimal("0.3200")
    aged_threshold = int(practice.aged_threshold_days) if practice else 180

    denial_date = case.denial_date.date() if case.denial_date else None
    amount = Decimal(str(outcome.amount_recovered or 0))
    fee, _, _ = calculate_fee(amount, denial_date, fee_rate_standard, fee_rate_aged, aged_threshold)

    outcome.verified = True
    outcome.verification_method = body.verification_method
    outcome.verified_at = datetime.now(timezone.utc)
    outcome.verified_by = body.verified_by
    outcome.billable_amount = float(fee)

    await session.flush()
    return {
        "case_id": case_id,
        "outcome_id": outcome.id,
        "verified": True,
        "verification_method": outcome.verification_method,
        "verified_at": outcome.verified_at.isoformat(),
        "verified_by": outcome.verified_by,
        "amount_recovered": float(outcome.amount_recovered or 0),
        "billable_amount": float(outcome.billable_amount or 0),
    }


@router.get("/outcomes/summary", response_model=OutcomeSummary)
async def outcomes_summary(
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_role(Role.reviewer, Role.ops_admin)),
):
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
