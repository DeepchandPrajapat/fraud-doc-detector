"""Stage 2c: document type classifier.

V1 is a keyword/pattern scorer over OCR text: transparent, needs no training data,
and accurate enough for 4 very distinct document types. Once labelled samples exist,
swap in an image model (e.g. DiT / LayoutLMv3) behind the same `classify` signature.
"""
from __future__ import annotations

import re

from fdd.schemas import DocType

AADHAAR_NUM = re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b")
PAN_NUM = re.compile(r"\b[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]\b")

# (pattern, weight) per class; patterns are matched case-insensitively on OCR text
RULES: dict[DocType, list[tuple[str, float]]] = {
    DocType.AADHAAR: [
        (r"aadhaa?r", 3), (r"unique identification authority", 3), (r"\buidai\b", 3),
        (r"government of india", 1), (r"mera aadhaar", 2), (r"enrol?ment no", 1.5),
        (r"\bvid\b", 1), (r"\b(male|female)\b", 0.5),
    ],
    DocType.PAN: [
        (r"income\s*tax\s*department", 3), (r"permanent account number", 3),
        (r"\bpan\b", 1), (r"govt\.? of india", 1), (r"father'?s name", 0.5),
    ],
    DocType.DEGREE: [
        (r"\bdegree of\b", 3), (r"bachelor of|master of|doctor of", 2.5),
        (r"\bconvocation\b", 2.5), (r"conferred|has been admitted to", 2.5),
        (r"\buniversity\b", 1), (r"\bvice[- ]?chancellor\b", 1.5),
        (r"first class|second class|distinction", 1),
    ],
    DocType.MARKSHEET_10: [
        (r"(?<!senior )secondary school (examination|certificate)|\baisse\b", 3),(r"\bclass\s*(x|10)\b", 2.5),
        (r"\bs\.?s\.?l\.?c\b|\bs\.?s\.?c\b|matriculation|high school", 2.5),
        (r"marks? (statement|sheet)|statement of marks", 1.5),
        (r"date of birth", 1),
    ],
    DocType.MARKSHEET_12: [
        (r"senior secondary|senior school certificate|higher secondary|intermediate|\baissce\b", 3),
        (r"\bclass\s*(xii|12)\b", 2.5), (r"\bh\.?s\.?c\b|\bp\.?u\.?c\b|pre[- ]university", 2.5),
        (r"marks? (statement|sheet)|statement of marks", 1.5),
    ],
    DocType.MARKSHEET_SEM: [
        (r"\bsemester\b", 2.5), (r"\bsgpa\b|\bcgpa\b", 2.5), (r"grade card|grade sheet", 2.5),
        (r"credits?", 1.5), (r"\buniversity\b", 0.5),
        (r"marks? (statement|sheet)|statement of marks", 1),
        (r"consolidated", 1),
    ],
}


def classify(text: str) -> tuple[DocType, float, dict[str, float]]:
    """Return (doc_type, confidence 0..1, raw scores)."""
    t = text.lower()
    scores: dict[DocType, float] = {}
    for dtype, rules in RULES.items():
        scores[dtype] = sum(w for pat, w in rules if re.search(pat, t))

    # ID number patterns are near-decisive evidence
    if AADHAAR_NUM.search(text):
        scores[DocType.AADHAAR] += 2
    if PAN_NUM.search(text.upper()):
        scores[DocType.PAN] += 3

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]
    second = ranked[1][1]
    if best_score < 2:
        return DocType.UNKNOWN, 0.0, {k.value: v for k, v in scores.items()}
    # confidence = absolute strength x margin over runner-up
    conf = min(1.0, best_score / 6) * (best_score - second) / best_score
    return best, round(conf, 3), {k.value: v for k, v in scores.items()}
