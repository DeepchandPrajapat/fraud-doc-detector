"""Stage 2b: image quality gate. Bad images go back to the candidate before any analysis,
so forensic modules never run on unusable input (a major source of false positives)."""
from __future__ import annotations

import cv2
import numpy as np

from config.settings import settings


def assess_quality(img: np.ndarray) -> dict:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = gray.shape
    # normalise scale so blur score is comparable across resolutions
    scale = 1000 / max(h, w)
    small = cv2.resize(gray, None, fx=scale, fy=scale) if scale < 1 else gray

    blur_var = float(cv2.Laplacian(small, cv2.CV_64F).var())
    brightness = float(small.mean())
    glare_ratio = float((small >= 250).mean())
    # Clean scans and digital PDFs have a pure-white background, which is not glare.
    # Glare/overexposure only make sense for photos, where the paper is off-white
    # and a flash reflection stands out as a saturated patch.
    clean_background = float(np.median(small)) >= 245

    issues = []
    if min(h, w) < settings.min_short_side_px:
        issues.append(f"low resolution ({w}x{h})")
    if blur_var < settings.min_blur_variance:
        issues.append(f"blurry (score {blur_var:.0f})")
    if brightness < settings.min_brightness:
        issues.append("too dark")
    if not clean_background:
        if brightness > settings.max_brightness:
            issues.append("overexposed")
        if glare_ratio > settings.max_glare_ratio:
            issues.append(f"glare ({glare_ratio:.0%} saturated)")

    return {
        "width": w, "height": h,
        "blur_variance": round(blur_var, 1),
        "brightness": round(brightness, 1),
        "glare_ratio": round(glare_ratio, 4),
        "clean_background": clean_background,
        "issues": issues,
        "ok": not issues,
    }
