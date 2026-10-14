"""Unit tests for ingestion parsers — no DB required."""
import textwrap
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from denialdesk.ingestion.base import IngestorError
from denialdesk.ingestion.csv_ingestor import CsvIngestor
from denialdesk.ingestion.x12_835_ingestor import X12835Ingestor

VALID_CSV = textwrap.dedent("""\
    claim_number,patient_ref,dos,cpt,icd10,billed_amt,allowed_amt,payer,carc,rarc,denial_date
    CLM-001,PT-SYNTH-AAAA,2026-01-15,99213,E11.9,250.00,175.00,Aetna Health Inc,16,MA01,2026-02-01
""")

TWO_ROW_CSV = textwrap.dedent("""\
    claim_number,patient_ref,dos,cpt,icd10,billed_amt,allowed_amt,payer,carc,rarc,denial_date
    CLM-001,PT-SYNTH-AAAA,2026-01-15,99213,E11.9,250.00,175.00,Aetna Health Inc,16,MA01,2026-02-01
    ,PT-SYNTH-BBBB,2026-01-16,99214,I10,300.00,200.00,Cigna Health,50,N30,2026-02-02
""")

MULTI_ICD_CSV = textwrap.dedent("""\
    claim_number,patient_ref,dos,cpt,icd10,billed_amt,allowed_amt,payer,carc,rarc,denial_date
    CLM-003,PT-SYNTH-CCCC,2026-03-01,99215,"E11.9,I10",400.00,300.00,UnitedHealthcare,11,,2026-03-15
""")

MINIMAL_835 = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *261014*1200*^*00501*000000001*0*T*:~"
    "NM1*PR*2*Humana Inc*****PI*99999~"
    "CLP*CLM-A01*4*500.00*0.00*0*MC*PT-REF-001*11*1~"
    "CAS*CO*29*500.00~"
    "DTM*232*20260101~"
    "DTM*405*20260301~"
    "SVC*HC:27447*500.00*0.00**1~"
    "CLP*CLM-A02*4*800.00*640.00*0*MC*PT-REF-002*11*1~"
    "CAS*CO*16*160.00~"
    "DTM*232*20260115~"
    "SVC*HC:93306*800.00*640.00**1~"
    "SE*9*0001~"
)


def test_csv_parse_valid():
    ingestor = CsvIngestor()
    records, errors = ingestor.parse(VALID_CSV.encode(), "test.csv")
    assert len(records) == 1
    assert len(errors) == 0
    r = records[0]
    assert r.claim_number == "CLM-001"
    assert r.patient_ref == "PT-SYNTH-AAAA"
    assert r.dos == date(2026, 1, 15)
    assert r.cpt == "99213"
    assert r.icd10 == ["E11.9"]
    assert r.billed_amt == Decimal("250.00")
    assert r.allowed_amt == Decimal("175.00")
    assert r.payer == "Aetna Health Inc"
    assert r.carc == "16"
    assert r.rarc == "MA01"
    assert r.denial_date == date(2026, 2, 1)
    assert r.source_format == "csv"


def test_csv_parse_skips_bad_rows():
    ingestor = CsvIngestor()
    records, errors = ingestor.parse(TWO_ROW_CSV.encode(), "test.csv")
    assert len(records) == 1
    assert len(errors) == 1
    assert "claim_number" in errors[0]


def test_csv_icd10_comma_separated():
    ingestor = CsvIngestor()
    records, errors = ingestor.parse(MULTI_ICD_CSV.encode(), "test.csv")
    assert len(records) == 1
    assert records[0].icd10 == ["E11.9", "I10"]


def test_csv_allowed_amt_defaults_to_zero():
    csv = textwrap.dedent("""\
        claim_number,patient_ref,dos,cpt,icd10,billed_amt,allowed_amt,payer,carc,rarc,denial_date
        CLM-004,PT-X,2026-01-01,99213,Z00.00,200.00,,Cigna Health,4,,2026-01-20
    """)
    ingestor = CsvIngestor()
    records, _ = ingestor.parse(csv.encode(), "test.csv")
    assert records[0].allowed_amt == Decimal("0")


def test_x12_835_parse():
    ingestor = X12835Ingestor()
    records, errors = ingestor.parse(MINIMAL_835.encode(), "test.835")
    assert len(records) == 2
    assert records[0].claim_number == "CLM-A01"
    assert records[0].billed_amt == Decimal("500.00")
    assert records[0].carc == "29"
    assert records[1].claim_number == "CLM-A02"
    assert records[1].billed_amt == Decimal("800.00")
    assert records[1].carc == "16"


def test_x12_835_payer_name():
    ingestor = X12835Ingestor()
    records, _ = ingestor.parse(MINIMAL_835.encode(), "test.835")
    assert all(r.payer == "Humana Inc" for r in records)


def test_x12_835_cpt_extraction():
    ingestor = X12835Ingestor()
    records, _ = ingestor.parse(MINIMAL_835.encode(), "test.835")
    assert records[0].cpt == "27447"
    assert records[1].cpt == "93306"


def test_x12_835_dos_extraction():
    ingestor = X12835Ingestor()
    records, _ = ingestor.parse(MINIMAL_835.encode(), "test.835")
    assert records[0].dos == date(2026, 1, 1)


def test_x12_835_icd10_is_unknown():
    # 835 does not carry diagnosis codes
    ingestor = X12835Ingestor()
    records, _ = ingestor.parse(MINIMAL_835.encode(), "test.835")
    assert records[0].icd10 == ["unknown"]


# ---------------------------------------------------------------------------
# New 835 field extraction tests
# ---------------------------------------------------------------------------

_835_WITH_RARC = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *261014*1200*^*00501*000000001*0*T*:~"
    "NM1*PR*2*Cigna Health*****PI*88888~"
    "CLP*CLM-RARC*4*350.00*0.00*0*MC*PT-X*11*1~"
    "CAS*CO*16*350.00~"
    "DTM*232*20260201~"
    "DTM*405*20260301~"
    "SVC*HC:99213*350.00*0.00**1~"
    "LQ*HE*M76~"
    "SE*8*0001~"
)

_835_WITH_MODIFIER = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *261014*1200*^*00501*000000001*0*T*:~"
    "NM1*PR*2*Aetna*****PI*11111~"
    "CLP*CLM-MOD*4*265.00*0.00*0*MC*PT-Y*11*1~"
    "CAS*CO*97*265.00~"
    "DTM*232*20260210~"
    "SVC*HC:99215:25*265.00*0.00**1~"
    "SE*6*0001~"
)

_835_WITH_OA_GROUP = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *261014*1200*^*00501*000000001*0*T*:~"
    "NM1*PR*2*Medicare*****PI*00000~"
    "CLP*CLM-OA*4*200.00*0.00*0*MC*PT-Z*11*1~"
    "CAS*OA*18*200.00~"
    "DTM*232*20260301~"
    "SVC*HC:93000*200.00*0.00**1~"
    "SE*6*0001~"
)

_835_WITH_DOS_QUALIFIER_472 = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *261014*1200*^*00501*000000001*0*T*:~"
    "NM1*PR*2*UnitedHealthcare*****PI*22222~"
    "CLP*CLM-472*4*400.00*0.00*0*MC*PT-W*11*1~"
    "CAS*CO*96*400.00~"
    "DTM*472*20260115~"
    "SVC*HC:71046*400.00*0.00**1~"
    "SE*6*0001~"
)

_835_WITH_TIN = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *261014*1200*^*00501*000000001*0*T*:~"
    "NM1*PR*2*Humana*****PI*55555~"
    "REF*TJ*987654321~"
    "CLP*CLM-TIN*4*125.00*0.00*0*MC*PT-V*11*1~"
    "CAS*CO*4*125.00~"
    "DTM*232*20260101~"
    "SVC*HC:80053*125.00*0.00**1~"
    "SE*7*0001~"
)


def test_x12_835_rarc_from_lq():
    ingestor = X12835Ingestor()
    records, _ = ingestor.parse(_835_WITH_RARC.encode(), "test.835")
    assert records[0].rarc == "M76"


def test_x12_835_modifier_from_svc():
    ingestor = X12835Ingestor()
    records, _ = ingestor.parse(_835_WITH_MODIFIER.encode(), "test.835")
    assert records[0].modifier == "25"
    assert records[0].cpt == "99215"


def test_x12_835_oa_group_carc():
    ingestor = X12835Ingestor()
    records, _ = ingestor.parse(_835_WITH_OA_GROUP.encode(), "test.835")
    assert records[0].carc == "18"
    assert "18" in records[0].carc_codes


def test_x12_835_dos_qualifier_472():
    ingestor = X12835Ingestor()
    records, _ = ingestor.parse(_835_WITH_DOS_QUALIFIER_472.encode(), "test.835")
    assert records[0].dos == date(2026, 1, 15)


def test_x12_835_tin_from_ref():
    ingestor = X12835Ingestor()
    records, _ = ingestor.parse(_835_WITH_TIN.encode(), "test.835")
    assert records[0].billing_provider_tin == "987654321"


def test_x12_835_carc_codes_list():
    ingestor = X12835Ingestor()
    records, _ = ingestor.parse(MINIMAL_835.encode(), "test.835")
    assert isinstance(records[0].carc_codes, list)
    assert records[0].carc in records[0].carc_codes


async def test_pipeline_detects_csv():
    from unittest.mock import AsyncMock, patch, MagicMock
    from denialdesk.ingestion.pipeline import IngestionPipeline

    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    batch_obj = MagicMock()
    batch_obj.id = 1

    pipeline = IngestionPipeline(mock_session)

    with patch.object(pipeline._ingestors[0], "parse", return_value=([], [])):
        with patch("denialdesk.ingestion.pipeline.Batch") as MockBatch:
            MockBatch.return_value = batch_obj
            result = await pipeline.ingest_file("claims.csv", VALID_CSV.encode(), 1)

    assert result.source_format == "csv"


async def test_pipeline_detects_835():
    from unittest.mock import AsyncMock, patch, MagicMock
    from denialdesk.ingestion.pipeline import IngestionPipeline

    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    batch_obj = MagicMock()
    batch_obj.id = 1

    pipeline = IngestionPipeline(mock_session)

    with patch.object(pipeline._ingestors[1], "parse", return_value=([], [])):
        with patch("denialdesk.ingestion.pipeline.Batch") as MockBatch:
            MockBatch.return_value = batch_obj
            result = await pipeline.ingest_file("claims.835", MINIMAL_835.encode(), 1)

    assert result.source_format == "835"


async def test_pipeline_unsupported_raises():
    from unittest.mock import MagicMock
    from denialdesk.ingestion.pipeline import IngestionPipeline

    mock_session = MagicMock()
    pipeline = IngestionPipeline(mock_session)

    with pytest.raises(IngestorError):
        await pipeline.ingest_file("data.xyz", b"random content", 1)
