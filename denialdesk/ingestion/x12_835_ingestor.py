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


# DTM qualifier -> date field mapping
_DOS_QUALIFIERS = {"232", "472", "150"}          # service date / service period start / assessment date
_DENIAL_QUALIFIERS = {"405", "036", "007"}        # adjudication date / remittance date / paid date


class X12835Ingestor(BaseIngestor):
    def can_handle(self, filename: str, content: bytes) -> bool:
        if filename.lower().endswith((".835", ".x12", ".edi")):
            return True
        return content.lstrip()[:4] == b"ISA*"

    def parse(self, content: bytes, filename: str) -> tuple[list[ClaimRecord], list[str]]:
        text = content.decode("utf-8", errors="replace")
        segments = [s.strip() for s in text.split("~") if s.strip()]

        payer_name = "unknown"
        file_rendering_npi = ""
        file_billing_tin = ""
        records: list[ClaimRecord] = []
        errors: list[str] = []
        current: dict | None = None

        def flush(clm: dict) -> None:
            try:
                billed = Decimal(str(clm.get("billed", "0")))
                paid = Decimal(str(clm.get("paid", "0")))
                dos = clm.get("dos") or date.today()
                denial_date = clm.get("denial_date") or date.today()
                carc_codes = clm.get("carc_codes", [])
                primary_carc = carc_codes[0] if carc_codes else clm.get("carc", "")
                records.append(ClaimRecord(
                    claim_number=clm.get("claim_number", "unknown"),
                    patient_ref=clm.get("patient_ref", "unknown"),
                    dos=dos,
                    cpt=clm.get("cpt", "unknown"),
                    icd10=["unknown"],  # 835 does not carry diagnosis codes
                    billed_amt=billed,
                    allowed_amt=paid,
                    payer=payer_name,
                    carc=primary_carc,
                    rarc=clm.get("rarc", ""),
                    denial_date=denial_date,
                    source_format="x12_835",
                    raw=clm,
                    modifier=clm.get("modifier", ""),
                    rendering_provider_npi=clm.get("rendering_npi", file_rendering_npi),
                    billing_provider_tin=clm.get("billing_tin", file_billing_tin),
                    carc_codes=carc_codes,
                ))
            except (InvalidOperation, Exception) as e:
                errors.append(f"Claim {clm.get('claim_number', '?')}: flush error — {e}")

        for seg in segments:
            elems = seg.split("*")
            seg_id = elems[0].upper()

            # Payer name (loop 1000A PR qualifier)
            if seg_id == "NM1" and len(elems) > 3 and elems[1].upper() == "PR":
                payer_name = elems[3].strip() or payer_name

            # Patient name (loop 2100 QC qualifier)
            elif seg_id == "NM1" and len(elems) > 1 and elems[1].upper() == "QC":
                if current is not None:
                    last = elems[3].strip() if len(elems) > 3 else ""
                    first = elems[4].strip() if len(elems) > 4 else ""
                    current["patient_ref"] = f"{last},{first}".strip(",")

            # Rendering provider NPI (qualifier 82)
            elif seg_id == "NM1" and len(elems) > 1 and elems[1] == "82":
                npi_val = elems[9].strip() if len(elems) > 9 else ""
                if npi_val:
                    if current is not None:
                        current["rendering_npi"] = npi_val
                    else:
                        file_rendering_npi = npi_val

            # Billing/pay-to provider (qualifier 85)
            elif seg_id == "NM1" and len(elems) > 1 and elems[1] == "85":
                npi_val = elems[9].strip() if len(elems) > 9 else ""
                if npi_val and current is not None:
                    current.setdefault("billing_npi", npi_val)

            # Billing provider TIN (REF qualifier TJ)
            elif seg_id == "REF" and len(elems) > 2 and elems[1].upper() == "TJ":
                tin = elems[2].strip()
                if current is not None:
                    current["billing_tin"] = tin
                else:
                    file_billing_tin = tin

            # Claim line — start a new claim context
            elif seg_id == "CLP":
                if current is not None:
                    flush(current)
                current = {
                    "claim_number": elems[1] if len(elems) > 1 else "unknown",
                    "billed": elems[3] if len(elems) > 3 else "0",
                    "paid": elems[4] if len(elems) > 4 else "0",
                    "patient_ref": elems[7] if len(elems) > 7 else "unknown",
                    "carc": "",
                    "carc_codes": [],
                    "rarc": "",
                    "cpt": "unknown",
                    "modifier": "",
                    "dos": None,
                    "denial_date": None,
                }

            # Claim adjustment — CO = contractual obligation, OA = other adjustment, PR = patient responsibility
            elif seg_id == "CAS" and current is not None:
                group = elems[1].upper() if len(elems) > 1 else ""
                if group in ("CO", "OA", "PR"):
                    # Each CAS segment can carry up to 6 (reason_code, amount, qty) triplets
                    i = 2
                    while i < len(elems):
                        code = elems[i].strip()
                        if code:
                            if code not in current["carc_codes"]:
                                current["carc_codes"].append(code)
                            if not current["carc"]:
                                current["carc"] = code
                        i += 3

            # Service line — CPT and modifier from composite
            elif seg_id == "SVC" and current is not None and len(elems) > 1:
                parts = elems[1].split(":")
                # HC:99213:25 → cpt=99213, modifier=25
                if len(parts) >= 2:
                    current["cpt"] = parts[1].strip()
                    if len(parts) >= 3 and parts[2].strip():
                        current["modifier"] = parts[2].strip()
                else:
                    current["cpt"] = elems[1].strip()

            # Date segments
            elif seg_id == "DTM" and current is not None and len(elems) > 2:
                qualifier = elems[1].strip()
                parsed = _parse_date(elems[2])
                if qualifier in _DOS_QUALIFIERS and parsed:
                    if current["dos"] is None:
                        current["dos"] = parsed
                elif qualifier in _DENIAL_QUALIFIERS and parsed:
                    if current["denial_date"] is None:
                        current["denial_date"] = parsed

            # RARC from LQ segment (LQ*HE*<rarc_code>)
            elif seg_id == "LQ" and current is not None and len(elems) > 2:
                if elems[1].upper() == "HE":
                    rarc = elems[2].strip()
                    if rarc and not current.get("rarc"):
                        current["rarc"] = rarc

            elif seg_id == "SE":
                if current is not None:
                    flush(current)
                    current = None

        if current is not None:
            flush(current)

        return records, errors
