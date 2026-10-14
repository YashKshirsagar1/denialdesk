from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from denialdesk.config import settings

engine = create_async_engine(settings.database_url, echo=False)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
