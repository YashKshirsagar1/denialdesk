import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from denialdesk.models.case import Base
from denialdesk.repositories.playbook_repository import PlaybookRepository


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


async def test_get_strategy_no_match(session: AsyncSession):
    repo = PlaybookRepository(session)
    result = await repo.get_strategy("Aetna Health Inc", "50")
    assert result is None


async def test_record_attempt_creates_entry(session: AsyncSession):
    repo = PlaybookRepository(session)
    entry = await repo.record_attempt(
        payer="Aetna Health Inc",
        reason_code="50",
        specialty="Cardiology",
        winning_strategy="Attach clinical notes and physician letter.",
        required_docs=["clinical_notes", "physician_letter"],
    )
    assert entry.id is not None
    assert entry.attempt_count == 1
    assert entry.success_count == 0

    found = await repo.get_strategy("Aetna Health Inc", "50", specialty="Cardiology")
    assert found is not None
    assert found.payer == "Aetna Health Inc"


async def test_record_win_increments(session: AsyncSession):
    repo = PlaybookRepository(session)
    await repo.record_attempt(
        payer="UnitedHealthcare",
        reason_code="16",
        specialty="Internal Medicine",
        winning_strategy="Submit completed claim form.",
        required_docs=["completed_claim_form"],
    )
    await repo.record_win("UnitedHealthcare", "16", "Internal Medicine")
    entry = await repo.get_strategy("UnitedHealthcare", "16", specialty="Internal Medicine")
    assert entry is not None
    assert entry.success_count == 1


async def test_get_strategy_prefers_specific_match(session: AsyncSession):
    repo = PlaybookRepository(session)
    # Generic entry (no specialty)
    await repo.record_attempt(
        payer="Cigna Health",
        reason_code="97",
        specialty="General",
        winning_strategy="Generic strategy.",
        required_docs=["operative_report"],
    )
    # Wait — specialty-specific match requires matching specialty param
    # Add a specific one with the exact specialty we'll query
    await repo.record_attempt(
        payer="Cigna Health",
        reason_code="97",
        specialty="Orthopedics",
        winning_strategy="Attach modifier justification and operative report.",
        required_docs=["modifier_justification", "operative_report"],
    )

    result = await repo.get_strategy("Cigna Health", "97", specialty="Orthopedics")
    assert result is not None
    assert result.specialty == "Orthopedics"
    assert "modifier" in (result.winning_strategy or "")
