"""OCR backends behind one interface. EasyOCR (GPU) is the default; Tesseract is the
lightweight fallback. Tokens keep bounding boxes, which F9 (region-weighted tampering)
and the field extractors rely on."""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np

from config.settings import settings
from fdd.schemas import OCRToken


@lru_cache(maxsize=1)
def _easyocr_reader():
    import easyocr
    return easyocr.Reader(list(settings.ocr_languages), gpu=settings.ocr_gpu, verbose=False)


def _ocr_easyocr(img: np.ndarray, page: int) -> list[OCRToken]:
    results = _easyocr_reader().readtext(img, paragraph=False)
    tokens = []
    for pts, text, conf in results:
        xs = [int(p[0]) for p in pts]
        ys = [int(p[1]) for p in pts]
        tokens.append(OCRToken(text=text, bbox=(min(xs), min(ys), max(xs), max(ys)),
                               conf=float(conf), page=page))
    return tokens


def _ocr_tesseract(img: np.ndarray, page: int) -> list[OCRToken]:
    import pytesseract
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    data = pytesseract.image_to_data(rgb, output_type=pytesseract.Output.DICT)
    tokens = []
    for i, text in enumerate(data["text"]):
        if not text.strip() or float(data["conf"][i]) < 0:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        tokens.append(OCRToken(text=text, bbox=(x, y, x + w, y + h),
                               conf=float(data["conf"][i]) / 100, page=page))
    return tokens


def run_ocr(pages: list[np.ndarray]) -> list[OCRToken]:
    fn = _ocr_easyocr if settings.ocr_backend == "easyocr" else _ocr_tesseract
    tokens: list[OCRToken] = []
    for i, img in enumerate(pages):
        tokens.extend(fn(img, i))
    return tokens


def tokens_to_lines(tokens: list[OCRToken], y_tol: float = 0.6) -> list[str]:
    """Group tokens into reading-order lines (same page, overlapping vertical span)."""
    lines: list[list[OCRToken]] = []
    for tok in sorted(tokens, key=lambda t: (t.page, (t.bbox[1] + t.bbox[3]) / 2, t.bbox[0])):
        cy = (tok.bbox[1] + tok.bbox[3]) / 2
        h = tok.bbox[3] - tok.bbox[1]
        if lines:
            last = lines[-1][-1]
            lcy = (last.bbox[1] + last.bbox[3]) / 2
            if last.page == tok.page and abs(cy - lcy) <= y_tol * max(h, 1):
                lines[-1].append(tok)
                continue
        lines.append([tok])
    return [" ".join(t.text for t in sorted(line, key=lambda t: t.bbox[0])) for line in lines]
