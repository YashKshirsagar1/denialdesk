import difflib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from denialdesk.api.deps import get_session
from denialdesk.api.schemas.review import ReviewRequest, ReviewResponse
from denialdesk.models.case import AuditEvent, Case, CaseState, Draft, Review

router = APIRouter()


@router.post("/cases/{case_id}/review", response_model=ReviewResponse)
async def review_case(
    case_id: int,
    body: ReviewRequest,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Case)
        .options(selectinload(Case.drafts))
        .where(Case.id == case_id)
    )
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    # Find latest appeal draft
    appeal_drafts = [d for d in case.drafts if d.type == "appeal"]
    appeal_drafts.sort(key=lambda d: d.version, reverse=True)
    latest_draft = appeal_drafts[0] if appeal_drafts else None

    new_draft_id: int | None = latest_draft.id if latest_draft else None

    if body.decision == "approve":
        if case.state != CaseState.awaiting_human_review:
            raise HTTPException(status_code=400, detail=f"Case is in state '{case.state.value}', expected 'awaiting_human_review'")

        if latest_draft:
            review = Review(
                draft_id=latest_draft.id,
                reviewer=body.reviewer,
                decision="approved",
                edits_diff=None,
                timestamp=datetime.now(timezone.utc),
            )
            session.add(review)

        event = case.transition(CaseState.submitted, actor=body.reviewer, action_note="review:approved")
        session.add(event)
        await session.flush()
        return ReviewResponse(case_id=case_id, new_state="submitted", draft_id=new_draft_id, message="Appeal approved and submitted.")

    elif body.decision == "edit":
        if case.state != CaseState.awaiting_human_review:
            raise HTTPException(status_code=400, detail=f"Case is in state '{case.state.value}', expected 'awaiting_human_review'")

        if latest_draft is None:
            raise HTTPException(status_code=400, detail="No draft found to edit")

        original_content = latest_draft.content or ""
        edited_content = body.edits or original_content

        # Compute unified diff
        diff_lines = list(difflib.unified_diff(
            original_content.splitlines(keepends=True),
            edited_content.splitlines(keepends=True),
            fromfile="original",
            tofile="edited",
        ))
        edits_diff = "".join(diff_lines) if diff_lines else ""

        # New draft version
        new_draft = Draft(
            case_id=case_id,
            type="appeal",
            content=edited_content,
            attachments=latest_draft.attachments,
            version=latest_draft.version + 1,
        )
        session.add(new_draft)
        await session.flush()

        review = Review(
            draft_id=new_draft.id,
            reviewer=body.reviewer,
            decision="edited",
            edits_diff=edits_diff,
            timestamp=datetime.now(timezone.utc),
        )
        session.add(review)

        event = case.transition(CaseState.submitted, actor=body.reviewer, action_note="review:edited")
        session.add(event)
        await session.flush()
        return ReviewResponse(case_id=case_id, new_state="submitted", draft_id=new_draft.id, message="Draft edited and submitted.")

    elif body.decision == "reject":
        if case.state != CaseState.awaiting_human_review:
            raise HTTPException(status_code=400, detail=f"Case is in state '{case.state.value}', expected 'awaiting_human_review'")

        if latest_draft:
            review = Review(
                draft_id=latest_draft.id,
                reviewer=body.reviewer,
                decision="rejected",
                edits_diff=None,
                timestamp=datetime.now(timezone.utc),
            )
            session.add(review)

        event = case.transition(CaseState.drafted, actor=body.reviewer, action_note="review:rejected")
        session.add(event)
        await session.flush()
        return ReviewResponse(case_id=case_id, new_state="drafted", draft_id=new_draft_id, message="Draft rejected, returned for redrafting.")

    else:
        raise HTTPException(status_code=400, detail=f"Unknown decision: {body.decision}")
