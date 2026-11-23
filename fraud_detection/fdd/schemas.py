"""Core data contracts shared by every stage and fraud module."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class DocType(str, Enum):
    AADHAAR = "AADHAAR"
    PAN = "PAN"
    DEGREE = "DEGREE"
    MARKSHEET_10 = "MARKSHEET_10"
    MARKSHEET_12 = "MARKSHEET_12"
    MARKSHEET_SEM = "MARKSHEET_SEM"
    SELFIE = "SELFIE"
    UNKNOWN = "UNKNOWN"

    @property
    def is_identity(self) -> bool:
        return self in (DocType.AADHAAR, DocType.PAN)

    @property
    def is_education(self) -> bool:
        return self in (DocType.DEGREE, DocType.MARKSHEET_10,
                        DocType.MARKSHEET_12, DocType.MARKSHEET_SEM)


REQUIRED_DOCS = {DocType.AADHAAR, DocType.PAN, DocType.DEGREE,
                 DocType.MARKSHEET_10, DocType.MARKSHEET_12}


class Severity(str, Enum):
    POSITIVE = "positive"   # evidence of genuineness
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"   # hard-rule level


class Verdict(str, Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    REJECT = "REJECT"


class ModuleStatus(str, Enum):
    CHECKED = "CHECKED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


# ---------------------------------------------------------------- extraction

class OCRToken(BaseModel):
    text: str
    bbox: tuple[int, int, int, int]   # x1, y1, x2, y2 in page pixels
    conf: float
    page: int = 0


class SubjectMark(BaseModel):
    subject: str
    code: Optional[str] = None
    marks: Optional[float] = None
    max_marks: Optional[float] = None
    grade: Optional[str] = None


class ExtractedFields(BaseModel):
    """Union of fields across V1 documents; unused ones stay None."""
    name: Optional[str] = None
    father_name: Optional[str] = None
    mother_name: Optional[str] = None
    dob: Optional[str] = None            # ISO yyyy-mm-dd
    gender: Optional[str] = None
    id_number: Optional[str] = None      # Aadhaar (digits) / PAN
    # education
    institution: Optional[str] = None    # university / board
    degree: Optional[str] = None
    branch: Optional[str] = None
    year: Optional[int] = None
    division: Optional[str] = None
    roll_number: Optional[str] = None
    certificate_number: Optional[str] = None
    subjects: list[SubjectMark] = Field(default_factory=list)
    total_marks: Optional[float] = None
    max_total: Optional[float] = None
    percentage: Optional[float] = None
    cgpa: Optional[float] = None
    result: Optional[str] = None
    # where each field was found (field -> bbox) for region-weighted forensics
    field_boxes: dict[str, tuple[int, int, int, int]] = Field(default_factory=dict)


class QRData(BaseModel):
    raw: Optional[str] = None
    kind: Optional[str] = None           # aadhaar_secure | aadhaar_xml | url | text
    payload: dict[str, Any] = Field(default_factory=dict)
    signed_bytes: Optional[bytes] = None  # Aadhaar secure QR: data that was signed
    signature: Optional[bytes] = None


class DocumentObject(BaseModel):
    """Everything known about one uploaded file after Stage 3."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    doc_id: str
    path: str
    mime: str
    doc_type: DocType = DocType.UNKNOWN
    classifier_confidence: float = 0.0
    pages: list[np.ndarray] = Field(default_factory=list, exclude=True)  # BGR
    quality: dict[str, Any] = Field(default_factory=dict)
    ocr_tokens: list[OCRToken] = Field(default_factory=list)
    full_text: str = ""
    fields: ExtractedFields = Field(default_factory=ExtractedFields)
    photo: Optional[np.ndarray] = Field(default=None, exclude=True)
    photo_bbox: Optional[tuple[int, int, int, int]] = None
    qr: list[QRData] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    """Data coming from earlier pipeline stages (resume parser, bot interview)."""
    candidate_id: str
    name: Optional[str] = None
    dob: Optional[str] = None
    resume: dict[str, Any] = Field(default_factory=dict)
    interview: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------- results

class Signal(BaseModel):
    fraud_id: str                      # e.g. "F1"
    doc_id: Optional[str] = None       # None for candidate-level signals
    severity: Severity
    code: str                          # machine-readable, e.g. "AADHAAR_CHECKSUM_FAIL"
    reason: str                        # human-readable
    confidence: float = 1.0
    region: Optional[str] = None       # field name, for region weighting
    evidence: dict[str, Any] = Field(default_factory=dict)


class ModuleResult(BaseModel):
    fraud_id: str
    status: ModuleStatus
    signals: list[Signal] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class DocumentReport(BaseModel):
    doc_id: str
    doc_type: DocType
    verdict: Verdict
    score: float
    signals: list[Signal]


class CandidateReport(BaseModel):
    candidate_id: str
    verdict: Verdict
    score: float
    documents: list[DocumentReport]
    candidate_signals: list[Signal]
    modules: list[ModuleResult]
    intake_issues: list[str] = Field(default_factory=list)
