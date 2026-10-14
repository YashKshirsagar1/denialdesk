import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from .base import BaseIngestor, ClaimRecord, IngestorError

REQUIRED_FIELDS = {"claim_number", "patient_ref", "dos", "cpt", "icd10", "billed_amt", "payer", "carc", "denial_date"}


class CsvIngestor(BaseIngestor):
    def can_handle(self, filename: str, content: bytes) -> bool:
        if filename.lower().endswith(".csv"):
            return True
        try:
            first_line = content.split(b"\n")[0].decode("utf-8", errors="replace").lower()
            return "claim_number" in first_line or "patient_ref" in first_line
        except Exception:
            return False

    def parse(self, content: bytes, filename: str) -> tuple[list[ClaimRecord], list[str]]:
        text = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        records: list[ClaimRecord] = []
        errors: list[str] = []

        for row_num, row in enumerate(reader, start=2):
            missing = [f for f in REQUIRED_FIELDS if not row.get(f, "").strip()]
            if missing:
                errors.append(f"Row {row_num}: missing required fields {missing} — skipped")
                continue

            try:
                dos = date.fromisoformat(row["dos"].strip())
                denial_date = date.fromisoformat(row["denial_date"].strip())
            except ValueError as e:
                errors.append(f"Row {row_num}: invalid date — {e} — skipped")
                continue

            try:
                billed_amt = Decimal(row["billed_amt"].strip())
            except InvalidOperation:
                errors.append(f"Row {row_num}: invalid billed_amt '{row['billed_amt']}' — skipped")
                continue

            raw_allowed = row.get("allowed_amt", "").strip()
            allowed_amt = Decimal(raw_allowed) if raw_allowed else Decimal("0")

            raw_icd10 = row.get("icd10", "").strip()
            icd10 = [c.strip() for c in raw_icd10.split(",") if c.strip()] if raw_icd10 else ["unknown"]

            records.append(ClaimRecord(
                claim_number=row["claim_number"].strip(),
                patient_ref=row["patient_ref"].strip(),
                dos=dos,
                cpt=row["cpt"].strip(),
                icd10=icd10,
                billed_amt=billed_amt,
                allowed_amt=allowed_amt,
                payer=row["payer"].strip(),
                carc=row["carc"].strip(),
                rarc=row.get("rarc", "").strip(),
                denial_date=denial_date,
                source_format="csv",
                raw=dict(row),
            ))

        return records, errors
