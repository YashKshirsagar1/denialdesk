import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_auth
from denialdesk.auth.demo import DEMO_PASSWORD, DEMO_USERS
from denialdesk.auth.jwt import create_dev_token
from denialdesk.auth.models import Role, UserClaims
from denialdesk.auth.passwords import (
    DUMMY_HASH,
    hash_password,
    validate_password_strength,
    verify_password,
)
from denialdesk.config import settings
from denialdesk.models.case import OnboardingStatus, Practice, User

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DevTokenRequest(BaseModel):
    user_id: str = "dev-user"
    email: str = "dev@denialdesk.local"
    tenant_id: int | None = 1
    role: str = "clinic_admin"


class DevTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: int | None


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    practice_name: str = Field(min_length=2, max_length=255)
    specialty: str = Field(min_length=2, max_length=100)
    full_name: str = Field(min_length=2, max_length=200)
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    tenant_id: int | None
    practice_name: str | None = None
    must_change_password: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    # SQLite returns naive datetimes; treat them as UTC.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _user_out(session: AsyncSession, user: User) -> UserOut:
    practice_name = None
    if user.tenant_id is not None:
        practice = await session.get(Practice, user.tenant_id)
        practice_name = practice.name if practice else None
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=user.tenant_id,
        practice_name=practice_name,
        must_change_password=user.must_change_password,
    )


def _issue(user: User) -> str:
    return create_dev_token(
        user_id=str(user.id),
        email=user.email,
        tenant_id=user.tenant_id,
        role=Role(user.role),
        name=user.full_name,
    )


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> LoginResponse:
    email = body.email.strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()

    # Always run one hash verification so response time doesn't leak whether the email exists.
    password_ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)

    locked_until = _aware(user.locked_until) if user else None
    if user and locked_until and locked_until > _now():
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a few minutes.")

    if not user or not user.is_active or not password_ok:
        if user and user.is_active:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILED_LOGINS:
                user.locked_until = _now() + timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_logins = 0
            await session.commit()  # persist the counter even though we're raising
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = _now()
    return LoginResponse(access_token=_issue(user), user=await _user_out(session, user))


@router.post("/signup", response_model=LoginResponse, status_code=201)
async def signup(body: SignupRequest, session: AsyncSession = Depends(get_session)) -> LoginResponse:
    """Create a clinic + its first admin. The clinic stays locked until ops activates it."""
    if not settings.allow_signup:
        raise HTTPException(status_code=403, detail="Signup is disabled. Contact DenialDesk for an invitation.")
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    problem = validate_password_strength(body.password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    existing = (await session.execute(select(User.id).where(User.email == email))).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    practice = Practice(
        name=body.practice_name.strip(),
        specialty=body.specialty.strip(),
        contact=email,
        onboarding_status=OnboardingStatus.pending_agreements.value,
    )
    session.add(practice)
    await session.flush()
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        role=Role.clinic_admin.value,
        tenant_id=practice.id,
        last_login_at=_now(),
    )
    session.add(user)
    await session.flush()
    return LoginResponse(access_token=_issue(user), user=await _user_out(session, user))


@router.get("/me", response_model=UserOut)
async def me(
    claims: UserClaims = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    try:
        user = await session.get(User, int(claims.user_id))
    except ValueError:
        user = None
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Account not found or disabled.")
    return await _user_out(session, user)


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    claims: UserClaims = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        user = await session.get(User, int(claims.user_id))
    except ValueError:
        user = None
    if user is None or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    problem = validate_password_strength(body.new_password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False


class DemoAccount(BaseModel):
    email: str
    full_name: str
    role: str


class DemoAccounts(BaseModel):
    password: str
    accounts: list[DemoAccount]


@router.get("/demo-accounts", response_model=DemoAccounts)
async def demo_accounts(session: AsyncSession = Depends(get_session)) -> DemoAccounts:
    """Lets the login screen offer one-click demo sign-in. 404 unless dev_mode is on."""
    if not settings.dev_mode:
        raise HTTPException(status_code=404, detail="Not found")
    emails = [e for e, *_ in DEMO_USERS]
    present = set((await session.execute(select(User.email).where(User.email.in_(emails)))).scalars())
    return DemoAccounts(
        password=DEMO_PASSWORD,
        accounts=[DemoAccount(email=e, full_name=n, role=r.value) for e, n, r, _ in DEMO_USERS if e in present],
    )


@router.post("/dev-token", response_model=DevTokenResponse)
async def get_dev_token(body: DevTokenRequest) -> DevTokenResponse:
    """Issue a signed dev JWT. Only available when dev_mode=True."""
    if not settings.dev_mode:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        role = Role(body.role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Choose from: {[r.value for r in Role]}",
        )
    token = create_dev_token(body.user_id, body.email, body.tenant_id, role)
    return DevTokenResponse(access_token=token, role=body.role, tenant_id=body.tenant_id)
