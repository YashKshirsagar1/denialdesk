from datetime import date
from typing import Optional

from pydantic import BaseModel


class DeadlineItem(BaseModel):
    case_id: int
    practice_name: Optional[str]
    payer: str
    patient_ref: Optional[str]
    cpt: str
    billed_amt: float
    state: str
    filing_deadline: date
    days_until_deadline: int
    urgency: str  # overdue | critical | warning | upcoming | ok
