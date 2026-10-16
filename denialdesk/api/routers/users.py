import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_role
from denialdesk.auth.models import Role, UserClaims
from denialdesk.auth.passwords import hash_password, validate_password_strength
from denialdesk.models.case import Practice, User

router = APIRouter(prefix="/users", tags=["users"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CLINIC_ROLES = {Role.clinic_admin.value, Role.clinic_staff.value}
_manage = require_role(Role.clinic_admin, Role.ops_admin)


class TeamMember(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    tenant_id: int | None
    practice_name: str | None = None
    is_active: bool
    last_login_at: str | None = None


class CreateUserBody(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=200)
    role: str
    temp_password: str
    tenant_id: int | None = None  # ops only; clinic admins always create into their own practice


class UpdateUserBody(BaseModel):
    is_active: bool | None = None
    role: str | None = None


def _out(u: User, practice_name: str | None) -> TeamMember:
    return TeamMember(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        role=u.role,
        tenant_id=u.tenant_id,
        practice_name=practice_name,
        is_active=u.is_active,
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
    )


@router.get("", response_model=list[TeamMember])
async def list_users(
    session: AsyncSession = Depends(get_session),
    caller: UserClaims = Depends(_manage),
):
    stmt = select(User, Practice.name).outerjoin(Practice, Practice.id == User.tenant_id).order_by(User.email)
    if caller.role == Role.clinic_admin:
        stmt = stmt.where(User.tenant_id == caller.tenant_id)
    rows = (await session.execute(stmt)).all()
    return [_out(u, name) for u, name in rows]


@router.post("", response_model=TeamMember, status_code=201)
async def create_user(
    body: CreateUserBody,
    session: AsyncSession = Depends(get_session),
    caller: UserClaims = Depends(_manage),
):
    try:
        role = Role(body.role)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid role.")
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    problem = validate_password_strength(body.temp_password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)

    if caller.role == Role.clinic_admin:
        if role.value not in _CLINIC_ROLES:
            raise HTTPException(status_code=403, detail="Clinic admins can only add clinic users.")
        tenant_id = caller.tenant_id
    else:
        tenant_id = body.tenant_id
        if role.value in _CLINIC_ROLES and tenant_id is None:
            raise HTTPException(status_code=422, detail="Clinic users must belong to a practice.")
        if role.value not in _CLINIC_ROLES:
            tenant_id = None  # internal staff are cross-tenant

    practice = await session.get(Practice, tenant_id) if tenant_id is not None else None
    if tenant_id is not None and practice is None:
        raise HTTPException(status_code=404, detail="Practice not found.")
    if (await session.execute(select(User.id).where(User.email == email))).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        email=email,
        password_hash=hash_password(body.temp_password),
        full_name=body.full_name.strip(),
        role=role.value,
        tenant_id=tenant_id,
        must_change_password=True,
    )
    session.add(user)
    await session.flush()
    return _out(user, practice.name if practice else None)


@router.patch("/{user_id}", response_model=TeamMember)
async def update_user(
    user_id: int,
    body: UpdateUserBody,
    session: AsyncSession = Depends(get_session),
    caller: UserClaims = Depends(_manage),
):
    user = await session.get(User, user_id)
    # Same 404 whether it doesn't exist or belongs to another clinic.
    if user is None or (caller.role == Role.clinic_admin and user.tenant_id != caller.tenant_id):
        raise HTTPException(status_code=404, detail="User not found.")
    if str(user.id) == caller.user_id and (body.is_active is False or body.role is not None):
        raise HTTPException(status_code=400, detail="You can't change your own access.")
    if body.role is not None:
        try:
            new_role = Role(body.role)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid role.")
        if caller.role == Role.clinic_admin and new_role.value not in _CLINIC_ROLES:
            raise HTTPException(status_code=403, detail="Clinic admins can only assign clinic roles.")
        if (new_role.value in _CLINIC_ROLES) != (user.role in _CLINIC_ROLES):
            raise HTTPException(status_code=422, detail="Can't move a user between clinic and internal roles.")
        user.role = new_role.value
    if body.is_active is not None:
        user.is_active = body.is_active
    practice = await session.get(Practice, user.tenant_id) if user.tenant_id is not None else None
    return _out(user, practice.name if practice else None)
