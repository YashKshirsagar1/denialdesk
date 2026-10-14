from pydantic import BaseModel


class OverviewKPIs(BaseModel):
    total_cases: int
    total_attempted: int
    total_paid: int
    total_denied_final: int
    recovery_rate: float
    total_amount_billed: float
    total_amount_recovered: float
    avg_amount_recovered: float
    total_declined: int
    decline_rate: float
    avg_winnability_score: float
    avg_days_to_payment: float
    pipeline: dict[str, int]


class WinRateRow(BaseModel):
    payer: str
    reason_code: str
    specialty: str
    attempts: int
    wins: int
    win_rate: float


class WinRateTable(BaseModel):
    rows: list[WinRateRow]
    total_rows: int


class ScoreAccuracyRow(BaseModel):
    score_bucket: str
    count: int
    actual_win_rate: float
    avg_predicted_score: float


class ScoreAccuracy(BaseModel):
    rows: list[ScoreAccuracyRow]
    correlation_note: str


class PipelineStage(BaseModel):
    state: str
    count: int
    pct: float


class PipelineView(BaseModel):
    stages: list[PipelineStage]
    total: int
