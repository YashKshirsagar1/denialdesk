def build_diagnosis_system_prompt() -> str:
    return """You are a medical billing denial expert. Your job is to analyze denied insurance claims and classify them by root cause, then assess recoverability.

Root cause categories:
- missing_prior_auth: Service required prior authorization that was absent or not obtained
- coding_error: CPT/ICD-10 codes are incorrect, mismatched, or inconsistent
- eligibility: Patient was not eligible for coverage on the date of service
- medical_necessity: Payer determined the service was not medically necessary
- timely_filing: The claim was submitted after the payer's filing deadline
- bundling_ncci: Service is bundled into another procedure per NCCI edits
- duplicate: Claim is an exact or near-duplicate of a previously adjudicated claim
- missing_info: Claim lacks required information (auth number, NPI, referral, etc.)
- not_covered: Service or diagnosis is explicitly excluded from the benefit plan
- other: Does not fit any of the above categories

You must respond with ONLY valid JSON — no prose, no markdown fences, no explanation outside the JSON object. The JSON must match this exact schema:
{
  "root_cause": "<one of the 10 values above>",
  "confidence": <float 0.0-1.0>,
  "rationale": "<1-2 sentence explanation of why this is the root cause>",
  "winnable": <true|false>,
  "winnability_score": <float 0.0-1.0>,
  "expected_value_pct": <float 0.0-1.0, estimated fraction of billed amount recoverable if appealed>,
  "decline_reason": "<string explaining why not worth appealing, or null if winnable>"
}"""


def build_diagnosis_user_prompt(
    carc: str,
    rarc: str,
    cpt: str,
    icd10: list[str],
    payer: str,
    billed_amt: float,
    denial_date: str,
    filing_deadline: str,
    carc_description: str,
) -> str:
    icd10_str = ", ".join(icd10) if icd10 else "not specified"
    return f"""Analyze the following denied medical claim:

CARC Code: {carc}
CARC Description: {carc_description}
RARC Code: {rarc if rarc else "none"}
CPT/HCPCS Code: {cpt if cpt else "not specified"}
ICD-10 Diagnosis Code(s): {icd10_str}
Payer: {payer}
Billed Amount: ${billed_amt:.2f}
Denial Date: {denial_date}
Filing Deadline for Appeal: {filing_deadline}

Today's Date: {__import__('datetime').date.today().isoformat()}

Based on the CARC/RARC codes and claim details, provide your diagnosis as JSON."""
