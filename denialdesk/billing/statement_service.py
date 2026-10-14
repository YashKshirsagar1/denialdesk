"""Generates monthly statements for a practice.

Covers all verified outcomes whose paid_date falls within the period
that have not been included in any prior statement for that practice.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.billing.fees import calculate_fee
from denialdesk.models.case import Case, Outcome, Practice, Statement


class StatementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate(self, practice_id: int, period_start: date, period_end: date) -> Statement:
        practice = await self.session.get(Practice, practice_id)
        if practice is None:
            raise ValueError(f"Practice {practice_id} not found")

        # Find all verified outcomes for this practice in the period
        stmt = (
            select(Outcome)
            .join(Case, Case.id == Outcome.case_id)
            .where(
                Case.tenant_id == practice_id,
                Outcome.verified == True,  # noqa: E712
                Outcome.paid_date >= datetime(period_start.year, period_start.month, period_start.day, tzinfo=timezone.utc),
                Outcome.paid_date <= datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc),
            )
        )
        result = await self.session.execute(stmt)
        outcomes = result.scalars().all()

        # Collect case_ids already billed in prior statements for this practice
        prior_stmt = select(Statement).where(Statement.practice_id == practice_id)
        prior_result = await self.session.execute(prior_stmt)
        prior_statements = prior_result.scalars().all()
        already_billed: set[int] = set()
        for s in prior_statements:
            if s.line_items:
                for item in json.loads(s.line_items):
                    already_billed.add(item["case_id"])

        # Load associated cases for denial_date
        case_ids = [o.case_id for o in outcomes if o.case_id not in already_billed]
        cases_result = await self.session.execute(select(Case).where(Case.id.in_(case_ids)))
        cases_by_id = {c.id: c for c in cases_result.scalars().all()}

        fee_rate_standard = Decimal(str(practice.fee_rate_standard))
        fee_rate_aged = Decimal(str(practice.fee_rate_aged))
        aged_threshold = int(practice.aged_threshold_days)

        line_items = []
        total_recovered = Decimal("0")
        total_fee = Decimal("0")

        for outcome in outcomes:
            if outcome.case_id in already_billed:
                continue
            case = cases_by_id.get(outcome.case_id)
            denial_date = case.denial_date.date() if case and case.denial_date else None
            amount = Decimal(str(outcome.amount_recovered or 0))
            fee, aged, rate = calculate_fee(amount, denial_date, fee_rate_standard, fee_rate_aged, aged_threshold)
            line_items.append({
                "case_id": outcome.case_id,
                "patient_ref": case.patient_ref if case else None,
                "denial_date": denial_date.isoformat() if denial_date else None,
                "amount_recovered": float(amount),
                "fee": float(fee),
                "rate": float(rate),
                "aged": aged,
            })
            total_recovered += amount
            total_fee += fee

        statement = Statement(
            practice_id=practice_id,
            period_start=period_start,
            period_end=period_end,
            total_recovered=float(total_recovered),
            fee_amount=float(total_fee),
            status="draft",
            line_items=json.dumps(line_items),
            generated_at=datetime.now(timezone.utc),
        )
        self.session.add(statement)
        await self.session.flush()
        return statement
