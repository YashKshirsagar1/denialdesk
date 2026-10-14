import io
import json
import re
from datetime import date
from decimal import Decimal

from .base import BaseIngestor, ClaimRecord, IngestorError

try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

_RE_CLAIM = re.compile(r"(?:claim|claim\s*#|claim\s*no\.?)\s*:?\s*([A-Z0-9\-]+)", re.IGNORECASE)
_RE_CPT = re.compile(r"\b(\d{5})\b")
_RE_CARC = re.compile(r"(?:reason\s*code|adjustment\s*code|carc)\s*:?\s*(\d+)", re.IGNORECASE)
_RE_BILLED = re.compile(r"(?:billed|charged)\s*:?\s*\$?([\d,]+\.?\d*)", re.IGNORECASE)
_RE_PAYER = re.compile(
    r"(?:payer|insurance|plan)\s*:?\s*([A-Za-z\s]+(?:Inc|LLC|Health|Blue|Aetna|United|Cigna|Humana)?)",
    re.IGNORECASE,
)

_LLM_SYSTEM = (
    "You are a medical billing data extractor. Extract structured claim denial data from the provided EOB/remittance text.\n"
    'Return ONLY valid JSON matching this schema: {"claim_number": str, "patient_ref": str, "dos": "YYYY-MM-DD", '
    '"cpt": str, "icd10": [str], "billed_amt": float, "allowed_amt": float, "payer": str, '
    '"carc": str, "rarc": str, "denial_date": "YYYY-MM-DD"}\n'
    'Use "unknown" for any field you cannot determine. Never guess PHI.'
)


class PdfIngestor(BaseIngestor):
    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    def can_handle(self, filename: str, content: bytes) -> bool:
        if filename.lower().endswith(".pdf"):
            return True
        return content[:4] == b"%PDF"

    def parse(self, content: bytes, filename: str) -> tuple[list[ClaimRecord], list[str]]:
        if not _HAS_PDFPLUMBER:
            raise IngestorError("pdfplumber is required for PDF ingestion. Install it with: pip install pdfplumber")

        text = self._extract_text(content)
        records, errors = self._structured_parse(text)

        if not records:
            if self._llm is None:
                raise IngestorError(
                    "Structured PDF extraction found no records and no LLM provider was supplied."
                )
            records, llm_errors = self._llm_parse(text)
            errors.extend(llm_errors)

        return records, errors

    def _extract_text(self, content: bytes) -> str:
        try:
            parts = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    parts.append(page_text)
            return "\n".join(parts)
        except Exception as exc:
            raise IngestorError(f"PDF extraction failed: {exc}") from exc

    def _structured_parse(self, text: str) -> tuple[list[ClaimRecord], list[str]]:
        errors: list[str] = []

        claim_match = _RE_CLAIM.search(text)
        cpt_match = _RE_CPT.search(text)
        carc_match = _RE_CARC.search(text)
        billed_match = _RE_BILLED.search(text)
        payer_match = _RE_PAYER.search(text)

        if not any([claim_match, cpt_match, carc_match, billed_match]):
            return [], ["PDF structured pass: no recognizable claim patterns found"]

        claim_number = claim_match.group(1) if claim_match else "unknown"
        cpt = cpt_match.group(1) if cpt_match else "unknown"
        carc = carc_match.group(1) if carc_match else ""
        payer = payer_match.group(1).strip() if payer_match else "unknown"

        billed_amt = Decimal("0")
        if billed_match:
            try:
                billed_amt = Decimal(billed_match.group(1).replace(",", ""))
            except Exception:
                errors.append("Could not parse billed amount from PDF")

        record = ClaimRecord(
            claim_number=claim_number,
            patient_ref="unknown",
            dos=date.today(),
            cpt=cpt,
            icd10=["unknown"],
            billed_amt=billed_amt,
            allowed_amt=Decimal("0"),
            payer=payer,
            carc=carc,
            rarc="",
            denial_date=date.today(),
            source_format="pdf",
            raw={"extracted_text_length": len(text)},
        )
        return [record], errors

    def _llm_parse(self, text: str) -> tuple[list[ClaimRecord], list[str]]:
        import asyncio
        from denialdesk.llm.base import LLMMessage

        async def _call():
            return await self._llm.complete_json(
                messages=[LLMMessage(role="user", content=f"Extract denial claim data from this text:\n\n{text[:4000]}")],
                system=_LLM_SYSTEM,
            )

        try:
            data = asyncio.get_event_loop().run_until_complete(_call())
        except Exception as e:
            return [], [f"LLM extraction failed: {e}"]

        try:
            record = ClaimRecord(
                claim_number=str(data.get("claim_number", "unknown")),
                patient_ref=str(data.get("patient_ref", "unknown")),
                dos=date.fromisoformat(data.get("dos", "1970-01-01")),
                cpt=str(data.get("cpt", "unknown")),
                icd10=data.get("icd10", ["unknown"]),
                billed_amt=Decimal(str(data.get("billed_amt", 0))),
                allowed_amt=Decimal(str(data.get("allowed_amt", 0))),
                payer=str(data.get("payer", "unknown")),
                carc=str(data.get("carc", "")),
                rarc=str(data.get("rarc", "")),
                denial_date=date.fromisoformat(data.get("denial_date", "1970-01-01")),
                source_format="pdf",
                raw=data,
            )
            return [record], []
        except Exception as e:
            return [], [f"LLM response parsing failed: {e}"]
