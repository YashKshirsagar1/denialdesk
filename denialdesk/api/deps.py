from collections.abc import AsyncGenerator
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
