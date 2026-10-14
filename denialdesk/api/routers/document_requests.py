import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_auth, require_role
from denialdesk.api.schemas.document_request import CreateDocumentRequestBody, DocumentRequestOut
from denialdesk.auth.models import Role, UserClaims
from denialdesk.models.case import Case, DocumentRequest, DocumentRequestStatus

router = APIRouter(tags=["document-requests"])

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "uploads")
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB for document fulfillments


def _ensure_uploads_dir() -> None:
    os.makedirs(UPLOADS_DIR, exist_ok=True)


def _scoped_stmt(user: UserClaims):
    stmt = select(DocumentRequest)
    if user.tenant_id is not None:
        stmt = stmt.where(DocumentRequest.tenant_id == user.tenant_id)
    return stmt


@router.get("/document-requests", response_model=list[DocumentRequestOut])
async def list_document_requests(
    user: UserClaims = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    stmt = _scoped_stmt(user).order_by(DocumentRequest.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/cases/{case_id}/document-requests", response_model=DocumentRequestOut, status_code=201)
async def create_document_request(
    case_id: int,
    body: CreateDocumentRequestBody,
    user: UserClaims = Depends(require_role(Role.reviewer, Role.ops_admin)),
    session: AsyncSession = Depends(get_session),
):
    case = await session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    req = DocumentRequest(
        case_id=case_id,
        tenant_id=case.tenant_id,
        requested_by=body.requested_by,
        document_type=body.document_type,
        description=body.description,
        status=DocumentRequestStatus.pending,
        created_at=datetime.now(timezone.utc),
    )
    session.add(req)
    await session.flush()
    return req


@router.get("/cases/{case_id}/document-requests", response_model=list[DocumentRequestOut])
async def list_case_document_requests(
    case_id: int,
    user: UserClaims = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(DocumentRequest).where(DocumentRequest.case_id == case_id)
    if user.tenant_id is not None:
        stmt = stmt.where(DocumentRequest.tenant_id == user.tenant_id)
    stmt = stmt.order_by(DocumentRequest.created_at.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/document-requests/{req_id}/fulfill", response_model=DocumentRequestOut)
async def fulfill_document_request(
    req_id: int,
    file: UploadFile | None = File(default=None),
    user: UserClaims = Depends(require_role(Role.clinic_admin, Role.clinic_staff)),
    session: AsyncSession = Depends(get_session),
):
    req = await session.get(DocumentRequest, req_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Document request not found")

    if user.tenant_id is not None and req.tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if req.status == DocumentRequestStatus.fulfilled:
        raise HTTPException(status_code=400, detail="Request already fulfilled")

    file_path: str | None = None
    if file is not None:
        _ensure_uploads_dir()
        safe_name = os.path.basename(file.filename or "upload")
        dest = os.path.join(UPLOADS_DIR, f"{req_id}_{safe_name}")
        content = await file.read()
        if len(content) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 20 MB.")
        with open(dest, "wb") as fh:
            fh.write(content)
        file_path = dest  # prod: replace with private S3 key

    req.status = DocumentRequestStatus.fulfilled
    req.fulfilled_at = datetime.now(timezone.utc)
    if file_path:
        req.file_path = file_path

    await session.flush()
    return req
