"""Stage 3 dispatcher: fills a DocumentObject's fields/photo/qr/metadata by doc type."""
from __future__ import annotations

from fdd.extraction.fields.education import extract_degree, extract_marksheet
from fdd.extraction.fields.identity import extract_aadhaar, extract_pan
from fdd.extraction.metadata import extract_metadata
from fdd.extraction.ocr import tokens_to_lines
from fdd.extraction.photo import crop_face
from fdd.extraction.qr import extract_qr
from fdd.schemas import DocType, DocumentObject

FIELD_EXTRACTORS = {
    DocType.AADHAAR: extract_aadhaar,
    DocType.PAN: extract_pan,
    DocType.DEGREE: extract_degree,
    DocType.MARKSHEET_10: extract_marksheet,
    DocType.MARKSHEET_12: extract_marksheet,
    DocType.MARKSHEET_SEM: extract_marksheet,
}


def extract(doc: DocumentObject) -> DocumentObject:
    """Assumes doc.pages, doc.ocr_tokens and doc.doc_type are already set."""
    doc.metadata = extract_metadata(doc.path, doc.mime)

    try:
        doc.qr = extract_qr(doc.pages)
    except Exception as e:  # noqa: BLE001
        doc.errors.append(f"qr: {e}")

    if doc.doc_type in (DocType.AADHAAR, DocType.PAN, DocType.SELFIE) and doc.pages:
        doc.photo, doc.photo_bbox = crop_face(doc.pages[0])
        if doc.photo is None:
            doc.errors.append("no face found on document")

    fn = FIELD_EXTRACTORS.get(doc.doc_type)
    if fn:
        try:
            doc.fields = fn(tokens_to_lines(doc.ocr_tokens))
        except Exception as e:  # noqa: BLE001
            doc.errors.append(f"fields: {e}")
    return doc
