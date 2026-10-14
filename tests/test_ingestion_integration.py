"""Integration tests for the ingestion pipeline using in-memory SQLite."""
import os
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from denialdesk.models.case import AuditEvent, Base, Batch, Case, CaseState, Practice
from denialdesk.ingestion.pipeline import IngestionPipeline

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = AsyncSession(engine, expire_on_commit=False)
    try:
        yield async_session
    finally:
        await async_session.close()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def _seed_practice(session: AsyncSession) -> Practice:
    practice = Practice(name="Test Practice", specialty="Internal Medicine")
    session.add(practice)
    await session.flush()
    return practice


@pytest.mark.skipif(not (DATA_DIR / "sample_claims.csv").exists(), reason="sample_claims.csv not generated")
async def test_ingest_csv_creates_batch_and_cases(session: AsyncSession):
    practice = await _seed_practice(session)
    csv_content = (DATA_DIR / "sample_claims.csv").read_bytes()

    pipeline = IngestionPipeline(session)
    result = await pipeline.ingest_file("sample_claims.csv", csv_content, practice.id)

    assert result.source_format == "csv"
    assert len(result.records) > 0

    batches = list((await session.execute(select(Batch))).scalars().all())
    assert len(batches) == 1

    cases = list((await session.execute(select(Case))).scalars().all())
    assert len(cases) == len(result.records)
    assert all(c.state == CaseState.ingested for c in cases)


@pytest.mark.skipif(not (DATA_DIR / "sample_claims.835").exists(), reason="sample_claims.835 not generated")
async def test_ingest_835_creates_cases(session: AsyncSession):
    practice = await _seed_practice(session)
    x12_content = (DATA_DIR / "sample_claims.835").read_bytes()

    pipeline = IngestionPipeline(session)
    result = await pipeline.ingest_file("sample_claims.835", x12_content, practice.id)

    assert result.source_format == "x12_835"
    assert len(result.records) > 0

    cases = list((await session.execute(select(Case))).scalars().all())
    assert len(cases) == len(result.records)
    assert all(c.state == CaseState.ingested for c in cases)


@pytest.mark.skipif(not (DATA_DIR / "sample_claims.csv").exists(), reason="sample_claims.csv not generated")
async def test_audit_events_created(session: AsyncSession):
    practice = await _seed_practice(session)
    csv_content = (DATA_DIR / "sample_claims.csv").read_bytes()

    pipeline = IngestionPipeline(session)
    result = await pipeline.ingest_file("sample_claims.csv", csv_content, practice.id)

    cases = list((await session.execute(select(Case))).scalars().all())
    for case in cases:
        events = list(
            (await session.execute(
                select(AuditEvent).where(AuditEvent.case_id == case.id)
            )).scalars().all()
        )
        assert len(events) == 1
        assert events[0].actor == "ingestion_pipeline"
        assert "ingested from" in events[0].action
