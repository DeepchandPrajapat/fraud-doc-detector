"""Degree certificate and marksheet field extraction (heuristic, layout-agnostic).

Education documents vary per board/university, so these rules recover the common
fields; the marks table parser is deliberately conservative. Per-board templates or an
LLM-based extractor (local DeepSeek) can replace this behind the same function names.
"""
from __future__ import annotations

import re

from fdd.extraction.fields.common import (
    clean_name,
    find_year,
    parse_date,
    to_float,
    value_after_label,
)
from fdd.schemas import ExtractedFields, SubjectMark

INSTITUTION = re.compile(r"([A-Z][A-Za-z.&,\- ]*?(University|Board|Council|Vidyapeeth|"
                         r"Institute of Technology|Education)[A-Za-z.,&\- ]*)", re.IGNORECASE)
DEGREE = re.compile(r"\b(Bachelor|Master|Doctor)\s+of\s+([A-Za-z ]+?)(?=\s+in\b|\s*\(|[,.]|$)", re.IGNORECASE)
DEGREE_ABBR = re.compile(r"\b(B\.?\s?Tech|B\.?\s?E|M\.?\s?Tech|B\.?\s?Sc|M\.?\s?Sc|B\.?\s?Com|"
                         r"M\.?\s?Com|B\.?\s?A|M\.?\s?A|BCA|MCA|MBA|BBA)\b\.?")
DIVISION = re.compile(r"\b(first class with distinction|first class|second class|"
                      r"third class|pass class|distinction|first division|second division|"
                      r"third division)\b", re.IGNORECASE)
MAX_MARK_VALUES = {25, 30, 40, 50, 60, 70, 75, 80, 100, 150, 200}
_HEADER = re.compile(r"subject|code|marks|max|min|total|obtained|grade|theory|practical|"
                     r"result|percentage|sgpa|cgpa|name|roll|father|mother|date", re.IGNORECASE)


def _institution(lines: list[str]) -> str | None:
    for line in lines[:12]:          # issuer is almost always in the header
        m = INSTITUTION.search(line)
        if m and len(m.group(1)) > 8:
            return re.sub(r"\s+", " ", m.group(1)).strip(" ,.")
    return None


def extract_degree(lines: list[str]) -> ExtractedFields:
    f = ExtractedFields()
    text = " ".join(lines)
    f.institution = _institution(lines)

    m = DEGREE.search(text)
    if m:
        f.degree = f"{m.group(1).title()} of {m.group(2).strip().title()}"
    else:
        m = DEGREE_ABBR.search(text)
        f.degree = m.group(1).replace(" ", "") if m else None

    b = re.search(r"\bin\s+([A-Z][A-Za-z &]+?(Engineering|Science|Technology|Commerce|Arts|"
                  r"Applications|Administration))", text)
    f.branch = b.group(1).strip() if b else None

    d = DIVISION.search(text)
    f.division = d.group(1).title() if d else None

    # year: prefer the exam/convocation phrase, else the latest plausible year
    y = re.search(r"(examination|held in|convocation|in the year)[^0-9]{0,40}(19|20)\d{2}", text, re.IGNORECASE)
    if y:
        f.year = find_year(y.group(0))
    else:
        years = [int(x) for x in re.findall(r"\b(?:19[6-9]\d|20[0-4]\d)\b", text)]
        f.year = max(years) if years else None

    n = re.search(r"(certify that|conferred (?:up)?on|awarded to)\s+(?:Mr\.?|Ms\.?|Miss|Shri|Smt\.?)?\s*"
                  r"([A-Z][A-Za-z .]{2,40}?)(?=\s+(son|daughter|s/o|d/o|has|having|who|bearing)\b|,)",
                  text, re.IGNORECASE)
    f.name = clean_name(n.group(2)) if n else clean_name(value_after_label(lines, r"name of the (student|candidate)"))
    cert = value_after_label(lines, r"(certificate|serial|sl\.?)\s*no\.?")
    f.certificate_number = cert.split()[0] if cert else None
    return f


def _parse_subject_line(line: str) -> SubjectMark | None:
    if _HEADER.fullmatch(line.strip()) or re.search(r"\btotal\b|grand", line, re.IGNORECASE):
        return None
    m = re.match(r"^\s*(?:(\d{2,6})\s+)?([A-Za-z][A-Za-z &.\-()/]{2,40}?)\s+([\d\s./A-Z+]+)$", line)
    if not m:
        return None
    code, subject, rest = m.groups()
    nums = [float(x) for x in re.findall(r"\b\d{1,3}(?:\.\d+)?\b", rest)]
    grade = re.search(r"\b([A-E][12]?\+?|O|F)\b\s*$", rest)
    nums = [n for n in nums if n <= 200]
    if not nums:
        return None
    max_marks = next((n for n in nums if n in MAX_MARK_VALUES and n >= max(nums)), None)
    obtained = [n for n in nums if n != max_marks] or nums
    return SubjectMark(subject=subject.strip().title(), code=code,
                       marks=obtained[-1], max_marks=max_marks,
                       grade=grade.group(1) if grade else None)


def extract_marksheet(lines: list[str]) -> ExtractedFields:
    f = ExtractedFields()
    text = " ".join(lines)
    f.institution = _institution(lines)
    f.name = clean_name(value_after_label(lines, r"(candidate'?s?\s*name|name of (the )?(candidate|student)|"
                                                 r"^\s*name)\s*[:\-]?"))
    f.father_name = clean_name(value_after_label(lines, r"father'?s?\s*name|guardian'?s?\s*name"))
    f.mother_name = clean_name(value_after_label(lines, r"mother'?s?\s*name"))
    dob = value_after_label(lines, r"date of birth|\bd\.?o\.?b\b")
    f.dob = parse_date(dob or "")
    roll = value_after_label(lines, r"roll\s*(no|number)\.?|seat\s*no\.?|reg(istration)?\.?\s*no\.?")
    f.roll_number = roll.split()[0] if roll else None

    y = re.search(r"(examination|exam|session|held in)[^0-9]{0,30}((?:19|20)\d{2})", text, re.IGNORECASE)
    f.year = int(y.group(2)) if y else find_year(text)

    f.subjects = [s for s in (_parse_subject_line(ln) for ln in lines) if s]

    tot = re.search(r"(grand\s+)?total[^0-9]{0,20}(\d{2,4}(?:\.\d+)?)(?:\s*/\s*|\s+out of\s+|\s+)(\d{2,4})?", text, re.IGNORECASE)
    if tot:
        f.total_marks = to_float(tot.group(2))
        f.max_total = to_float(tot.group(3))
    pct = re.search(r"(\d{2,3}(?:\.\d{1,2})?)\s*%|percentage[^0-9]{0,10}(\d{2,3}(?:\.\d{1,2})?)", text, re.IGNORECASE)
    if pct:
        f.percentage = to_float(pct.group(1) or pct.group(2))
    cg = re.search(r"\b(?:cgpa|cpi|ogpa|sgpa|gpa)\b[^0-9]{0,10}(\d{1,2}\.\d{1,2})", text, re.IGNORECASE)
    if cg:
        f.cgpa = to_float(cg.group(1))
    r = re.search(r"\bresult\b[^A-Za-z]{0,5}(pass(ed)?|fail(ed)?|promoted|compartment|essential repeat)", text, re.IGNORECASE)
    f.result = r.group(1).upper() if r else None
    return f
