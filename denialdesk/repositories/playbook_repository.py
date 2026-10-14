import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.models.case import PayerPlaybook


class PlaybookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_strategy(
        self,
        payer: str,
        reason_code: str,
        specialty: str | None = None,
    ) -> PayerPlaybook | None:
        """Return best matching playbook entry: payer+reason+specialty > payer+reason > reason."""
        if specialty:
            stmt = select(PayerPlaybook).where(
                PayerPlaybook.payer == payer,
                PayerPlaybook.reason_code == reason_code,
                PayerPlaybook.specialty == specialty,
            ).limit(1)
            result = await self._session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return row

        stmt = select(PayerPlaybook).where(
            PayerPlaybook.payer == payer,
            PayerPlaybook.reason_code == reason_code,
            PayerPlaybook.specialty.is_(None),
        ).limit(1)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return row

        stmt = select(PayerPlaybook).where(
            PayerPlaybook.reason_code == reason_code,
        ).order_by(PayerPlaybook.success_count.desc()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def record_attempt(
        self,
        payer: str,
        reason_code: str,
        specialty: str,
        winning_strategy: str,
        required_docs: list[str],
    ) -> PayerPlaybook:
        """Upsert a playbook entry, incrementing attempt_count."""
        stmt = select(PayerPlaybook).where(
            PayerPlaybook.payer == payer,
            PayerPlaybook.reason_code == reason_code,
            PayerPlaybook.specialty == specialty,
        ).limit(1)
        result = await self._session.execute(stmt)
        entry = result.scalar_one_or_none()

        if entry is None:
            entry = PayerPlaybook(
                payer=payer,
                reason_code=reason_code,
                specialty=specialty,
                winning_strategy=winning_strategy,
                required_docs=json.dumps(required_docs),
                attempt_count=1,
                success_count=0,
            )
            self._session.add(entry)
        else:
            entry.attempt_count += 1
            entry.winning_strategy = winning_strategy
            entry.required_docs = json.dumps(required_docs)

        await self._session.flush()
        await self._session.refresh(entry)
        return entry

    async def record_win(self, payer: str, reason_code: str, specialty: str) -> None:
        """Increment success_count for a matching playbook entry."""
        stmt = select(PayerPlaybook).where(
            PayerPlaybook.payer == payer,
            PayerPlaybook.reason_code == reason_code,
            PayerPlaybook.specialty == specialty,
        ).limit(1)
        result = await self._session.execute(stmt)
        entry = result.scalar_one_or_none()
        if entry is not None:
            entry.success_count += 1
            await self._session.flush()
