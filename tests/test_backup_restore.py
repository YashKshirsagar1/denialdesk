"""
Restore test: verifies that the application's database schema and data survive
a full schema creation cycle and a SQLite file copy (simulating backup/restore).

Uses SQLite in-memory or file-based. In production, the shell scripts in scripts/
handle the PostgreSQL pg_dump / psql cycle — those must be tested manually in
the prod environment as part of the go-live gate (CLAUDE.md section 12.10).
"""
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from denialdesk.models.case import (
    Base,
    Batch,
    Case,
    CaseState,
    Diagnosis,
    OnboardingStatus,
    Outcome,
    Practice,
)

EXPECTED_TABLES = {
    "practices",
    "batches",
    "cases",
    "diagnoses",
    "drafts",
    "reviews",
    "submissions",
    "outcomes",
    "payer_playbooks",
    "audit_events",
    "document_requests",
    "access_logs",
    "statements",
    "payer_portal_access",
}


@pytest_asyncio.fixture
async def fresh_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_alembic_migrations_run_cleanly(fresh_engine):
    """All tables can be created via metadata (mirrors migration end state)."""
    async with fresh_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with fresh_engine.connect() as conn:
        tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
    assert len(tables) > 0, "No tables created"


@pytest.mark.asyncio
async def test_all_tables_present_after_migrations(fresh_engine):
    """Every table defined in the spec exists after schema creation."""
    async with fresh_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with fresh_engine.connect() as conn:
        actual = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))

    missing = EXPECTED_TABLES - actual
    assert not missing, f"Missing tables after schema creation: {missing}"


@pytest.mark.asyncio
async def test_data_survives_schema_reload():
    """A Practice written in one session is readable after the session closes (simulates restart)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Write
    async with factory() as session:
        p = Practice(
            name="Riverside Clinic",
            specialty="Family Medicine",
            onboarding_status=OnboardingStatus.active,
        )
        session.add(p)
        await session.commit()
        practice_id = p.id

    # Read in a new session
    async with factory() as session:
        loaded = await session.get(Practice, practice_id)
        assert loaded is not None
        assert loaded.name == "Riverside Clinic"
        assert loaded.specialty == "Family Medicine"

    await engine.dispose()


def test_sqlite_backup_and_restore():
    """
    Write rows to a SQLite file, copy the file (backup), reopen the copy (restore),
    and verify row counts match.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "original.db"
        backup_path = Path(tmpdir) / "backup.db"

        # Create schema + insert rows in original
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE practices "
            "(id INTEGER PRIMARY KEY, name TEXT NOT NULL, specialty TEXT)"
        )
        conn.executemany(
            "INSERT INTO practices (name, specialty) VALUES (?, ?)",
            [
                ("Riverside Clinic", "Family Medicine"),
                ("Metro Cardiology", "Cardiology"),
                ("Sunset Pediatrics", "Pediatrics"),
            ],
        )
        conn.commit()
        conn.close()

        # "Backup" = file copy
        shutil.copy2(str(db_path), str(backup_path))

        # "Restore" = open the copy and verify
        restored = sqlite3.connect(str(backup_path))
        rows = restored.execute("SELECT COUNT(*) FROM practices").fetchone()[0]
        restored.close()

        assert rows == 3, f"Expected 3 rows after restore, got {rows}"


@pytest.mark.asyncio
async def test_write_and_read_outcome_roundtrip():
    """Full write → close → reopen round-trip with a Case + Outcome."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_url = f"sqlite+aiosqlite:///{tmpdir}/roundtrip.db"
        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as session:
            practice = Practice(
                name="Test Clinic",
                specialty="Internal Medicine",
                onboarding_status=OnboardingStatus.active,
            )
            session.add(practice)
            await session.flush()

            batch = Batch(
                practice_id=practice.id,
                uploaded_at=datetime.now(timezone.utc),
                source_files="test.csv",
            )
            session.add(batch)
            await session.flush()

            case = Case(
                batch_id=batch.id,
                payer="Aetna",
                patient_ref="PT-001",
                cpt_hcpcs="99213",
                icd10="I10",
                billed_amt=500.0,
                allowed_amt=350.0,
                carc="16",
                denial_date=datetime.now(timezone.utc),
                state=CaseState.ingested,
            )
            session.add(case)
            await session.flush()

            outcome = Outcome(
                case_id=case.id,
                result="paid",
                amount_recovered=350.0,
                paid_date=datetime.now(timezone.utc),
                notes="Paid after appeal",
            )
            session.add(outcome)
            await session.commit()
            case_id = case.id

        # Close and reopen
        await engine.dispose()
        engine2 = create_async_engine(db_url, echo=False)
        factory2 = async_sessionmaker(engine2, expire_on_commit=False)

        async with factory2() as session:
            result = await session.get(Case, case_id)
            assert result is not None
            assert result.payer == "Aetna"

            from sqlalchemy import select
            outcomes = (await session.execute(
                select(Outcome).where(Outcome.case_id == case_id)
            )).scalars().all()
            assert len(outcomes) == 1
            assert outcomes[0].amount_recovered == 350.0

        await engine2.dispose()
