import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, get_session_factory, require_active_practice, require_auth, require_role
from denialdesk.auth.models import Role, UserClaims
from denialdesk.coordinator import Coordinator
from denialdesk.ingestion.base import IngestorError
from denialdesk.ingestion.pipeline import IngestionPipeline
from denialdesk.llm import get_llm_provider
from denialdesk.models.case import Batch, Case, CaseState, Practice

router = APIRouter(tags=["upload"])
logger = logging.getLogger(__name__)

_upload_roles = require_role(Role.clinic_admin, Role.clinic_staff, Role.ops_admin)
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


class UploadResponse(BaseModel):
    batch_id: int
    practice_id: int
    case_count: int
    errors: list[str]


class ProcessResponse(BaseModel):
    batch_id: int
    processed: int
    declined: int
    awaiting_review: int
    errors: list[dict]


class PracticeOut(BaseModel):
    id: int
    name: str
    specialty: str


@router.get("/practices", response_model=list[PracticeOut])
async def list_practices(
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_role(Role.ops_admin, Role.reviewer)),
) -> list[PracticeOut]:
    result = await session.execute(select(Practice).order_by(Practice.name))
    practices = result.scalars().all()
    return [PracticeOut(id=p.id, name=p.name, specialty=p.specialty) for p in practices]


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    practice_id: int | None = Form(None),
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(_upload_roles),
    _practice_active=Depends(require_active_practice),
) -> UploadResponse:
    # Clinic users always upload into their own practice — never trust a client-supplied id.
    # Ops uploads on behalf of a clinic and must say which one.
    if not user.is_ops:
        practice_id = user.tenant_id
    elif practice_id is None:
        raise HTTPException(status_code=422, detail="practice_id is required for ops uploads")
    practice = await session.get(Practice, practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail=f"Practice {practice_id} not found")

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum upload size is 50 MB.")
    filename = file.filename or "upload"

    try:
        pipeline = IngestionPipeline(session)
        result = await pipeline.ingest_file(filename, content, practice_id)
    except IngestorError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    batch_id = result.batch_id.int

    return UploadResponse(
        batch_id=batch_id,
        practice_id=practice_id,
        case_count=len(result.records),
        errors=[str(e) for e in result.errors],
    )


async def _owned_batch(session: AsyncSession, batch_id: int, user: UserClaims) -> Batch:
    batch = await session.get(Batch, batch_id)
    # Same 404 whether it doesn't exist or belongs to another clinic.
    if batch is None or (not user.is_ops and batch.tenant_id != user.tenant_id):
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


async def _process_in_background(batch_id: int, practice_name: str) -> None:
    """Run the pipeline on its own DB session after the HTTP response has been sent."""
    try:
        async with get_session_factory()() as session:
            await Coordinator(session, get_llm_provider(), practice_name=practice_name).process_batch(batch_id)
    except Exception:
        logger.exception("Background processing failed for batch %s", batch_id)


@router.post("/batches/{batch_id}/process", response_model=ProcessResponse)
async def process_batch(
    batch_id: int,
    background_tasks: BackgroundTasks,
    background: bool = False,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(_upload_roles),
    _practice_active=Depends(require_active_practice),
) -> ProcessResponse:
    batch = await _owned_batch(session, batch_id, user)
    practice = await session.get(Practice, batch.practice_id)
    practice_name = practice.name if practice else "Unknown Practice"

    if background:
        # Commit now so the worker's separate session sees the batch.
        await session.commit()
        background_tasks.add_task(_process_in_background, batch_id, practice_name)
        return ProcessResponse(batch_id=batch_id, processed=0, declined=0, awaiting_review=0, errors=[])

    llm = get_llm_provider()
    coordinator = Coordinator(session, llm, practice_name=practice_name)
    batch_result = await coordinator.process_batch(batch_id)
    return ProcessResponse(
        batch_id=batch_id,
        processed=batch_result.processed,
        declined=batch_result.declined,
        awaiting_review=batch_result.awaiting_review,
        errors=batch_result.errors,
    )


class BatchSummary(BaseModel):
    id: int
    practice_id: int
    practice_name: str | None
    filename: str | None
    uploaded_at: datetime
    total: int
    analyzing: int  # ingested, not yet diagnosed
    declined: int
    in_progress: int  # drafted / in review / submitted / pending payer / escalated
    paid: int
    done: bool


def _bucket(state: CaseState) -> str:
    if state == CaseState.ingested:
        return "analyzing"
    if state in (CaseState.declined, CaseState.closed, CaseState.re_denied):
        return "declined"
    if state == CaseState.paid:
        return "paid"
    return "in_progress"


async def _batch_summaries(session: AsyncSession, user: UserClaims, only_id: int | None = None) -> list[BatchSummary]:
    stmt = select(Batch, Practice.name).outerjoin(Practice, Practice.id == Batch.practice_id)
    if not user.is_ops:
        stmt = stmt.where(Batch.tenant_id == user.tenant_id)
    if only_id is not None:
        stmt = stmt.where(Batch.id == only_id)
    batches = (await session.execute(stmt.order_by(Batch.uploaded_at.desc()).limit(100))).all()
    if not batches:
        return []
    ids = [b.id for b, _ in batches]
    rows = (
        await session.execute(
            select(Case.batch_id, Case.state, func.count()).where(Case.batch_id.in_(ids)).group_by(Case.batch_id, Case.state)
        )
    ).all()
    counts: dict[int, dict[str, int]] = {i: {"analyzing": 0, "declined": 0, "in_progress": 0, "paid": 0} for i in ids}
    for batch_id, state, n in rows:
        counts[batch_id][_bucket(state)] += n
    out = []
    for b, name in batches:
        c = counts[b.id]
        total = sum(c.values())
        out.append(
            BatchSummary(
                id=b.id, practice_id=b.practice_id, practice_name=name, filename=b.source_files,
                uploaded_at=b.uploaded_at, total=total, done=c["analyzing"] == 0, **c,
            )
        )
    return out


@router.get("/batches", response_model=list[BatchSummary])
async def list_batches(
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
) -> list[BatchSummary]:
    return await _batch_summaries(session, user)


@router.get("/batches/{batch_id}", response_model=BatchSummary)
async def get_batch(
    batch_id: int,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
) -> BatchSummary:
    await _owned_batch(session, batch_id, user)
    return (await _batch_summaries(session, user, only_id=batch_id))[0]
