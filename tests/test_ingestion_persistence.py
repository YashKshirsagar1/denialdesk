"""Uploaded claims keep their claim number and get a payer-based appeal deadline."""
from sqlalchemy import select

from denialdesk.models.case import Case, Practice

CSV = b"""claim_number,patient_ref,dos,cpt,icd10,billed_amt,allowed_amt,payer,carc,rarc,denial_date
CLM-777,PT-1,2026-06-01,99213,I10,500.00,0.00,Aetna Health Inc,16,MA01,2026-07-01
"""


async def test_upload_persists_claim_number_and_deadline(api_client, db_session):
    p = Practice(name="P", specialty="FM", onboarding_status="active")
    db_session.add(p)
    await db_session.commit()
    r = await api_client.post("/api/upload", data={"practice_id": str(p.id)}, files={"file": ("c.csv", CSV, "text/csv")})
    assert r.status_code == 201
    case = (await db_session.execute(select(Case))).scalar_one()
    assert case.claim_number == "CLM-777"
    assert case.filing_deadline is not None
    assert case.filing_deadline > case.denial_date


async def test_ops_upload_requires_practice_id(api_client):
    r = await api_client.post("/api/upload", files={"file": ("c.csv", CSV, "text/csv")})
    assert r.status_code == 422
