from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel


class OutcomeRequest(BaseModel):
    result: Literal["paid", "partially_paid", "denied"]
    amount_recovered: float = 0.0
    paid_date: Optional[date] = None
    notes: str = ""


class OutcomeResponse(BaseModel):
    case_id: int
    outcome_id: int
    new_state: str
    amount_recovered: float
    playbook_updated: bool
    message: str


class OutcomeSummary(BaseModel):
    total_cases_with_outcomes: int
    total_paid: int
    total_denied: int
    total_amount_recovered: float
    win_rate: float
    avg_amount_recovered: float
