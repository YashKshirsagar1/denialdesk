"""
Create all tables directly from SQLAlchemy models (SQLite dev only).
For production (PostgreSQL), use: alembic upgrade head
"""
import sys
import asyncio
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine
from denialdesk.models.case import Base

async def main():
    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data/dev.db")
    if db_url.startswith("sqlite") and "+aiosqlite" not in db_url:
        db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print(f"[init] All tables created in {db_url}")

asyncio.run(main())
