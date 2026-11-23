"""Shared parsing helpers for field extractors."""
from __future__ import annotations

import re
from datetime import date

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

_DATE_NUM = re.compile(r"\b(\d{1,2})[./\-\s](\d{1,2})[./\-\s](\d{4})\b")
_DATE_TXT = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[\s\-]+([A-Za-z]{3,9})[,\s\-]+(\d{4})\b")
_YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


def parse_date(s: str) -> str | None:
    """Indian documents are day-first. Returns ISO yyyy-mm-dd or None."""
    if not s:
        return None
    m = _DATE_NUM.search(s)
    if m:
        d, mo, y = map(int, m.groups())
    else:
        m = _DATE_TXT.search(s)
        if not m or m.group(2)[:3].lower() not in MONTHS:
            return None
        d, mo, y = int(m.group(1)), MONTHS[m.group(2)[:3].lower()], int(m.group(3))
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def find_year(s: str) -> int | None:
    m = _YEAR.search(s)
    return int(m.group(1)) if m else None


def clean_name(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"[^A-Za-z .']", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s.title() if len(s) >= 2 else None


def value_after_label(lines: list[str], label_pat: str, max_lookahead: int = 1) -> str | None:
    """Value on the same line after `label:` or, failing that, on the next line(s)."""
    rx = re.compile(label_pat, re.IGNORECASE)
    for i, line in enumerate(lines):
        m = rx.search(line)
        if not m:
            continue
        rest = line[m.end():].strip(" :-/|")
        if rest:
            return rest
        for j in range(1, max_lookahead + 1):
            if i + j < len(lines) and lines[i + j].strip():
                return lines[i + j].strip()
    return None


def to_float(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None
