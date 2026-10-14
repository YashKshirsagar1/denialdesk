from collections.abc import AsyncGenerator
from typing import Optional

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from denialdesk.auth.jwt import verify_token
from denialdesk.auth.models import Role, UserClaims
from denialdesk.config import settings
from denialdesk.repositories.tenant_scoped import TenantContext


def _make_session_factory(url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


_default_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _default_factory
    if _default_factory is None:
        url = settings.database_url
        if url.startswith("sqlite") and "+aiosqlite" not in url:
            url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        _default_factory = _make_session_factory(url)
    return _default_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# JWT auth (new in Phase 2 Step 3)
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserClaims | None:
    """Extract and verify JWT from Authorization: Bearer <token> header."""
    if credentials is None:
        return None
    return verify_token(credentials.credentials)


async def require_auth(
    user: UserClaims | None = Depends(get_current_user),
) -> UserClaims:
    """Raises 401 if no valid token is present."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(*roles: Role):
    """Dependency factory: raises 403 if the user's role is not in the allowed set."""

    async def _check(user: UserClaims = Depends(require_auth)) -> UserClaims:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role.value}' not permitted. Required: {[r.value for r in roles]}",
            )
        return user

    return _check


# ---------------------------------------------------------------------------
# Legacy X-Tenant-ID header functions (kept for backwards compatibility)
# These are tested directly in test_tenant_isolation.py.
# ---------------------------------------------------------------------------


def get_tenant_context(
    x_tenant_id: Optional[str] = Header(default=None),
) -> Optional[TenantContext]:
    if x_tenant_id is None:
        return None
    try:
        return TenantContext(tenant_id=int(x_tenant_id))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="X-Tenant-ID must be an integer")


def require_tenant_context(
    tenant: Optional[TenantContext] = Depends(get_tenant_context),
) -> TenantContext:
    if tenant is None:
        raise HTTPException(status_code=401, detail="X-Tenant-ID header is required")
    return tenant


async def require_active_practice(
    user: UserClaims = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """Raises 403 if the clinic's practice is not in 'active' onboarding_status.

    Ops roles bypass this check (they are not bound to a single practice).
    Clinic users cannot upload until BAA + SA are signed by an ops admin.
    """
    from denialdesk.models.case import OnboardingStatus, Practice  # local import to avoid circular

    if user.is_ops:
        return None
    if user.tenant_id is None:
        raise HTTPException(status_code=403, detail="No practice associated with this account")
    practice = await session.get(Practice, user.tenant_id)
    if practice is None:
        raise HTTPException(status_code=403, detail="Practice not found")
    if practice.onboarding_status != OnboardingStatus.active.value:
        raise HTTPException(
            status_code=403,
            detail=f"Account not yet active. Onboarding status: {practice.onboarding_status}. "
                   "Please complete the onboarding process.",
        )
    return practice
