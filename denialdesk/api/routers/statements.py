"""Statement generation, listing, PDF download, and Stripe stub."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_auth, require_role
from denialdesk.auth.models import Role, UserClaims
from denialdesk.billing.statement_service import StatementService
from denialdesk.export.statement_pdf import generate_statement_pdf
from denialdesk.models.case import Practice, Statement

router = APIRouter(tags=["statements"])


class GenerateStatementRequest(BaseModel):
    practice_id: int
    period_start: date
    period_end: date


class StatementOut(BaseModel):
    id: int
    practice_id: int
    practice_name: str | None = None
    period_start: date
    period_end: date
    total_recovered: float
    fee_amount: float
    status: str
    generated_at: datetime
    sent_at: datetime | None = None
    stripe_invoice_id: str | None = None
    pdf_path: str | None = None

    model_config = ConfigDict(from_attributes=True)


async def _statement_out(statement: Statement, session: AsyncSession) -> dict:
    practice = await session.get(Practice, statement.practice_id)
    return StatementOut(
        id=statement.id,
        practice_id=statement.practice_id,
        practice_name=practice.name if practice else None,
        period_start=statement.period_start,
        period_end=statement.period_end,
        total_recovered=float(statement.total_recovered or 0),
        fee_amount=float(statement.fee_amount or 0),
        status=statement.status,
        generated_at=statement.generated_at,
        sent_at=statement.sent_at,
        stripe_invoice_id=statement.stripe_invoice_id,
        pdf_path=statement.pdf_path,
    ).model_dump()


@router.post("/ops/statements/generate")
async def generate_statement(
    body: GenerateStatementRequest,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_role(Role.ops_admin)),
):
    service = StatementService(session)
    statement = await service.generate(body.practice_id, body.period_start, body.period_end)
    await session.flush()
    # Generate PDF now that we have an id
    practice = await session.get(Practice, body.practice_id)
    generate_statement_pdf(statement, practice)
    return await _statement_out(statement, session)


@router.get("/ops/statements")
async def list_statements_ops(
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_role(Role.ops_admin)),
):
    result = await session.execute(select(Statement).order_by(Statement.generated_at.desc()))
    statements = result.scalars().all()
    return [await _statement_out(s, session) for s in statements]


@router.get("/clinic/statements")
async def list_statements_clinic(
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
):
    if user.tenant_id is None:
        raise HTTPException(status_code=400, detail="No practice associated with this account")
    result = await session.execute(
        select(Statement)
        .where(Statement.practice_id == user.tenant_id)
        .order_by(Statement.generated_at.desc())
    )
    statements = result.scalars().all()
    return [await _statement_out(s, session) for s in statements]


@router.get("/statements/{statement_id}/pdf")
async def download_statement_pdf(
    statement_id: int,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
):
    statement = await session.get(Statement, statement_id)
    if statement is None:
        raise HTTPException(status_code=404, detail="Statement not found")

    # Clinic users can only see their own practice's statements
    if not user.is_ops and user.tenant_id != statement.practice_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # (Re-)generate PDF if path missing or file gone
    if not statement.pdf_path or not __import__("os").path.exists(statement.pdf_path):
        practice = await session.get(Practice, statement.practice_id)
        generate_statement_pdf(statement, practice)

    return FileResponse(statement.pdf_path, media_type="application/pdf", filename=f"statement_{statement_id}.pdf")


@router.post("/ops/statements/{statement_id}/send")
async def mark_statement_sent(
    statement_id: int,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_role(Role.ops_admin)),
):
    statement = await session.get(Statement, statement_id)
    if statement is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    if statement.status == "sent":
        raise HTTPException(status_code=400, detail="Statement already sent")

    # TODO: In production, create a Stripe invoice here using the Stripe Python SDK.
    # stripe.Invoice.create(customer=practice.stripe_customer_id, amount=statement.fee_amount, ...)
    # statement.stripe_invoice_id = invoice.id
    # Never store card or bank numbers ourselves.

    statement.status = "sent"
    statement.sent_at = datetime.now(timezone.utc)
    await session.flush()
    return await _statement_out(statement, session)
