"""Aadhaar and PAN field extraction from OCR lines."""
from __future__ import annotations

import re

from fdd.extraction.fields.common import clean_name, find_year, parse_date, value_after_label
from fdd.schemas import ExtractedFields

AADHAAR_NUM = re.compile(r"\b([2-9]\d{3})\s?(\d{4})\s?(\d{4})\b")
PAN_NUM = re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b")
VID = re.compile(r"\bVID\b", re.IGNORECASE)
_NOISE = re.compile(r"government|india|authority|aadhaa?r|uidai|income|tax|department|"
                    r"permanent|account|signature|dob|birth|male|female|card", re.IGNORECASE)


def extract_aadhaar(lines: list[str]) -> ExtractedFields:
    f = ExtractedFields()
    for line in lines:
        if VID.search(line):          # 16-digit VID must not be mistaken for the number
            continue
        m = AADHAAR_NUM.search(line)
        if m:
            f.id_number = "".join(m.groups())
            break

    dob_idx = None
    for i, line in enumerate(lines):
        if re.search(r"\b(dob|date of birth|d\.o\.b)\b", line, re.IGNORECASE):
            f.dob = parse_date(line) or parse_date(lines[i + 1] if i + 1 < len(lines) else "")
            dob_idx = i
            break
        if re.search(r"year of birth|yob", line, re.IGNORECASE):
            y = find_year(line)
            f.dob = f"{y}" if y else None   # year only; downstream treats len==4 as YOB
            dob_idx = i
            break

    g = re.search(r"\b(male|female|transgender)\b", " ".join(lines), re.IGNORECASE)
    f.gender = g.group(1).upper() if g else None

    # name is conventionally the English line just above DOB
    if dob_idx is not None:
        for j in range(dob_idx - 1, max(-1, dob_idx - 4), -1):
            cand = lines[j]
            if re.fullmatch(r"[A-Za-z .']{3,}", cand.strip()) and not _NOISE.search(cand):
                f.name = clean_name(cand)
                break
    return f


def extract_pan(lines: list[str]) -> ExtractedFields:
    f = ExtractedFields()
    joined_upper = " ".join(lines).upper()
    m = PAN_NUM.search(joined_upper.replace(" ", " "))
    if m:
        f.id_number = m.group(1)

    # new-format cards have labels
    f.name = clean_name(value_after_label(lines, r"^\s*name\b(?!.*father)"))
    f.father_name = clean_name(value_after_label(lines, r"father'?s?\s*name"))
    dob_raw = value_after_label(lines, r"date of birth|\bdob\b")
    f.dob = parse_date(dob_raw or "") or parse_date(" ".join(lines))

    # old-format cards: name, father's name, DOB as consecutive unlabeled lines
    if not f.name:
        cands = [ln for ln in lines
                 if re.fullmatch(r"[A-Za-z .']{3,}", ln.strip()) and not _NOISE.search(ln)]
        if cands:
            f.name = clean_name(cands[0])
        if len(cands) > 1 and not f.father_name:
            f.father_name = clean_name(cands[1])
    return f
