import io
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from denialdesk.api.deps import get_session, require_auth
from denialdesk.api.schemas.case import CaseDetail, CaseSummary, DraftSchema
from denialdesk.auth.models import UserClaims
from denialdesk.export.packet_builder import PacketBuilder
from denialdesk.models.case import Case, CaseState, Diagnosis

router = APIRouter()


@router.get("/cases/{case_id}", response_model=CaseDetail)
async def get_case(
    case_id: int,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
):
    stmt = (
        select(Case)
        .options(selectinload(Case.diagnosis), selectinload(Case.drafts))
        .where(Case.id == case_id)
    )
    # Scope to tenant if user has a tenant_id (non-ops users)
    tenant_ctx = user.to_tenant_context()
    if tenant_ctx is not None:
        stmt = stmt.where(Case.tenant_id == tenant_ctx.tenant_id)

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
async def get_case_drafts(
    case_id: int,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
):
    stmt = (
        select(Case)
        .options(selectinload(Case.drafts))
        .where(Case.id == case_id)
    )
    tenant_ctx = user.to_tenant_context()
    if tenant_ctx is not None:
        stmt = stmt.where(Case.tenant_id == tenant_ctx.tenant_id)

    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return [DraftSchema.from_orm_draft(d) for d in sorted(case.drafts, key=lambda d: d.version, reverse=True)]


async def _load_case_for_packet(case_id: int, session: AsyncSession) -> tuple[Case, Diagnosis | None]:
    """Load case + diagnosis; raise 404 if not found."""
    stmt = (
        select(Case)
        .options(selectinload(Case.diagnosis), selectinload(Case.drafts))
        .where(Case.id == case_id)
    )
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case, case.diagnosis


def _pick_appeal_draft(case: Case):
    """Return the latest appeal draft, or None."""
    appeal_drafts = [d for d in case.drafts if d.type == "appeal"]
    if not appeal_drafts:
        return None
    return max(appeal_drafts, key=lambda d: d.version)


def _pick_call_packet_draft(case: Case):
    """Return the latest call_packet draft, or None."""
    cp_drafts = [d for d in case.drafts if d.type == "call_packet"]
    if not cp_drafts:
        return None
    return max(cp_drafts, key=lambda d: d.version)


@router.get("/cases/{case_id}/packet/appeal.pdf")
async def get_appeal_pdf(
    case_id: int,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
):
    case, diagnosis = await _load_case_for_packet(case_id, session)
    draft = _pick_appeal_draft(case)
    if draft is None:
        raise HTTPException(status_code=404, detail="No appeal draft found for this case")

    packet = PacketBuilder().build_packet(case=case, diagnosis=diagnosis, draft=draft)
    return StreamingResponse(
        io.BytesIO(packet.appeal_pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=appeal_{case_id}.pdf"},
    )


@router.get("/cases/{case_id}/packet/call-packet.pdf")
async def get_call_packet_pdf(
    case_id: int,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
):
    case, diagnosis = await _load_case_for_packet(case_id, session)
    draft = _pick_call_packet_draft(case) or _pick_appeal_draft(case)
    if draft is None:
        raise HTTPException(status_code=404, detail="No draft found for this case")

    packet = PacketBuilder().build_packet(case=case, diagnosis=diagnosis, draft=draft)
    return StreamingResponse(
        io.BytesIO(packet.call_packet_pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=call_packet_{case_id}.pdf"},
    )


@router.get("/cases/{case_id}/packet/attachments")
async def get_attachments(
    case_id: int,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
):
    case, _ = await _load_case_for_packet(case_id, session)
    draft = _pick_appeal_draft(case)
    if draft is None:
        return {"case_id": str(case_id), "attachments": []}

    raw = draft.attachments or "[]"
    try:
        attachments = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        attachments = []

    return {"case_id": str(case_id), "attachments": attachments}
