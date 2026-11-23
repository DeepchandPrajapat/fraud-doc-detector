"""Debug tool: run Stages 2-3 on one file and print what was extracted.

usage: python scripts/inspect_document.py path/to/file.pdf [--type AADHAAR] [--ocr tesseract]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings  # noqa: E402
from fdd.pipeline import ingest  # noqa: E402
from fdd.schemas import DocType  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--type", choices=[t.value for t in DocType])
    ap.add_argument("--ocr", choices=["easyocr", "tesseract"])
    args = ap.parse_args()
    if args.ocr:
        settings.ocr_backend = args.ocr

    doc = ingest(args.path, DocType(args.type) if args.type else None)
    out = {
        "doc_type": doc.doc_type, "classifier_confidence": doc.classifier_confidence,
        "quality": doc.quality,
        "fields": doc.fields.model_dump(exclude_none=True, exclude={"field_boxes"}),
        "photo_found": doc.photo is not None, "photo_bbox": doc.photo_bbox,
        "qr": [{"kind": q.kind, "payload": q.payload} for q in doc.qr],
        "metadata": doc.metadata, "errors": doc.errors,
        "ocr_lines": doc.full_text.splitlines()[:60],
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
