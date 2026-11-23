"""Locate and crop the holder photo on ID cards (used by F11 face match and F9 photo-swap checks).

V1 uses OpenCV's bundled Haar cascade (no downloads). F11 will re-detect/align with
InsightFace on the crop, so this only needs a reasonable region.
"""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np


@lru_cache(maxsize=1)
def _cascade():
    return cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def crop_face(img: np.ndarray, pad: float = 0.35) -> tuple[np.ndarray | None, tuple | None]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    min_side = max(24, min(gray.shape) // 20)
    faces = _cascade().detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5,
                                        minSize=(min_side, min_side))
    if len(faces) == 0:
        return None, None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])   # largest face = holder photo
    px, py = int(w * pad), int(h * pad)
    x1, y1 = max(0, x - px), max(0, y - py)
    x2, y2 = min(img.shape[1], x + w + px), min(img.shape[0], y + h + py)
    return img[y1:y2, x1:x2].copy(), (x1, y1, x2, y2)
