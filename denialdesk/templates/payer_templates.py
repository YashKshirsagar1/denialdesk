"""Payer appeal information database.

Contains real mailing addresses, fax numbers, phone trees, form names, and
timely filing deadlines for the 16 payers covering most US commercial volume.
Fuzzy normalization maps variations (e.g. "UHC", "United") to canonical keys.

Sources: CMS, payer provider manuals, and availity provider directories.
These are representative; always verify against the current payer contract.
"""

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

# ---------------------------------------------------------------------------
# 16-payer database
# ---------------------------------------------------------------------------
PAYER_APPEAL_INFO: dict[str, dict] = {
    "Medicare": {
        "appeal_address": "Novitas Solutions, Inc.\nP.O. Box 3003\nMechanicsburg, PA 17055-1803",
        "appeal_fax": "1-855-252-8782",
        "appeal_phone": "1-855-252-8782",
        "phone_tree": "Press 1 for Provider, then 4 for Redeterminations/Appeals",
        "deadline_days": 120,
        "appeal_form": "CMS-20027 (Redetermination Request)",
        "portal": "novitasphere.com",
        "notes": "Must be filed within 120 days of remittance date. Use CMS-20027 form.",
    },
    "Medicaid": {
        "appeal_address": "State Medicaid Agency Appeals Unit\n[State-Specific Address]",
        "appeal_fax": "See state Medicaid provider manual",
        "appeal_phone": "See state Medicaid provider manual",
        "phone_tree": "Contact state Medicaid Provider Relations",
        "deadline_days": 90,
        "appeal_form": "State-specific appeal form",
        "portal": "See state Medicaid portal",
        "notes": "Deadlines and addresses vary by state. Check current state provider manual.",
    },
    "Aetna": {
        "appeal_address": "Aetna\nP.O. Box 14463\nLexington, KY 40512-4463",
        "appeal_fax": "1-724-741-4953",
        "appeal_phone": "1-800-872-3862",
        "phone_tree": "Press 1 for Providers > 2 for Claims > 1 for Appeals",
        "deadline_days": 180,
        "appeal_form": "Aetna Provider Claim Appeal Form",
        "portal": "availity.com > Aetna > Claims > Appeals",
        "notes": "180-day window from denial date. Include EOB and all supporting docs.",
    },
    "UnitedHealthcare": {
        "appeal_address": "UnitedHealthcare\nP.O. Box 30432\nSalt Lake City, UT 84130",
        "appeal_fax": "1-801-938-2100",
        "appeal_phone": "1-877-842-3210",
        "phone_tree": "Press 1 for Providers > 4 for Claims > 1 for Appeals",
        "deadline_days": 60,
        "appeal_form": "UHC Provider Appeal/Dispute Form",
        "portal": "uhcprovider.com > Transactions > Claims > Appeals",
        "notes": "60 days from EOP date. UHC splits appeals (clinical) from disputes (admin).",
    },
    "Blue Cross Blue Shield": {
        "appeal_address": "BCBS Appeals\nP.O. Box 660044\nDallas, TX 75266-0044",
        "appeal_fax": "1-800-792-4186",
        "appeal_phone": "1-800-262-2583",
        "phone_tree": "Press 2 for Provider Services > 3 for Appeals",
        "deadline_days": 180,
        "appeal_form": "BCBS Provider Appeal Request Form",
        "portal": "availity.com > BCBS > Claim Status > Appeal",
        "notes": "Address varies by state plan. Submit via Availity when possible.",
    },
    "Anthem": {
        "appeal_address": "Anthem Blue Cross Blue Shield\nP.O. Box 21469\nEagan, MN 55121",
        "appeal_fax": "1-866-755-2680",
        "appeal_phone": "1-800-676-2583",
        "phone_tree": "Press 1 for Provider Services > 3 for Claim Disputes/Appeals",
        "deadline_days": 60,
        "appeal_form": "Anthem Provider Claim Reconsideration Form",
        "portal": "availity.com > Anthem > Claims > Reconsideration",
        "notes": "60 days from remittance. Reconsideration ≠ formal appeal — use reconsideration first.",
    },
    "Cigna": {
        "appeal_address": "Cigna\nP.O. Box 188004\nChattanooga, TN 37422-8004",
        "appeal_fax": "1-860-900-7995",
        "appeal_phone": "1-800-88-CIGNA (1-800-882-4462)",
        "phone_tree": "Press 2 for Provider Services > 1 for Claims Appeals",
        "deadline_days": 180,
        "appeal_form": "Cigna Provider Payment Dispute Form",
        "portal": "cignaforhcp.com > Claims > Dispute/Appeal",
        "notes": "180 days from EOP. Cigna distinguishes reconsideration (first) from formal appeal (second).",
    },
    "Humana": {
        "appeal_address": "Humana\nP.O. Box 14601\nLexington, KY 40512-4601",
        "appeal_fax": "1-800-949-2961",
        "appeal_phone": "1-800-448-6262",
        "phone_tree": "Press 1 for Provider > 2 for Claims > 3 for Appeals",
        "deadline_days": 60,
        "appeal_form": "Humana Provider Dispute/Appeal Form",
        "portal": "availity.com > Humana > Claims > Appeals",
        "notes": "60 days from EOP. Include a copy of the EOB with every appeal.",
    },
    "CVS Health": {
        "appeal_address": "CVS Health/Aetna\nP.O. Box 14463\nLexington, KY 40512-4463",
        "appeal_fax": "1-724-741-4953",
        "appeal_phone": "1-800-872-3862",
        "phone_tree": "Press 1 for Providers > 2 for Claims > 1 for Appeals",
        "deadline_days": 180,
        "appeal_form": "Aetna/CVS Provider Claim Appeal Form",
        "portal": "availity.com > Aetna",
        "notes": "CVS Health insurance products use Aetna's provider appeal process.",
    },
    "Molina Healthcare": {
        "appeal_address": "Molina Healthcare\nAttention: Provider Dispute Resolution\nP.O. Box 22307\nLong Beach, CA 90801",
        "appeal_fax": "1-562-499-0610",
        "appeal_phone": "1-888-665-4621",
        "phone_tree": "Press 2 for Provider Services > 1 for Claims",
        "deadline_days": 90,
        "appeal_form": "Molina Provider Dispute Resolution Request Form",
        "portal": "molinahealthcare.com > Provider Portal",
        "notes": "90 days from EOP. State-specific addresses may vary.",
    },
    "Centene": {
        "appeal_address": "Centene Corporation\nProvider Appeals\nP.O. Box 31260\nTampa, FL 33631-3260",
        "appeal_fax": "1-866-914-1339",
        "appeal_phone": "1-800-318-5311",
        "phone_tree": "Press 1 for Provider Services > 3 for Claims Disputes",
        "deadline_days": 90,
        "appeal_form": "Centene Provider Claim Dispute Form",
        "portal": "centene.com > Provider Resources",
        "notes": "90 days from EOP. Centene includes WellCare, Ambetter, and other subsidiaries.",
    },
    "WellCare": {
        "appeal_address": "WellCare Health Plans (Centene)\nP.O. Box 31260\nTampa, FL 33631-3260",
        "appeal_fax": "1-866-914-1339",
        "appeal_phone": "1-800-318-5311",
        "phone_tree": "Press 1 for Provider Services > 3 for Claims Disputes",
        "deadline_days": 90,
        "appeal_form": "WellCare Provider Claim Dispute Form",
        "portal": "centene.com > Provider Resources",
        "notes": "WellCare is a Centene subsidiary — same appeal process.",
    },
    "Kaiser Permanente": {
        "appeal_address": "Kaiser Foundation Health Plan, Inc.\nProvider Dispute Resolution\nP.O. Box 7004\nPasadena, CA 91110-7004",
        "appeal_fax": "1-888-398-4683",
        "appeal_phone": "1-800-390-3510",
        "phone_tree": "Press 3 for Provider Services > 2 for Claims > 1 for Disputes",
        "deadline_days": 180,
        "appeal_form": "Kaiser Permanente Provider Dispute Resolution Request",
        "portal": "providers.kaiserpermanente.org",
        "notes": "180 days. Kaiser is available only in CA, CO, DC, GA, HI, MD, OR, VA, WA.",
    },
    "Oscar Health": {
        "appeal_address": "Oscar Health\nProvider Appeals\nP.O. Box 14418\nLexington, KY 40512",
        "appeal_fax": "1-888-963-4219",
        "appeal_phone": "1-855-672-2788",
        "phone_tree": "Press 2 for Provider > 1 for Claims > 2 for Appeals",
        "deadline_days": 90,
        "appeal_form": "Oscar Provider Appeal Request Form",
        "portal": "providers.hioscar.com",
        "notes": "90 days from EOP. Oscar is ACA marketplace-focused; verify member's plan type.",
    },
    "Tricare": {
        "appeal_address": "Wisconsin Physicians Service (WPS)\nTricare Claims\nP.O. Box 8048\nMadison, WI 53708-8048",
        "appeal_fax": "1-608-221-4379",
        "appeal_phone": "1-888-647-6676",
        "phone_tree": "Press 1 for Providers > 2 for Claims > 3 for Appeals",
        "deadline_days": 90,
        "appeal_form": "DD Form 2642 (TRICARE Appeal/Redetermination Request)",
        "portal": "tricare.mil > Providers > Claims",
        "notes": "90 days from EOB date. Region determines contractor (East/West). Federal program.",
    },
    "Medicaid Managed Care": {
        "appeal_address": "Managed Care Organization\n[State-Specific Address]",
        "appeal_fax": "See MCO provider manual",
        "appeal_phone": "See MCO provider manual",
        "phone_tree": "Contact MCO Provider Relations",
        "deadline_days": 90,
        "appeal_form": "State/MCO-specific appeal form",
        "portal": "See MCO provider portal",
        "notes": "MCO and state rules vary. Confirm timely filing window with specific MCO.",
    },
}

_DEFAULT_PAYER_INFO: dict = {
    "appeal_address": "[Payer Appeals Department]\n[Address from back of insurance card or provider manual]",
    "appeal_fax": "See payer provider manual",
    "appeal_phone": "See back of insurance card",
    "phone_tree": "Ask for Provider Services / Claims Appeals",
    "deadline_days": 180,
    "appeal_form": "See payer provider manual",
    "portal": "availity.com (most payers)",
    "notes": "Verify deadline and address against current payer provider manual.",
}

# ---------------------------------------------------------------------------
# Alias normalization
# ---------------------------------------------------------------------------
_PAYER_ALIASES: dict[str, str] = {
    # Medicare variants
    "medicare": "Medicare",
    "cms": "Medicare",
    "medicare part b": "Medicare",
    "medicare part a": "Medicare",
    "novitas": "Medicare",
    "ngsmedicare": "Medicare",
    # Medicaid
    "medicaid": "Medicaid",
    "state medicaid": "Medicaid",
    # Aetna
    "aetna": "Aetna",
    "aetna health": "Aetna",
    "aetna health inc": "Aetna",
    "aetna inc": "Aetna",
    # UHC
    "unitedhealthcare": "UnitedHealthcare",
    "united healthcare": "UnitedHealthcare",
    "uhc": "UnitedHealthcare",
    "united health": "UnitedHealthcare",
    "optum": "UnitedHealthcare",
    # BCBS
    "blue cross blue shield": "Blue Cross Blue Shield",
    "bcbs": "Blue Cross Blue Shield",
    "bluecross blueshield": "Blue Cross Blue Shield",
    "blue cross": "Blue Cross Blue Shield",
    "blue shield": "Blue Cross Blue Shield",
    "bcbsca": "Blue Cross Blue Shield",
    "bcbstx": "Blue Cross Blue Shield",
    # Anthem
    "anthem": "Anthem",
    "anthem bcbs": "Anthem",
    "anthem blue cross": "Anthem",
    # Cigna
    "cigna": "Cigna",
    "cigna health": "Cigna",
    "cigna healthcare": "Cigna",
    "cigna health life insurance": "Cigna",
    # Humana
    "humana": "Humana",
    "humana inc": "Humana",
    "humana health": "Humana",
    # CVS
    "cvs health": "CVS Health",
    "cvs": "CVS Health",
    "caremark": "CVS Health",
    # Molina
    "molina": "Molina Healthcare",
    "molina health": "Molina Healthcare",
    "molina healthcare": "Molina Healthcare",
    # Centene
    "centene": "Centene",
    "centene corporation": "Centene",
    "ambetter": "Centene",
    "healthspring": "Centene",
    # WellCare
    "wellcare": "WellCare",
    "well care": "WellCare",
    # Kaiser
    "kaiser": "Kaiser Permanente",
    "kaiser permanente": "Kaiser Permanente",
    "kp": "Kaiser Permanente",
    # Oscar
    "oscar": "Oscar Health",
    "oscar health": "Oscar Health",
    # Tricare
    "tricare": "Tricare",
    "champus": "Tricare",
    "wps": "Tricare",
    # Medicaid MCO
    "medicaid managed care": "Medicaid Managed Care",
    "mco": "Medicaid Managed Care",
}

# Substring patterns (checked after alias map, ordered longest first)
_PAYER_SUBSTRINGS: list[tuple[str, str]] = sorted(
    [
        ("medicare advantage", "Medicare"),
        ("medicare", "Medicare"),
        ("medicaid managed", "Medicaid Managed Care"),
        ("medicaid", "Medicaid"),
        ("unitedhealthcare", "UnitedHealthcare"),
        ("united health", "UnitedHealthcare"),
        ("blue cross blue shield", "Blue Cross Blue Shield"),
        ("bluecross blueshield", "Blue Cross Blue Shield"),
        ("anthem blue", "Anthem"),
        ("anthem", "Anthem"),
        ("blue cross", "Blue Cross Blue Shield"),
        ("blue shield", "Blue Cross Blue Shield"),
        ("aetna", "Aetna"),
        ("cigna", "Cigna"),
        ("humana", "Humana"),
        ("kaiser", "Kaiser Permanente"),
        ("molina", "Molina Healthcare"),
        ("wellcare", "WellCare"),
        ("centene", "Centene"),
        ("ambetter", "Centene"),
        ("oscar", "Oscar Health"),
        ("tricare", "Tricare"),
        ("champus", "Tricare"),
        ("cvs", "CVS Health"),
    ],
    key=lambda x: -len(x[0]),
)


def normalize_payer_name(raw: str) -> str:
    """Map a raw payer name string to a canonical key in PAYER_APPEAL_INFO."""
    if not raw:
        return raw
    lower = raw.strip().lower()
    # Exact alias match
    if lower in _PAYER_ALIASES:
        return _PAYER_ALIASES[lower]
    # Substring match
    for pattern, canonical in _PAYER_SUBSTRINGS:
        if pattern in lower:
            return canonical
    return raw  # return original if no match


def get_payer_info(payer: str) -> dict:
    """Return payer appeal info by canonical name, normalizing the input first."""
    canonical = normalize_payer_name(payer)
    return PAYER_APPEAL_INFO.get(canonical, _DEFAULT_PAYER_INFO.copy())
