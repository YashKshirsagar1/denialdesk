def build_appeal_system_prompt() -> str:
    return (
        "You are an expert medical billing appeals specialist with 15+ years of experience "
        "overturning insurance claim denials. Your task is to write a professional, persuasive "
        "appeal letter on behalf of a medical practice.\n\n"
        "Guidelines:\n"
        "- Use proper business letter format\n"
        "- Cite specific clinical, regulatory, or contractual basis for the appeal\n"
        "- Be factual, professional, and persuasive\n"
        "- Reference relevant coverage policies, clinical guidelines, or payer contracts where applicable\n"
        "- State clearly what you are requesting (reconsideration and payment)\n"
        "- Return ONLY the letter text — no JSON, no preamble, no explanation\n"
    )


def build_appeal_user_prompt(
    practice_name: str,
    payer: str,
    claim_number: str,
    patient_ref: str,
    dos: str,
    cpt: str,
    icd10: list[str],
    billed_amt: float,
    carc: str,
    carc_description: str,
    root_cause: str,
    rationale: str,
    required_docs: list[str],
    payer_address: str,
    appeal_deadline: str,
) -> str:
    icd10_str = ", ".join(icd10) if icd10 else "Not specified"
    docs_str = "\n".join(f"  - {d}" for d in required_docs)
    return (
        f"Write an appeal letter for the following denied claim:\n\n"
        f"Practice: {practice_name}\n"
        f"Payer: {payer}\n"
        f"Payer Address: {payer_address}\n"
        f"Claim Number: {claim_number}\n"
        f"Patient Reference: {patient_ref}\n"
        f"Date of Service: {dos}\n"
        f"CPT Code: {cpt}\n"
        f"ICD-10 Diagnoses: {icd10_str}\n"
        f"Billed Amount: ${billed_amt:.2f}\n"
        f"Denial Reason (CARC {carc}): {carc_description}\n"
        f"Root Cause Classification: {root_cause}\n"
        f"Clinical Rationale: {rationale}\n"
        f"Appeal Deadline: {appeal_deadline}\n\n"
        f"Supporting documents being attached:\n{docs_str}\n\n"
        "Write the complete appeal letter now."
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
        f"CARC Code: {carc}\n"
        f"Root Cause: {root_cause}\n"
        f"Rationale: {rationale}\n"
        f"Known Phone Tree: {phone_tree}\n\n"
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
