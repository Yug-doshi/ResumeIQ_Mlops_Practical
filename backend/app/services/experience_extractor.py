"""Report explicit "N years ... experience" statements found in resume text.

This is information for the human reviewer. It is NOT part of the score and it
does not verify that a candidate meets an experience requirement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.utils.text_normalization import redact_contact_info

_YEARS = re.compile(r"(?<![\w.])(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)
_EXPERIENCE_WORD = re.compile(r"\bexperience\b|\bexp\b", re.IGNORECASE)


@dataclass(frozen=True)
class ExperienceMention:
    years: float
    snippet: str
    line: int


def extract_experience_mentions(text: str, max_mentions: int = 5, max_chars: int = 200) -> list[ExperienceMention]:
    mentions: list[ExperienceMention] = []
    for line_no, line in enumerate(text.split("\n"), start=1):
        if not _EXPERIENCE_WORD.search(line):
            continue
        for match in _YEARS.finditer(line):
            years = float(match.group(1))
            if years > 60:
                continue
            snippet = redact_contact_info(line.strip()[:max_chars])
            mentions.append(ExperienceMention(years=years, snippet=snippet, line=line_no))
            break  # one mention per line is enough
        if len(mentions) >= max_mentions:
            break
    return mentions
