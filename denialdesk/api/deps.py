from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from denialdesk.config import settings


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
