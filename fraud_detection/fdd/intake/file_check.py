"""Stage 2a: file-level validation and loading into page images."""
from __future__ import annotations

from pathlib import Path

import cv2
import fitz  # PyMuPDF
import numpy as np

from config.settings import settings

_MAGIC = {
    b"%PDF": "application/pdf",
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


class IntakeError(Exception):
    pass


def sniff_mime(path: Path) -> str:
    """Detect type from file bytes, not the extension (renamed files are common)."""
    head = path.read_bytes()[:8]
    for magic, mime in _MAGIC.items():
        if head.startswith(magic):
            return mime
    raise IntakeError(f"Unsupported or corrupted file: {path.name}")


def check_file(path: str | Path) -> str:
    path = Path(path)
    if not path.is_file():
        raise IntakeError(f"File not found: {path}")
    if path.suffix.lower() not in settings.allowed_extensions:
        raise IntakeError(f"Extension {path.suffix} not allowed")
    size_mb = path.stat().st_size / 1e6
    if size_mb > settings.max_file_mb:
        raise IntakeError(f"File too large ({size_mb:.1f} MB)")
    if size_mb == 0:
        raise IntakeError("Empty file")
    return sniff_mime(path)


def load_pages(path: str | Path, mime: str) -> list[np.ndarray]:
    """Return BGR page images. PDFs are rendered at settings.pdf_render_dpi."""
    path = Path(path)
    if mime == "application/pdf":
        try:
            doc = fitz.open(path)
        except Exception as e:  # noqa: BLE001
            raise IntakeError(f"Cannot open PDF: {e}") from e
        if doc.needs_pass:
            raise IntakeError("Password-protected PDF")
        if doc.page_count > settings.max_pdf_pages:
            raise IntakeError(f"PDF has {doc.page_count} pages (max {settings.max_pdf_pages})")
        pages = []
        zoom = settings.pdf_render_dpi / 72
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            pages.append(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        doc.close()
        return pages

    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise IntakeError("Cannot decode image")
    return [img]
