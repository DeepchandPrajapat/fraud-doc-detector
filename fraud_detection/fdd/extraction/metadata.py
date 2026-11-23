"""File metadata extraction. Raw facts only; F8 decides what is suspicious."""
from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image
from PIL.ExifTags import TAGS


def pdf_metadata(path: Path) -> dict:
    raw = path.read_bytes()
    doc = fitz.open(path)
    fonts: set[str] = set()
    text_pages = 0
    image_count = 0
    for page in doc:
        fonts.update(f[3] for f in page.get_fonts(full=True))
        if page.get_text().strip():
            text_pages += 1
        image_count += len(page.get_images(full=True))
    meta = {
        "kind": "pdf",
        "info": {k: v for k, v in (doc.metadata or {}).items() if v},
        "page_count": doc.page_count,
        # each incremental save appends a new %%EOF; >1 means edited after creation
        "eof_markers": raw.count(b"%%EOF"),
        "has_xmp": b"<x:xmpmeta" in raw,
        "fonts": sorted(fonts),
        "text_layer_pages": text_pages,   # 0 => pure scan, >0 => digitally generated/edited
        "embedded_images": image_count,
        "is_signed": bool(doc.get_sigflags() > 0) if hasattr(doc, "get_sigflags") else None,
    }
    doc.close()
    return meta


def image_metadata(path: Path) -> dict:
    with Image.open(path) as im:
        exif = {}
        try:
            for tag_id, val in (im.getexif() or {}).items():
                tag = TAGS.get(tag_id, str(tag_id))
                exif[tag] = val.decode(errors="ignore") if isinstance(val, bytes) else str(val)
        except Exception:  # noqa: BLE001
            pass
        info = {k: str(v) for k, v in im.info.items() if isinstance(v, (str, int, float))}
        meta = {"kind": "image", "format": im.format, "mode": im.mode,
                "size": im.size, "exif": exif, "info": info}
        if im.format == "JPEG":
            q = getattr(im, "quantization", None)
            meta["jpeg_quant_tables"] = len(q) if q else None
    return meta


def extract_metadata(path: str | Path, mime: str) -> dict:
    path = Path(path)
    try:
        return pdf_metadata(path) if mime == "application/pdf" else image_metadata(path)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
