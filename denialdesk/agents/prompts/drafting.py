"""Prompt builders for appeal letters, call packets, and corrected claim cover letters."""

from datetime import date


def build_appeal_system_prompt() -> str:
    return (
        "You are an expert medical billing appeals specialist with 15+ years of experience "
        "overturning insurance claim denials. Your task is to write a formal, persuasive "
        "appeal letter that a real payer will accept.\n\n"
        "Critical rules:\n"
        "- Follow the exact structure provided — do not add sections or remove them.\n"
        "- Use the payer address and form reference exactly as supplied.\n"
        "- If a field is marked [MISSING: X], include the marker verbatim. "
        "Do NOT guess or fabricate data.\n"
        "- Cite the specific CARC/RARC codes and their meaning in the denial reason section.\n"
        "- The policy argument must name the specific coverage statute, LCD, or plan provision "
        "that supports payment — do not use generic language.\n"
        "- Reference the documents being attached by their exact names.\n"
        "- Return ONLY the letter text — no JSON, no preamble, no explanation.\n"
    )


def build_appeal_user_prompt(
    practice_name: str,
    payer: str,
    payer_address: str,
    appeal_form: str,
    claim_number: str,
    patient_ref: str,
    dos: str,
    cpt: str,
    modifier: str,
    icd10: list[str],
    billed_amt: float,
    carc: str,
    carc_description: str,
    rarc: str,
    rarc_description: str,
    rendering_npi: str,
    billing_tin: str,
    root_cause: str,
    rationale: str,
    required_docs: list[str],
    appeal_deadline: str,
    playbook_strategy: str,
    today: str,
) -> str:
    icd10_str = ", ".join(icd10) if icd10 else "[MISSING: ICD-10 diagnosis code(s)]"
    docs_str = "\n".join(f"  - {d}" for d in required_docs) if required_docs else "  - [MISSING: supporting documentation]"

    cpt_display = cpt
    if modifier:
        cpt_display = f"{cpt}-{modifier}"

    npi_display = rendering_npi if rendering_npi else "[MISSING: rendering provider NPI]"
    tin_display = billing_tin if billing_tin else "[MISSING: billing provider TIN]"

    playbook_section = ""
    if playbook_strategy:
        playbook_section = (
            f"Cross-practice win strategy for this payer+CARC combination:\n"
            f"{playbook_strategy}\n\n"
        )

    return (
        f"Write an appeal letter using this exact structure:\n\n"
        f"---\n"
        f"[DATE LINE: {today}]\n\n"
        f"[PAYER ADDRESS BLOCK:]\n"
        f"{payer_address}\n\n"
        f"RE: Provider Appeal — {appeal_form}\n"
        f"    Claim/ICN: {claim_number}\n"
        f"    Patient Reference: {patient_ref}\n"
        f"    Date of Service: {dos}\n"
        f"    CPT/HCPCS: {cpt_display}\n"
        f"    ICD-10: {icd10_str}\n"
        f"    Billed Amount: ${billed_amt:.2f}\n"
        f"    Rendering Provider NPI: {npi_display}\n"
        f"    Billing Provider TIN: {tin_display}\n"
        f"    Denial Reason: CARC {carc} — {carc_description}"
        + (f" | RARC {rarc} — {rarc_description}" if rarc and rarc_description else "")
        + "\n\n"
        f"Dear {payer} Appeals Department,\n\n"
        f"[SECTION 1 — INTRODUCTION: 1-2 sentences. Practice name, claim reference, denial date, "
        f"and your intent to appeal.]\n\n"
        f"[SECTION 2 — DENIAL REASON STATEMENT: State the exact CARC/RARC codes and their plain-English "
        f"meaning as issued on the remittance.]\n\n"
        f"[SECTION 3 — POLICY ARGUMENT: This is the most important section. "
        f"Root cause: {root_cause}. "
        f"Clinical rationale: {rationale}. "
        + playbook_section
        + f"Cite the specific statute, LCD, NCB policy, CMS transmittal, or plan provision that "
        f"supports payment. If root cause is missing_prior_auth, cite the clinical necessity "
        f"and any retroactive auth precedents. If coding_error, state what was corrected and why "
        f"the corrected code is clinically appropriate. If medical_necessity, cite the specific "
        f"clinical guideline (e.g., USPSTF, AHA, ACP) supporting the procedure. "
        f"If timely_filing, cite any documented extenuating circumstances.]\n\n"
        f"[SECTION 4 — DOCUMENTATION CHECKLIST: List each attached document by name. Use this list:]\n"
        f"{docs_str}\n\n"
        f"[SECTION 5 — REQUEST: Specifically request reconsideration and payment of ${billed_amt:.2f}. "
        f"Cite the appeal deadline of {appeal_deadline}. "
        f"Request written response within the payer's required timeframe.]\n\n"
        f"Sincerely,\n"
        f"{practice_name}\n"
        f"Billing Department\n"
        f"NPI: {npi_display}\n"
        f"TIN: {tin_display}\n"
        f"---\n\n"
        f"Now write the complete letter following this structure. "
        f"Replace each [SECTION X — ...] with real content. "
        f"Keep [MISSING: X] markers exactly where data is absent."
    )


def build_call_packet_system_prompt() -> str:
    return (
        "You are a medical billing coordinator preparing a staff member for a payer phone call. "
        "Your job is to produce a concise, actionable call packet.\n\n"
        "Return ONLY valid JSON matching this schema exactly:\n"
        "{\n"
        '  "claim_summary": "<2-3 sentences on the claim>",\n'
        '  "denial_reason": "<plain English explanation of why it was denied>",\n'
        '  "the_ask": "<exactly what to request from the payer representative>",\n'
        '  "phone_tree": "<step-by-step navigation instructions>",\n'
        '  "talking_points": ["<point 1>", "<point 2>", "<point 3>"],\n'
        '  "escalation_trigger": "<when to ask for a supervisor>",\n'
        '  "reference_numbers": ["<claim number>", "<other refs>"]\n'
        "}\n"
        "No prose outside the JSON object."
    )


def build_call_packet_user_prompt(
    payer: str,
    claim_number: str,
    patient_ref: str,
    dos: str,
    cpt: str,
    billed_amt: float,
    carc: str,
    carc_description: str,
    root_cause: str,
    rationale: str,
    phone_tree: str,
) -> str:
    return (
        f"Prepare a call packet for the following denied claim:\n\n"
        f"Payer: {payer}\n"
        f"Claim Number: {claim_number}\n"
        f"Patient Reference: {patient_ref}\n"
        f"Date of Service: {dos}\n"
        f"CPT Code: {cpt}\n"
        f"Billed Amount: ${billed_amt:.2f}\n"
        f"Denial Code: CARC {carc} — {carc_description}\n"
        f"Root Cause: {root_cause}\n"
        f"Rationale: {rationale}\n"
        f"Phone Tree: {phone_tree}\n\n"
        "Generate the call packet JSON now."
    )


def build_corrected_claim_system_prompt() -> str:
    return (
        "You are a medical billing specialist writing a corrected claim cover letter. "
        "The letter should be brief (3-4 paragraphs), explain exactly what was corrected "
        "and why the correction is clinically and administratively appropriate. "
        "Use professional business letter format. "
        "Return ONLY the letter text."
    )


def build_corrected_claim_user_prompt(
    payer: str,
    claim_number: str,
    patient_ref: str,
    dos: str,
    cpt: str,
    icd10: list[str],
    billed_amt: float,
    root_cause: str,
    rationale: str,
) -> str:
    icd10_str = ", ".join(icd10) if icd10 else "Not specified"
    return (
        f"Write a corrected claim cover letter for:\n\n"
        f"Payer: {payer}\n"
        f"Original Claim Number: {claim_number}\n"
        f"Patient Reference: {patient_ref}\n"
        f"Date of Service: {dos}\n"
        f"CPT Code: {cpt}\n"
        f"ICD-10 Diagnoses: {icd10_str}\n"
        f"Billed Amount: ${billed_amt:.2f}\n"
        f"Correction Reason: {root_cause}\n"
        f"Explanation: {rationale}\n\n"
        "Write the corrected claim cover letter now."
    )
