"""RARC (Remittance Advice Remark Code) descriptions.

Used in appeal letters to provide the full human-readable reason alongside
the code. These are published by the Washington Publishing Company (WPC)
under CMS contract.
"""

RARC_DESCRIPTIONS: dict[str, str] = {
    # M-series — Medicare-specific
    "M17": "Requested information not received. The claim/service will be reconsidered upon receipt of the requested information.",
    "M51": "Missing/incomplete/invalid procedure code(s).",
    "M52": "Missing/incomplete/invalid number of services.",
    "M53": "Missing/incomplete/invalid days or units of service.",
    "M62": "Missing/incomplete/invalid treatment authorization code.",
    "M76": "Missing/incomplete/invalid diagnosis or condition.",
    "M77": "Missing/incomplete/invalid place of service.",
    "M79": "Missing/incomplete/invalid charge.",
    "M86": "Service denied because payment already made for same/similar procedure within set time frame.",
    "M117": "Not covered unless submitted via your carrier.",
    "MA04": "Secondary payment cannot be considered without the identity of or payment information from the primary payer.",
    "MA18": "Claim/information submitted to the incorrect payer/contractor. Please resubmit to the correct payer/contractor.",
    "MA120": "Missing/incomplete/invalid CLIA certification number.",
    "MA125": "Per CFR 424.32, direct payment may only be made when the provider has not yet received payment.",
    "MA130": "Your claim contains incomplete and/or invalid information, and no appeal rights are afforded because the claim is unprocessable.",
    # N-series — non-Medicare
    "N1": "You may appeal this decision in accordance with your contract.",
    "N2": "This allowance has been made in accordance with the most appropriate course of treatment provision of the plan.",
    "N4": "Missing/incomplete/invalid prior authorization number.",
    "N10": "Payment based on the findings of a review organization/professional consult/manual adjudication.",
    "N19": "Procedure code incidental to primary procedure.",
    "N29": "Missing documentation/additional information has been requested from the provider. Please resubmit the claim when you receive this information.",
    "N30": "Patient not eligible for the date(s) of service.",
    "N31": "Missing/incomplete/invalid service(s) date(s).",
    "N56": "Procedure code billed is not correct/valid for the services billed or date of service billed.",
    "N95": "This provider type/specialty may not bill this service.",
    "N107": "Claim/service denied. The diagnosis is inconsistent with the patient's age.",
    "N115": "This decision was based on a National Coverage Determination (NCD).",
    "N130": "Consult plan benefit documents/guidelines for information about restrictions for this service.",
    "N234": "This procedure is not payable unless appropriate non-payable reporting codes and/or appropriate service codes are submitted.",
    "N265": "Missing/incomplete/invalid ordering provider name.",
    "N286": "Missing/incomplete/invalid referring provider primary identifier.",
    "N362": "The number of Days or Units of Service exceeds our acceptable maximum.",
    "N428": "Not covered by this payer/contractor. You must send the claim to the correct payer/contractor.",
    "N519": "Invalid combination of HCPCS modifiers.",
    "N522": "Duplicate of a claim processed, or to be processed, as a crossover claim.",
    "N542": "Missing/incomplete/invalid Ordering Provider Identifier.",
    "N582": "Rendering provider must be affiliated with the billed group practice.",
    "N657": "This should be billed with the appropriate code for these services.",
    "N779": "Missing/incomplete/invalid HCPCS.",
    "N805": "Claim requires prior authorization. Submit a prior authorization request.",
}


def get_rarc_description(rarc_code: str) -> str:
    """Return the human-readable description for a RARC code, or a generic fallback."""
    if not rarc_code:
        return ""
    return RARC_DESCRIPTIONS.get(rarc_code.strip(), f"Remark code {rarc_code} — see payer remittance.")
