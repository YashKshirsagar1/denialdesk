import json
import uuid
from datetime import date, datetime

from pydantic import BaseModel, field_validator


class DiagnosisSchema(BaseModel):
    root_cause: str
    winnability_score: float
    expected_value: float
    rationale: str
    model_version: str

    model_config = {"from_attributes": True}


class DraftSchema(BaseModel):
    id: int
    draft_type: str
    content: str
    attachments: list[str]
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_draft(cls, draft) -> "DraftSchema":
        attachments = draft.attachments or "[]"
        if isinstance(attachments, str):
            try:
                attachments = json.loads(attachments)
            except Exception:
                attachments = []
        return cls(
            id=draft.id,
            draft_type=draft.type,
            content=draft.content or "",
            attachments=attachments,
            version=draft.version,
            created_at=draft.created_at,
        )


class CaseSummary(BaseModel):
    id: int
    payer: str
    cpt: str
    billed_amt: float
    carc: str
    denial_date: date | None
    state: str
    winnability_score: float | None
    root_cause: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseDetail(CaseSummary):
    icd10: list[str]
    allowed_amt: float
    rarc: str
    filing_deadline: date | None
    diagnosis: DiagnosisSchema | None
    drafts: list[DraftSchema]


class QueueStats(BaseModel):
    awaiting_review: int
    drafted: int
    submitted: int
    paid: int
    declined: int
    total_active: int


class ClinicCaseSummary(BaseModel):
    """Case summary for the clinic portal — includes patient_ref, dos, updated_at."""

    id: int
    payer: str
    patient_ref: str | None
    dos: date | None
    cpt: str
    billed_amt: float
    carc: str
    denial_date: date | None
    state: str
    winnability_score: float | None
    root_cause: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClinicDashboard(BaseModel):
    dollars_submitted: float
    dollars_recovered: float
    cases_in_progress: int
    cases_paid: int
    cases_declined: int
    total_cases: int
