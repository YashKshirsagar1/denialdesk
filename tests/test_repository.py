import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from denialdesk.models.case import Base, Batch, Case, CaseState, Practice
from denialdesk.repositories import CaseRepository


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


async def _seed_practice_and_batch(session: AsyncSession) -> tuple[Practice, Batch]:
    practice = Practice(name="Riverside Internal Medicine", specialty="Internal Medicine")
    session.add(practice)
    await session.flush()
    batch = Batch(practice_id=practice.id, source_files="test.csv")
    session.add(batch)
    await session.flush()
    return practice, batch


async def test_create_case(session: AsyncSession):
    _, batch = await _seed_practice_and_batch(session)
    repo = CaseRepository(session)
    case = await repo.create_case(batch_id=batch.id, payer="Aetna Health Inc")
    assert case.id is not None
    assert case.payer == "Aetna Health Inc"
    assert case.state == CaseState.ingested


async def test_get_case_returns_case(session: AsyncSession):
    _, batch = await _seed_practice_and_batch(session)
    repo = CaseRepository(session)
    created = await repo.create_case(batch_id=batch.id, payer="UnitedHealthcare")
    fetched = await repo.get_case(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.payer == "UnitedHealthcare"


async def test_get_case_returns_none_for_missing(session: AsyncSession):
    repo = CaseRepository(session)
    result = await repo.get_case(999999)
    assert result is None


async def test_list_cases_no_filter(session: AsyncSession):
    _, batch = await _seed_practice_and_batch(session)
    repo = CaseRepository(session)
    await repo.create_case(batch_id=batch.id, payer="Cigna Health")
    await repo.create_case(batch_id=batch.id, payer="Humana Inc")
    cases = await repo.list_cases()
    assert len(cases) == 2


async def test_list_cases_with_state_filter(session: AsyncSession):
    _, batch = await _seed_practice_and_batch(session)
    repo = CaseRepository(session)
    c1 = await repo.create_case(batch_id=batch.id, payer="Aetna Health Inc")
    await repo.create_case(batch_id=batch.id, payer="Cigna Health")

    await repo.transition_case(c1.id, CaseState.diagnosed, actor="system")
    await session.commit()

    ingested = await repo.list_cases(state=CaseState.ingested)
    diagnosed = await repo.list_cases(state=CaseState.diagnosed)
    assert len(ingested) == 1
    assert len(diagnosed) == 1
    assert diagnosed[0].id == c1.id


async def test_list_cases_pagination(session: AsyncSession):
    _, batch = await _seed_practice_and_batch(session)
    repo = CaseRepository(session)
    for i in range(5):
        await repo.create_case(batch_id=batch.id, payer=f"Payer {i}")
    page1 = await repo.list_cases(limit=3, offset=0)
    page2 = await repo.list_cases(limit=3, offset=3)
    assert len(page1) == 3
    assert len(page2) == 2


async def test_transition_case_updates_state(session: AsyncSession):
    _, batch = await _seed_practice_and_batch(session)
    repo = CaseRepository(session)
    case = await repo.create_case(batch_id=batch.id, payer="BlueCross BlueShield")
    updated_case, event = await repo.transition_case(
        case.id, CaseState.diagnosed, actor="agent:diagnosis", note="score=0.72"
    )
    assert updated_case.state == CaseState.diagnosed
    assert event.id is not None
    assert event.actor == "agent:diagnosis"
    assert "ingested->diagnosed" in event.action


async def test_transition_case_creates_audit_event_in_db(session: AsyncSession):
    _, batch = await _seed_practice_and_batch(session)
    repo = CaseRepository(session)
    case = await repo.create_case(batch_id=batch.id, payer="Humana Inc")
    await repo.transition_case(case.id, CaseState.diagnosed, actor="system")
    await session.commit()

    trail = await repo.get_audit_trail(case.id)
    assert len(trail) == 1
    assert "ingested->diagnosed" in trail[0].action


async def test_get_audit_trail_ordered(session: AsyncSession):
    _, batch = await _seed_practice_and_batch(session)
    repo = CaseRepository(session)
    case = await repo.create_case(batch_id=batch.id, payer="Aetna Health Inc")

    await repo.transition_case(case.id, CaseState.diagnosed, actor="system")
    await repo.transition_case(case.id, CaseState.approved, actor="human")
    await session.commit()

    trail = await repo.get_audit_trail(case.id)
    assert len(trail) == 2
    assert "ingested->diagnosed" in trail[0].action
    assert "diagnosed->approved" in trail[1].action


async def test_transition_invalid_raises_value_error(session: AsyncSession):
    _, batch = await _seed_practice_and_batch(session)
    repo = CaseRepository(session)
    case = await repo.create_case(batch_id=batch.id, payer="Cigna Health")
    with pytest.raises(ValueError, match="Invalid transition"):
        await repo.transition_case(case.id, CaseState.paid, actor="system")


async def test_transition_nonexistent_case_raises(session: AsyncSession):
    repo = CaseRepository(session)
    with pytest.raises(ValueError, match="not found"):
        await repo.transition_case(999999, CaseState.diagnosed, actor="system")
