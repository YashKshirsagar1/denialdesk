"""Ops onboarding endpoints — manage practices, sign agreements, track checklist."""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_auth, require_role
from denialdesk.auth.models import Role, UserClaims
from denialdesk.models.case import OnboardingStatus, PayerPortalAccess, Practice

router = APIRouter(prefix="/ops", tags=["onboarding"])

_ops_only = require_role(Role.ops_admin)
_ops_or_clinic_admin = require_role(Role.ops_admin, Role.clinic_admin)


# --------------------------------------------------------------------------- #
# Pydantic schemas
# --------------------------------------------------------------------------- #

class PracticeCreate(BaseModel):
    name: str
    specialty: str
    contact: Optional[str] = None


class PracticeUpdate(BaseModel):
    name: Optional[str] = None
    specialty: Optional[str] = None
    contact: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    npi: Optional[str] = None
    specialties: Optional[list[str]] = None
    payers_billed: Optional[list[str]] = None


class PracticeOut(BaseModel):
    id: int
    name: str
    specialty: str
    contact: Optional[str]
    onboarding_status: str
    baa_signed: bool
    service_agreement_signed: bool
    address: Optional[str]
    phone: Optional[str]
    npi: Optional[str]
    specialties: Optional[list[str]]
    payers_billed: Optional[list[str]]


class PayerPortalCreate(BaseModel):
    payer: str
    portal_url: Optional[str] = None
    our_username: Optional[str] = None
    notes: Optional[str] = None


class PayerPortalOut(BaseModel):
    id: int
    practice_id: int
    payer: str
    portal_url: Optional[str]
    our_username: Optional[str]
    notes: Optional[str]
    created_by: str


def _practice_out(p: Practice) -> PracticeOut:
    specialties = json.loads(p.specialties) if p.specialties else None
    payers_billed = json.loads(p.payers_billed) if p.payers_billed else None
    return PracticeOut(
        id=p.id,
        name=p.name,
        specialty=p.specialty,
        contact=p.contact,
        onboarding_status=p.onboarding_status,
        baa_signed=p.baa_signed_at is not None,
        service_agreement_signed=p.service_agreement_signed_at is not None,
        address=p.address,
        phone=p.phone,
        npi=p.npi,
        specialties=specialties,
        payers_billed=payers_billed,
    )


# --------------------------------------------------------------------------- #
# Practice CRUD
# --------------------------------------------------------------------------- #

@router.post("/practices", response_model=PracticeOut, status_code=status.HTTP_201_CREATED)
async def create_practice(
    body: PracticeCreate,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_ops_only),
):
    """Create a new practice. Starts in pending_agreements status."""
    practice = Practice(
        name=body.name,
        specialty=body.specialty,
        contact=body.contact,
        onboarding_status=OnboardingStatus.pending_agreements.value,
    )
    session.add(practice)
    await session.flush()
    return _practice_out(practice)


@router.get("/practices", response_model=list[PracticeOut])
async def list_practices(
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_ops_only),
):
    result = await session.execute(select(Practice).order_by(Practice.name))
    return [_practice_out(p) for p in result.scalars().all()]


@router.get("/practices/{practice_id}", response_model=PracticeOut)
async def get_practice(
    practice_id: int,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(_ops_or_clinic_admin),
):
    """ops_admin can view any practice; clinic_admin can view only their own."""
    practice = await session.get(Practice, practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    if user.role == Role.clinic_admin and user.tenant_id != practice_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return _practice_out(practice)


@router.patch("/practices/{practice_id}", response_model=PracticeOut)
async def update_practice(
    practice_id: int,
    body: PracticeUpdate,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_ops_only),
):
    practice = await session.get(Practice, practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    if body.name is not None:
        practice.name = body.name
    if body.specialty is not None:
        practice.specialty = body.specialty
    if body.contact is not None:
        practice.contact = body.contact
    if body.address is not None:
        practice.address = body.address
    if body.phone is not None:
        practice.phone = body.phone
    if body.npi is not None:
        practice.npi = body.npi
    if body.specialties is not None:
        practice.specialties = json.dumps(body.specialties)
    if body.payers_billed is not None:
        practice.payers_billed = json.dumps(body.payers_billed)
    await session.flush()
    return _practice_out(practice)


# --------------------------------------------------------------------------- #
# Agreement signing
# --------------------------------------------------------------------------- #

@router.post("/practices/{practice_id}/sign-baa", response_model=PracticeOut)
async def sign_baa(
    practice_id: int,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(_ops_only),
):
    practice = await session.get(Practice, practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    practice.baa_signed_at = datetime.now(timezone.utc)
    practice.baa_signed_by = user.user_id
    await session.flush()
    return _practice_out(practice)


@router.post("/practices/{practice_id}/sign-service-agreement", response_model=PracticeOut)
async def sign_service_agreement(
    practice_id: int,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(_ops_only),
):
    practice = await session.get(Practice, practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    practice.service_agreement_signed_at = datetime.now(timezone.utc)
    practice.service_agreement_signed_by = user.user_id
    await session.flush()
    return _practice_out(practice)


@router.post("/practices/{practice_id}/activate", response_model=PracticeOut)
async def activate_practice(
    practice_id: int,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_ops_only),
):
    practice = await session.get(Practice, practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    if practice.baa_signed_at is None or practice.service_agreement_signed_at is None:
        raise HTTPException(
            status_code=400,
            detail="Both BAA and service agreement must be signed before activation.",
        )
    practice.onboarding_status = OnboardingStatus.active.value
    await session.flush()
    return _practice_out(practice)


@router.post("/practices/{practice_id}/suspend", response_model=PracticeOut)
async def suspend_practice(
    practice_id: int,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_ops_only),
):
    practice = await session.get(Practice, practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    practice.onboarding_status = OnboardingStatus.suspended.value
    await session.flush()
    return _practice_out(practice)


# --------------------------------------------------------------------------- #
# Payer portal access
# --------------------------------------------------------------------------- #

@router.post("/practices/{practice_id}/payer-portals", response_model=PayerPortalOut, status_code=status.HTTP_201_CREATED)
async def add_payer_portal(
    practice_id: int,
    body: PayerPortalCreate,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(_ops_only),
):
    practice = await session.get(Practice, practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    entry = PayerPortalAccess(
        practice_id=practice_id,
        payer=body.payer,
        portal_url=body.portal_url,
        our_username=body.our_username,
        notes=body.notes,
        created_by=user.user_id,
    )
    session.add(entry)
    await session.flush()
    return PayerPortalOut(
        id=entry.id,
        practice_id=entry.practice_id,
        payer=entry.payer,
        portal_url=entry.portal_url,
        our_username=entry.our_username,
        notes=entry.notes,
        created_by=entry.created_by,
    )


@router.get("/practices/{practice_id}/payer-portals", response_model=list[PayerPortalOut])
async def list_payer_portals(
    practice_id: int,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_ops_only),
):
    result = await session.execute(
        select(PayerPortalAccess).where(PayerPortalAccess.practice_id == practice_id)
    )
    entries = result.scalars().all()
    return [
        PayerPortalOut(
            id=e.id,
            practice_id=e.practice_id,
            payer=e.payer,
            portal_url=e.portal_url,
            our_username=e.our_username,
            notes=e.notes,
            created_by=e.created_by,
        )
        for e in entries
    ]
