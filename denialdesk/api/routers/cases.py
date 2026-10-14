from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from denialdesk.api.deps import get_session
from denialdesk.api.schemas.case import CaseDetail, CaseSummary, DraftSchema
from denialdesk.models.case import Case, Diagnosis

router = APIRouter()


@router.get("/cases/{case_id}", response_model=CaseDetail)
async def get_case(case_id: int, session: AsyncSession = Depends(get_session)):
    stmt = (
        select(Case)
        .options(selectinload(Case.diagnosis), selectinload(Case.drafts))
        .where(Case.id == case_id)
    )
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    diag = case.diagnosis
    icd10 = [c.strip() for c in (case.icd10 or "").split(",") if c.strip()]
    drafts = [DraftSchema.from_orm_draft(d) for d in sorted(case.drafts, key=lambda d: d.version, reverse=True)]

    from denialdesk.api.schemas.case import DiagnosisSchema
    diag_schema = None
    if diag:
        diag_schema = DiagnosisSchema(
            root_cause=diag.root_cause or "",
            winnability_score=diag.winnability_score or 0.0,
            expected_value=diag.expected_value or 0.0,
            rationale=diag.rationale or "",
            model_version=diag.model_version or "",
        )

    return CaseDetail(
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
        icd10=icd10,
        allowed_amt=float(case.allowed_amt or 0),
        rarc=case.rarc or "",
        filing_deadline=case.filing_deadline.date() if case.filing_deadline else None,
        diagnosis=diag_schema,
        drafts=drafts,
    )


@router.get("/cases/{case_id}/drafts", response_model=list[DraftSchema])
async def get_case_drafts(case_id: int, session: AsyncSession = Depends(get_session)):
    stmt = (
        select(Case)
        .options(selectinload(Case.drafts))
        .where(Case.id == case_id)
    )
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return [DraftSchema.from_orm_draft(d) for d in sorted(case.drafts, key=lambda d: d.version, reverse=True)]
