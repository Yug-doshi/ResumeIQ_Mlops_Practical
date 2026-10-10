"""CSV export with spreadsheet formula-injection protection.

Untrusted text (file names, skill names) is prefixed with an apostrophe when it
could be interpreted as a formula by Excel / LibreOffice / Google Sheets.
Full resume text and evidence snippets are never exported.
"""
from __future__ import annotations

import csv
import io
from typing import Iterable

from app.schemas import CandidateResult, FileError

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")

COLUMNS = [
    "resume_id",
    "rank",
    "filename",
    "final_score",
    "semantic_score",
    "required_skills_matched",
    "required_skills_not_found_in_resume",
    "preferred_skills_matched",
    "preferred_skills_not_found_in_resume",
    "processing_status",
]


def sanitize_cell(value) -> str | int | float:
    """Neutralise formula triggers in text cells; numbers pass through unchanged."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = "" if value is None else str(value)
    if text.lstrip().startswith(_DANGEROUS_PREFIXES) or text.startswith(_DANGEROUS_PREFIXES):
        return "'" + text
    return text


def _join(items: Iterable[str]) -> str:
    return "; ".join(items)


def build_results_csv(candidates: list[CandidateResult], errors: list[FileError]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    for c in candidates:
        row = [
            c.resume_id, c.rank, c.filename, round(c.score, 1), round(c.semantic_score, 1),
            _join(c.required_matched), _join(c.required_not_found),
            _join(c.preferred_matched), _join(c.preferred_not_found),
            c.status,
        ]
        writer.writerow([sanitize_cell(v) for v in row])
    for e in errors:
        row = ["", "", e.filename, "", "", "", "", "", "", f"failed: {e.code}"]
        writer.writerow([sanitize_cell(v) for v in row])
    # UTF-8 BOM so Excel on Windows detects the encoding.
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")
