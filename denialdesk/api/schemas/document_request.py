from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentRequestOut(BaseModel):
    id: int
    case_id: int
    tenant_id: Optional[int]
    requested_by: str
    document_type: str
    description: str
    status: str
    created_at: datetime
    fulfilled_at: Optional[datetime]
    file_path: Optional[str]

    model_config = {"from_attributes": True}


class CreateDocumentRequestBody(BaseModel):
    document_type: str
    description: str
    requested_by: str = "diagnosis_agent"
