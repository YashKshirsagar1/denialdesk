from typing import Literal

from pydantic import BaseModel


class ReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "edit"]
    edits: str | None = None
    reviewer: str = "human"
    notes: str | None = None


class ReviewResponse(BaseModel):
    case_id: int
    new_state: str
    draft_id: int | None
    message: str
