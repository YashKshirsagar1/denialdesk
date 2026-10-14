from datetime import date
from decimal import Decimal, InvalidOperation

from .base import BaseIngestor, ClaimRecord


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    if len(raw) == 8:
        try:
            return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
        except ValueError:
            return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


class X12835Ingestor(BaseIngestor):
    def can_handle(self, filename: str, content: bytes) -> bool:
        if filename.lower().endswith((".835", ".x12", ".edi")):
            return True
        return content.lstrip()[:4] == b"ISA*"

    def parse(self, content: bytes, filename: str) -> tuple[list[ClaimRecord], list[str]]:
        text = content.decode("utf-8", errors="replace")
        segments = [s.strip() for s in text.split("~") if s.strip()]

        payer_name = "unknown"
        records: list[ClaimRecord] = []
        errors: list[str] = []
        current: dict | None = None

        def flush(clm: dict) -> None:
            try:
                # 835 does not carry diagnosis codes — those live in the 837 original claim
                billed = Decimal(str(clm.get("billed", "0")))
                paid = Decimal(str(clm.get("paid", "0")))
                dos = clm.get("dos") or date.today()
                denial_date = clm.get("denial_date") or date.today()
                records.append(ClaimRecord(
                    claim_number=clm.get("claim_number", "unknown"),
                    patient_ref=clm.get("patient_ref", "unknown"),
                    dos=dos,
                    cpt=clm.get("cpt", "unknown"),
                    icd10=["unknown"],
                    billed_amt=billed,
                    allowed_amt=paid,
                    payer=payer_name,
                    carc=clm.get("carc", ""),
                    rarc="",
                    denial_date=denial_date,
                    source_format="x12_835",
                    raw=clm,
                ))
            except (InvalidOperation, Exception) as e:
                errors.append(f"Claim {clm.get('claim_number', '?')}: flush error — {e}")

        for seg in segments:
            elems = seg.split("*")
            seg_id = elems[0].upper()

            if seg_id == "NM1" and len(elems) > 3 and elems[1].upper() == "PR":
                payer_name = elems[3].strip() or payer_name

            elif seg_id == "NM1" and len(elems) > 4 and elems[1].upper() == "QC":
                if current is not None:
                    last = elems[3].strip() if len(elems) > 3 else ""
                    first = elems[4].strip() if len(elems) > 4 else ""
                    current["patient_ref"] = f"{last},{first}".strip(",")

            elif seg_id == "CLP":
                if current is not None:
                    flush(current)
                current = {
                    "claim_number": elems[1] if len(elems) > 1 else "unknown",
                    "billed": elems[3] if len(elems) > 3 else "0",
                    "paid": elems[4] if len(elems) > 4 else "0",
                    "patient_ref": elems[7] if len(elems) > 7 else "unknown",
                    "carc": "",
                    "cpt": "unknown",
                    "dos": None,
                    "denial_date": None,
                }

            elif seg_id == "CAS" and current is not None:
                group = elems[1].upper() if len(elems) > 1 else ""
                if group == "CO" and not current["carc"] and len(elems) > 2:
                    current["carc"] = elems[2].strip()

            elif seg_id == "SVC" and current is not None and len(elems) > 1:
                svc_code = elems[1]
                if ":" in svc_code:
                    current["cpt"] = svc_code.split(":")[1].strip()
                else:
                    current["cpt"] = svc_code.strip()

            elif seg_id == "DTM" and current is not None and len(elems) > 2:
                qualifier = elems[1].strip()
                parsed = _parse_date(elems[2])
                if qualifier == "232" and parsed:
                    current["dos"] = parsed
                elif qualifier == "405" and parsed:
                    current["denial_date"] = parsed

            elif seg_id == "SE":
                if current is not None:
                    flush(current)
                    current = None

        if current is not None:
            flush(current)

        return records, errors
