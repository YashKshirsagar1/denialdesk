from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
import uuid


@dataclass
class ClaimRecord:
    """Normalized claim data extracted from any source format."""
    patient_ref: str
    dos: date
    cpt: str
    icd10: list[str]
    billed_amt: Decimal
    allowed_amt: Decimal
    payer: str
    carc: str
    rarc: str
    denial_date: date
    claim_number: str
    source_format: str  # "csv" | "x12_835" | "pdf"
    raw: dict = field(default_factory=dict)  # original parsed data for audit


@dataclass
class IngestionResult:
    batch_id: uuid.UUID
    records: list[ClaimRecord]
    errors: list[str]  # non-fatal parse errors (skipped rows, etc.)
    source_format: str


class IngestorError(Exception):
    pass


class BaseIngestor:
    def can_handle(self, filename: str, content: bytes) -> bool:
        raise NotImplementedError

    def parse(self, content: bytes, filename: str) -> list[ClaimRecord]:
        raise NotImplementedError
