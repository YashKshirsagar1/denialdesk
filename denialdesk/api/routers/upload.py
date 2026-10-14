import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_role
from denialdesk.auth.models import Role, UserClaims
from denialdesk.coordinator import Coordinator
from denialdesk.ingestion.base import IngestorError
from denialdesk.ingestion.pipeline import IngestionPipeline
from denialdesk.llm import get_llm_provider
from denialdesk.models.case import Practice

router = APIRouter(tags=["upload"])
logger = logging.getLogger(__name__)

_upload_roles = require_role(Role.clinic_admin, Role.clinic_staff, Role.ops_admin)


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
) -> list[PracticeOut]:
    result = await session.execute(select(Practice).order_by(Practice.name))
    practices = result.scalars().all()
    return [PracticeOut(id=p.id, name=p.name, specialty=p.specialty) for p in practices]


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    practice_id: int = Form(1),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_upload_roles),
) -> UploadResponse:
    practice = await session.get(Practice, practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail=f"Practice {practice_id} not found")

    content = await file.read()
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


@router.post("/batches/{batch_id}/process", response_model=ProcessResponse)
async def process_batch(
    batch_id: int,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_upload_roles),
) -> ProcessResponse:
    llm = get_llm_provider()
    coordinator = Coordinator(session, llm)
    batch_result = await coordinator.process_batch(batch_id)
    return ProcessResponse(
        batch_id=batch_id,
        processed=batch_result.processed,
        declined=batch_result.declined,
        awaiting_review=batch_result.awaiting_review,
        errors=batch_result.errors,
    )
