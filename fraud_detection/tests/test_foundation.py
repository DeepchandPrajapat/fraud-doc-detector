"""Foundation tests. No real documents needed: OCR output is simulated as text lines,
and the end-to-end test renders a synthetic image and uses Tesseract."""
import zlib

import cv2
import numpy as np
import pytest

from fdd.extraction.fields.common import parse_date
from fdd.extraction.fields.education import extract_degree, extract_marksheet
from fdd.extraction.fields.identity import extract_aadhaar, extract_pan
from fdd.extraction.ocr import tokens_to_lines
from fdd.extraction.qr import decode_qr
from fdd.fusion.fuse import score_signals
from fdd.intake.classifier import classify
from fdd.intake.quality import assess_quality
from fdd.schemas import DocType, OCRToken, Severity, Signal, Verdict

AADHAAR_LINES = [
    "Government of India", "Rahul Kumar", "DOB: 12/05/1998", "MALE",
    "2345 6789 0123", "VID : 9134 5678 9012 3456", "Mera Aadhaar, Meri Pehchan",
]
PAN_NEW = [
    "INCOME TAX DEPARTMENT", "GOVT. OF INDIA", "Permanent Account Number Card",
    "ABCPK1234F", "Name", "RAHUL KUMAR", "Father's Name", "SURESH KUMAR",
    "Date of Birth", "12/05/1998", "Signature",
]
PAN_OLD = [
    "INCOME TAX DEPARTMENT", "GOVT. OF INDIA", "RAHUL KUMAR", "SURESH KUMAR",
    "12/05/1998", "Permanent Account Number", "ABCPK1234F", "Signature",
]
DEGREE_LINES = [
    "Anna University", "Chennai",
    "This is to certify that Rahul Kumar has been admitted to the Degree of",
    "Bachelor of Engineering in Computer Science and Engineering",
    "having passed the examination held in May 2020",
    "in First Class with Distinction", "Certificate No: AU2020123456",
]
MARKSHEET_12_LINES = [
    "Central Board of Secondary Education", "Senior School Certificate Examination 2016",
    "Marks Statement", "Roll No: 9123456", "Candidate's Name: RAHUL KUMAR",
    "Mother's Name: SUNITA DEVI", "Father's Name: SURESH KUMAR",
    "Code Subject Marks Max Grade",
    "301 English Core 85 100 A2", "041 Mathematics 92 100 A1",
    "042 Physics 78 100 B1", "043 Chemistry 80 100 B1", "083 Computer Science 95 100 A1",
    "Total 430 500", "Result: PASS",
]


# ---------------------------------------------------------------- classifier

@pytest.mark.parametrize("lines,expected", [
    (AADHAAR_LINES, DocType.AADHAAR),
    (PAN_NEW, DocType.PAN),
    (PAN_OLD, DocType.PAN),
    (DEGREE_LINES, DocType.DEGREE),
    (MARKSHEET_12_LINES, DocType.MARKSHEET_12),
    (["Secondary School Examination (Class X) 2014", "Statement of Marks", "Date of Birth 12-05-1998"],
     DocType.MARKSHEET_10),
    (["XYZ University", "Grade Card", "Semester V", "SGPA 8.2 CGPA 8.0", "Credits 22"],
     DocType.MARKSHEET_SEM),
    (["hello world", "random receipt 123"], DocType.UNKNOWN),
])
def test_classifier(lines, expected):
    dtype, conf, _ = classify("\n".join(lines))
    assert dtype == expected
    if expected != DocType.UNKNOWN:
        assert conf > 0


# ---------------------------------------------------------------- fields

def test_aadhaar_fields_ignore_vid():
    f = extract_aadhaar(AADHAAR_LINES)
    assert f.id_number == "234567890123"
    assert f.name == "Rahul Kumar"
    assert f.dob == "1998-05-12"
    assert f.gender == "MALE"


@pytest.mark.parametrize("lines", [PAN_NEW, PAN_OLD])
def test_pan_fields_both_layouts(lines):
    f = extract_pan(lines)
    assert f.id_number == "ABCPK1234F"
    assert f.name == "Rahul Kumar"
    assert f.father_name == "Suresh Kumar"
    assert f.dob == "1998-05-12"


def test_degree_fields():
    f = extract_degree(DEGREE_LINES)
    assert f.institution == "Anna University"
    assert f.degree == "Bachelor of Engineering"
    assert f.branch.startswith("Computer Science")
    assert f.year == 2020
    assert f.division == "First Class With Distinction"
    assert f.name == "Rahul Kumar"
    assert f.certificate_number == "AU2020123456"


def test_marksheet_fields_and_table():
    f = extract_marksheet(MARKSHEET_12_LINES)
    assert f.institution == "Central Board of Secondary Education"
    assert f.name == "Rahul Kumar"
    assert f.father_name == "Suresh Kumar"
    assert f.mother_name == "Sunita Devi"
    assert f.roll_number == "9123456"
    assert f.year == 2016
    assert len(f.subjects) == 5
    assert sum(s.marks for s in f.subjects) == 430
    assert all(s.max_marks == 100 for s in f.subjects)
    assert f.total_marks == 430 and f.max_total == 500
    assert f.result == "PASS"


@pytest.mark.parametrize("s,iso", [
    ("12/05/1998", "1998-05-12"), ("12-05-1998", "1998-05-12"), ("12.05.1998", "1998-05-12"),
    ("12 May 1998", "1998-05-12"), ("1st January 2001", "2001-01-01"),
    ("31/02/1998", None), ("no date", None),
])
def test_parse_date(s, iso):
    assert parse_date(s) == iso


def test_tokens_to_lines_orders_reading():
    toks = [OCRToken(text="Kumar", bbox=(120, 10, 200, 30), conf=1),
            OCRToken(text="Rahul", bbox=(10, 12, 100, 31), conf=1),
            OCRToken(text="DOB", bbox=(10, 60, 60, 80), conf=1)]
    assert tokens_to_lines(toks) == ["Rahul Kumar", "DOB"]


# ---------------------------------------------------------------- QR

def _make_secure_qr(fields: list[str]) -> str:
    body = b"\xff".join(f.encode("iso-8859-1") for f in fields) + b"\xff" + b"PHOTO"
    blob = body + bytes(range(256))           # fake 256-byte signature
    gz = zlib.compressobj(wbits=16 + zlib.MAX_WBITS)
    data = gz.compress(blob) + gz.flush()
    return str(int.from_bytes(data, "big"))


def test_aadhaar_secure_qr_v2_decode():
    fields = ["V2", "3", "012320190101123456789", "Rahul Kumar", "12-05-1998", "M",
              "S/O Suresh Kumar", "Chennai", "", "12", "", "600001", "Chennai GPO",
              "Tamil Nadu", "Main Road", "Chennai", "Chennai", "4321"]
    q = decode_qr(_make_secure_qr(fields))
    assert q.kind == "aadhaar_secure"
    assert q.payload["name"] == "Rahul Kumar"
    assert q.payload["dob"] == "1998-05-12"
    assert q.payload["aadhaar_last4"] == "0123"
    assert q.payload["last_4_mobile"] == "4321"
    assert q.signature == bytes(range(256))


def test_corrupt_numeric_qr_flagged_invalid():
    q = decode_qr("9" * 800)
    assert q.kind == "aadhaar_invalid"


def test_aadhaar_xml_qr():
    raw = ('<?xml version="1.0" encoding="UTF-8"?><PrintLetterBarcodeData uid="234567890123" '
           'name="Rahul Kumar" gender="M" yob="1998" co="S/O Suresh" pc="600001" state="Tamil Nadu"/>')
    q = decode_qr(raw)
    assert q.kind == "aadhaar_xml" and q.payload["uid"] == "234567890123"


# ---------------------------------------------------------------- quality & fusion

def test_quality_gate_flags_blur_and_low_res():
    rng = np.random.default_rng(0)
    sharp = (rng.random((1200, 1600, 3)) * 255).astype(np.uint8)
    assert assess_quality(sharp)["ok"]
    blurry = cv2.GaussianBlur(sharp, (51, 51), 20)
    assert any("blurry" in i for i in assess_quality(blurry)["issues"])
    tiny = cv2.resize(sharp, (300, 200))
    assert any("low resolution" in i for i in assess_quality(tiny)["issues"])


def _text_page(bg: int) -> np.ndarray:
    img = np.full((1754, 1240, 3), bg, np.uint8)
    for i in range(30):
        cv2.putText(img, "Central Board of Secondary Education 2016", (60, 80 + i * 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    return img


def test_quality_clean_white_document_passes():
    # clean scans / digital PDFs are mostly pure white: must not count as glare
    q = assess_quality(_text_page(255))
    assert q["ok"], q["issues"]


def test_quality_photo_with_flash_glare_fails():
    img = _text_page(200)                                   # off-white paper (photo)
    cv2.circle(img, (620, 800), 350, (255, 255, 255), -1)   # flash reflection over text
    q = assess_quality(img)
    assert any("glare" in i for i in q["issues"])


def test_bad_quality_document_blocked_before_ocr(tmp_path):
    from fdd.intake.file_check import IntakeError
    from fdd.pipeline import ingest
    p = tmp_path / "blurry.png"
    cv2.imwrite(str(p), cv2.GaussianBlur(_text_page(255), (61, 61), 25))
    with pytest.raises(IntakeError, match="re-upload needed"):
        ingest(p)


def test_fusion_verdicts():
    def sig(sev):
        return Signal(fraud_id="FX", severity=sev, code="X", reason="x")
    assert score_signals([])[1] == Verdict.PASS
    assert score_signals([sig(Severity.LOW)])[1] == Verdict.PASS
    assert score_signals([sig(Severity.MEDIUM)])[1] == Verdict.REVIEW
    assert score_signals([sig(Severity.CRITICAL)])[1] == Verdict.REJECT
    # corroboration: several mediums escalate
    assert score_signals([sig(Severity.HIGH)] * 3)[1] == Verdict.REJECT


# ---------------------------------------------------------------- end-to-end (Tesseract)

def test_ingest_end_to_end_synthetic_pan(tmp_path):
    from config.settings import settings
    from fdd.pipeline import ingest
    settings.ocr_backend = "tesseract"

    img = np.full((900, 1400, 3), 255, np.uint8)
    for i, line in enumerate(PAN_NEW):
        cv2.putText(img, line, (60, 70 + i * 75), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 3)
    p = tmp_path / "pan.png"
    cv2.imwrite(str(p), img)

    doc = ingest(p)
    assert doc.doc_type == DocType.PAN
    assert doc.fields.id_number == "ABCPK1234F"
    assert doc.fields.dob == "1998-05-12"
    assert doc.metadata["kind"] == "image"
