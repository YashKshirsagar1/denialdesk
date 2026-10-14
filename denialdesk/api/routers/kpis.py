from datetime import timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.api.deps import get_session, require_role
from denialdesk.api.schemas.kpis import (
    OverviewKPIs,
    PipelineStage,
    PipelineView,
    ScoreAccuracy,
    ScoreAccuracyRow,
    WinRateRow,
    WinRateTable,
)
from denialdesk.auth.models import Role, UserClaims
from denialdesk.models.case import Case, CaseState, Diagnosis, Outcome
from denialdesk.repositories.playbook_repository import PlaybookRepository

router = APIRouter(prefix="/kpis", tags=["kpis"])

_ops_only = require_role(Role.ops_admin)

_ATTEMPTED_STATES = {
    CaseState.submitted,
    CaseState.pending_payer,
    CaseState.paid,
    CaseState.re_denied,
    CaseState.escalated,
    CaseState.closed,
}

_SCORE_BUCKETS = [
    ("0.0–0.2", 0.0, 0.2),
    ("0.2–0.4", 0.2, 0.4),
    ("0.4–0.6", 0.4, 0.6),
    ("0.6–0.8", 0.6, 0.8),
    ("0.8–1.0", 0.8, 1.01),
]


@router.get("/overview", response_model=OverviewKPIs)
async def get_overview(
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_ops_only),
):
    # Total cases
    total_cases_r = await session.execute(select(func.count()).select_from(Case))
    total_cases = total_cases_r.scalar_one() or 0

    # All cases for state-based counts
    all_cases_r = await session.execute(select(Case.state))
    all_states = [row[0] for row in all_cases_r.fetchall()]

    total_attempted = sum(1 for s in all_states if s in _ATTEMPTED_STATES)
    total_declined = sum(1 for s in all_states if s == CaseState.declined)

    # Pipeline dict
    pipeline: dict[str, int] = {}
    for s in all_states:
        key = s.value if hasattr(s, "value") else str(s)
        pipeline[key] = pipeline.get(key, 0) + 1

    # Amount billed
    billed_r = await session.execute(select(func.sum(Case.billed_amt)))
    total_amount_billed = float(billed_r.scalar_one() or 0)

    # Outcomes
    outcomes_r = await session.execute(select(Outcome))
    outcomes = outcomes_r.scalars().all()
    paid_outcomes = [o for o in outcomes if o.result in ("paid", "partially_paid")]
    total_paid = len(paid_outcomes)
    total_amount_recovered = sum(float(o.amount_recovered or 0) for o in paid_outcomes)
    avg_amount_recovered = total_amount_recovered / total_paid if total_paid else 0.0

    paid_case_ids = {o.case_id for o in paid_outcomes}
    closed_r = await session.execute(
        select(Case.id).where(Case.state == CaseState.closed)
    )
    closed_ids = {row[0] for row in closed_r.fetchall()}
    total_denied_final = len(closed_ids - paid_case_ids)

    # Avg winnability
    avg_w_r = await session.execute(select(func.avg(Diagnosis.winnability_score)))
    avg_winnability_score = float(avg_w_r.scalar_one() or 0.0)

    # Avg days to payment
    avg_days_to_payment = 0.0
    if paid_outcomes:
        paid_case_ids_list = [o.case_id for o in paid_outcomes if o.paid_date]
        if paid_case_ids_list:
            cases_r = await session.execute(
                select(Case).where(Case.id.in_(paid_case_ids_list))
            )
            cases_map = {c.id: c for c in cases_r.scalars().all()}
            days_list = []
            for o in paid_outcomes:
                if o.paid_date and o.case_id in cases_map:
                    c = cases_map[o.case_id]
                    paid_dt = o.paid_date
                    created_dt = c.created_at
                    if paid_dt.tzinfo is None:
                        paid_dt = paid_dt.replace(tzinfo=timezone.utc)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    days_list.append((paid_dt - created_dt).days)
            avg_days_to_payment = sum(days_list) / len(days_list) if days_list else 0.0

    # Rates
    recovery_rate = total_paid / total_attempted if total_attempted else 0.0
    decline_rate = total_declined / (total_declined + total_attempted) if (total_declined + total_attempted) else 0.0

    return OverviewKPIs(
        total_cases=total_cases,
        total_attempted=total_attempted,
        total_paid=total_paid,
        total_denied_final=total_denied_final,
        recovery_rate=round(recovery_rate, 4),
        total_amount_billed=total_amount_billed,
        total_amount_recovered=total_amount_recovered,
        avg_amount_recovered=avg_amount_recovered,
        total_declined=total_declined,
        decline_rate=round(decline_rate, 4),
        avg_winnability_score=round(avg_winnability_score, 4),
        avg_days_to_payment=round(avg_days_to_payment, 1),
        pipeline=pipeline,
    )


@router.get("/win-rates", response_model=WinRateTable)
async def get_win_rates(
    min_attempts: int = 1,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_ops_only),
):
    result = await session.execute(
        text(
            "SELECT payer, reason_code, specialty, attempt_count, success_count, "
            "CAST(success_count AS FLOAT) / attempt_count AS win_rate "
            "FROM payer_playbooks "
            "WHERE attempt_count >= :min_attempts "
            "ORDER BY win_rate DESC"
        ),
        {"min_attempts": min_attempts},
    )
    rows = [
        WinRateRow(
            payer=row.payer,
            reason_code=row.reason_code,
            specialty=row.specialty or "unknown",
            attempts=row.attempt_count,
            wins=row.success_count,
            win_rate=round(row.win_rate, 4),
        )
        for row in result.fetchall()
    ]
    return WinRateTable(rows=rows, total_rows=len(rows))


@router.get("/score-accuracy", response_model=ScoreAccuracy)
async def get_score_accuracy(
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_ops_only),
):
    diag_r = await session.execute(select(Diagnosis))
    diagnoses = {d.case_id: d for d in diag_r.scalars().all()}

    outcome_r = await session.execute(select(Outcome))
    outcomes = {o.case_id: o for o in outcome_r.scalars().all()}

    paired = [
        (diagnoses[cid], outcomes[cid])
        for cid in diagnoses
        if cid in outcomes and diagnoses[cid].winnability_score is not None
    ]

    rows: list[ScoreAccuracyRow] = []
    for label, lo, hi in _SCORE_BUCKETS:
        bucket = [(d, o) for d, o in paired if lo <= d.winnability_score < hi]
        if not bucket:
            continue
        wins = sum(1 for _, o in bucket if o.result in ("paid", "partially_paid"))
        rows.append(
            ScoreAccuracyRow(
                score_bucket=label,
                count=len(bucket),
                actual_win_rate=round(wins / len(bucket), 4),
                avg_predicted_score=round(
                    sum(d.winnability_score for d, _ in bucket) / len(bucket), 4
                ),
            )
        )

    return ScoreAccuracy(
        rows=rows,
        correlation_note=f"Based on {len(paired)} cases with outcomes",
    )


@router.get("/pipeline", response_model=PipelineView)
async def get_pipeline(
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(_ops_only),
):
    result = await session.execute(
        text("SELECT state, COUNT(*) as cnt FROM cases GROUP BY state")
    )
    raw = result.fetchall()
    total = sum(row.cnt for row in raw)
    stages = [
        PipelineStage(
            state=row.state,
            count=row.cnt,
            pct=round(row.cnt / total, 4) if total else 0.0,
        )
        for row in sorted(raw, key=lambda r: r.cnt, reverse=True)
    ]
    return PipelineView(stages=stages, total=total)
