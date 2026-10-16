import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from denialdesk.llm.base import LLMProvider
from denialdesk.models.case import AuditEvent, Batch, Case, CaseState, Practice
from denialdesk.templates.payer_templates import get_payer_info
from .base import ClaimRecord, IngestionResult, IngestorError
from .csv_ingestor import CsvIngestor
from .x12_835_ingestor import X12835Ingestor
from .pdf_ingestor import PdfIngestor


class IngestionPipeline:
    def __init__(self, session: AsyncSession, llm_provider: LLMProvider | None = None):
        self._session = session
        self._ingestors = [
            CsvIngestor(),
            X12835Ingestor(),
            PdfIngestor(llm_provider=llm_provider),
        ]

    async def ingest_file(
        self,
        filename: str,
        content: bytes,
        practice_id: int,
    ) -> IngestionResult:
        ingestor = next(
            (i for i in self._ingestors if i.can_handle(filename, content)),
            None,
        )
        if ingestor is None:
            raise IngestorError("Unsupported file format")

        records, errors = ingestor.parse(content, filename)
        source_format = records[0].source_format if records else filename.rsplit(".", 1)[-1]

        batch = Batch(
            practice_id=practice_id,
            tenant_id=practice_id,
            uploaded_at=datetime.now(timezone.utc),
            source_files=filename,
        )
        self._session.add(batch)
        await self._session.flush()

        for record in records:
            denial_dt = datetime(
                record.denial_date.year, record.denial_date.month, record.denial_date.day, tzinfo=timezone.utc
            )
            # Appeal window comes from the payer's rules; deadlines are first-class data.
            appeal_days = int(get_payer_info(record.payer).get("deadline_days", 180))
            case = Case(
                batch_id=batch.id,
                tenant_id=practice_id,
                payer=record.payer,
                patient_ref=record.patient_ref,
                dos=datetime(record.dos.year, record.dos.month, record.dos.day, tzinfo=timezone.utc),
                cpt_hcpcs=record.cpt,
                icd10=",".join(record.icd10),
                billed_amt=float(record.billed_amt),
                allowed_amt=float(record.allowed_amt),
                carc=record.carc,
                rarc=record.rarc,
                denial_date=denial_dt,
                filing_deadline=denial_dt + timedelta(days=appeal_days),
                claim_number=record.claim_number or None,
                modifier=record.modifier or None,
                rendering_provider_npi=record.rendering_provider_npi or None,
                billing_provider_tin=record.billing_provider_tin or None,
                clinical_notes=record.clinical_notes or None,
                carc_codes=json.dumps(record.carc_codes) if record.carc_codes else None,
                state=CaseState.ingested,
            )
            self._session.add(case)
            await self._session.flush()

            event = AuditEvent(
                case_id=case.id,
                tenant_id=practice_id,
                actor="ingestion_pipeline",
                action=f"ingested from {source_format}",
                timestamp=datetime.now(timezone.utc),
            )
            self._session.add(event)

        await self._session.commit()

        batch_uuid = uuid.UUID(int=batch.id)

        return IngestionResult(
            batch_id=batch_uuid,
            records=records,
            errors=errors,
            source_format=source_format,
        )
