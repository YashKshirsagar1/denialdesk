from enum import Enum

from denialdesk.agents.diagnosis_agent import RootCause


class DraftType(str, Enum):
    appeal = "appeal"
    corrected_claim = "corrected_claim"
    call_packet = "call_packet"


REQUIRED_DOCS_BY_ROOT_CAUSE: dict[RootCause, list[str]] = {
    RootCause.missing_prior_auth: ["prior_auth_request", "clinical_notes", "physician_letter"],
    RootCause.coding_error:       ["corrected_claim_form", "coding_rationale"],
    RootCause.eligibility:        ["eligibility_verification", "insurance_card_copy"],
    RootCause.medical_necessity:  ["clinical_notes", "physician_letter", "clinical_guidelines"],
    RootCause.timely_filing:      ["proof_of_timely_filing", "system_logs", "certified_mail_receipt"],
    RootCause.bundling_ncci:      ["modifier_justification", "operative_report"],
    RootCause.duplicate:          ["original_claim_copy", "remittance_advice"],
    RootCause.missing_info:       ["completed_claim_form", "supporting_documentation"],
    RootCause.not_covered:        ["plan_documents", "medical_necessity_letter"],
    RootCause.other:              ["supporting_documentation"],
}

PAYER_APPEAL_INFO: dict[str, dict] = {
    "BlueCross BlueShield of California": {
        "appeal_address": "P.O. Box 272540, Chico, CA 95927",
        "appeal_fax": "1-800-xxx-xxxx",
        "appeal_phone": "1-800-676-2583",
        "phone_tree": "Press 2 for Provider Services, then 3 for Appeals",
        "deadline_days": 180,
        "portal": "availity.com",
    },
    "Aetna Health Inc": {
        "appeal_address": "P.O. Box 14463, Lexington, KY 40512",
        "appeal_fax": "1-724-741-4953",
        "appeal_phone": "1-800-872-3862",
        "phone_tree": "Press 1 for Providers, then 2 for Claims, then 1 for Appeals",
        "deadline_days": 180,
        "portal": "availity.com",
    },
    "UnitedHealthcare": {
        "appeal_address": "P.O. Box 30432, Salt Lake City, UT 84130",
        "appeal_fax": "1-801-938-2100",
        "appeal_phone": "1-877-842-3210",
        "phone_tree": "Press 1 for Providers, then 4 for Appeals",
        "deadline_days": 90,
        "portal": "uhcprovider.com",
    },
    "Cigna Health": {
        "appeal_address": "P.O. Box 188004, Chattanooga, TN 37422",
        "appeal_fax": "1-860-900-7995",
        "appeal_phone": "1-800-88-Cigna",
        "phone_tree": "Press 2 for Provider Services, then 1 for Claims Appeals",
        "deadline_days": 180,
        "portal": "cignaforhcp.com",
    },
    "Humana Inc": {
        "appeal_address": "P.O. Box 14601, Lexington, KY 40512",
        "appeal_fax": "1-800-949-2961",
        "appeal_phone": "1-800-448-6262",
        "phone_tree": "Press 1 for Provider, then 2 for Appeals",
        "deadline_days": 180,
        "portal": "availity.com",
    },
}

_DEFAULT_PAYER_INFO: dict = {
    "appeal_address": "Appeals Department, [Payer Address]",
    "appeal_fax": "Unknown",
    "appeal_phone": "See back of insurance card",
    "phone_tree": "Ask for Provider Services / Claims Appeals",
    "deadline_days": 180,
    "portal": "Unknown",
}


def get_payer_info(payer: str) -> dict:
    return PAYER_APPEAL_INFO.get(payer, _DEFAULT_PAYER_INFO.copy())
