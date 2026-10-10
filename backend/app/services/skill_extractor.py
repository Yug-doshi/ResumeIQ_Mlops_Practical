"""Deterministic, dictionary-based skill extraction.

* The dictionary lives in ``config/skills.json`` (versioned, hashed).
* Matching is case-insensitive and boundary-aware, so "Java" does not match
  inside "JavaScript" and "Git" does not match inside "GitHub".
* Skills that are not in the dictionary but are requested by the recruiter are
  still searched in the resume with the same boundary-aware rules.

This does NOT identify every skill that may appear in a resume; it finds the
configured skills and their aliases only.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.utils.text_normalization import collapse_whitespace, redact_contact_info

# A skill must not be glued to word characters, '.', '+' or '#' on the left,
# nor to word characters, '+', '#' or ".word" (as in "Java.util") on the right.
_LEFT = r"(?<![\w.+#])"
_RIGHT = r"(?![\w+#]|\.\w)"


def _key(term: str) -> str:
    return re.sub(r"[\s\-_]+", " ", term.strip().lower())


def _term_regex(term: str) -> str:
    tokens = [t for t in re.split(r"[\s\-]+", term.strip()) if t]
    return r"[\s\-]+".join(re.escape(t) for t in tokens)


def _compile(terms: list[str], ignore_case: bool) -> re.Pattern | None:
    terms = sorted({t for t in terms if t.strip()}, key=len, reverse=True)
    if not terms:
        return None
    body = "|".join(_term_regex(t) for t in terms)
    flags = re.IGNORECASE if ignore_case else 0
    return re.compile(f"{_LEFT}(?:{body}){_RIGHT}", flags)


@dataclass(frozen=True)
class SkillEntry:
    name: str
    category: str
    aliases: tuple[str, ...]
    case_sensitive_terms: tuple[str, ...]


@dataclass(frozen=True)
class SkillDictionary:
    version: str
    entries: tuple[SkillEntry, ...]
    sha256: str

    @classmethod
    def from_file(cls, path: Path) -> "SkillDictionary":
        raw = Path(path).read_bytes()
        data = json.loads(raw.decode("utf-8"))
        entries = []
        for name, spec in data["skills"].items():
            entries.append(
                SkillEntry(
                    name=name,
                    category=spec.get("category", "other"),
                    aliases=tuple(spec.get("aliases", [])),
                    case_sensitive_terms=tuple(spec.get("case_sensitive_terms", [])),
                )
            )
        return cls(version=data.get("version", "unversioned"), entries=tuple(entries), sha256=hashlib.sha256(raw).hexdigest())


@dataclass(frozen=True)
class Evidence:
    skill: str
    snippet: str
    line: int


class SkillExtractor:
    def __init__(self, dictionary: SkillDictionary):
        self.dictionary = dictionary
        self._patterns: dict[str, list[re.Pattern]] = {}
        self._alias_to_canonical: dict[str, str] = {}
        for entry in dictionary.entries:
            terms = [entry.name, *entry.aliases]
            sensitive = [t for t in terms if t in entry.case_sensitive_terms]
            insensitive = [t for t in terms if t not in entry.case_sensitive_terms]
            patterns = [
                p
                for p in (_compile(insensitive, True), _compile(sensitive, False))
                if p is not None
            ]
            self._patterns[entry.name] = patterns
            for term in terms:
                self._alias_to_canonical.setdefault(_key(term), entry.name)
        self._custom_cache: dict[str, re.Pattern] = {}

    @classmethod
    def from_file(cls, path: Path) -> "SkillExtractor":
        return cls(SkillDictionary.from_file(path))

    # ---- normalisation -------------------------------------------------
    def normalize_requirement(self, raw: str) -> str:
        """Map user input (alias, any casing) to a canonical name, else keep it as typed."""
        cleaned = collapse_whitespace(raw)
        return self._alias_to_canonical.get(_key(cleaned), cleaned)

    def normalize_requirements(self, raws: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for raw in raws:
            name = self.normalize_requirement(raw)
            if name and name.lower() not in seen:
                seen.add(name.lower())
                result.append(name)
        return result

    # ---- matching ------------------------------------------------------
    def _patterns_for(self, skill: str) -> list[re.Pattern]:
        if skill in self._patterns:
            return self._patterns[skill]
        if skill not in self._custom_cache:
            self._custom_cache[skill] = re.compile(f"{_LEFT}(?:{_term_regex(skill)}){_RIGHT}", re.IGNORECASE)
        return [self._custom_cache[skill]]

    def contains_skill(self, text: str, skill: str) -> bool:
        return any(p.search(text) for p in self._patterns_for(skill))

    def extract_skills(self, text: str) -> list[str]:
        """Return unique canonical dictionary skills found in ``text`` (dictionary order)."""
        return [e.name for e in self.dictionary.entries if self.contains_skill(text, e.name)]

    def find_evidence(self, text: str, skill: str, max_snippets: int = 2, max_chars: int = 220) -> list[Evidence]:
        """Return verbatim excerpts of ``text`` around matches of ``skill``.

        Excerpts come directly from the extracted text; only e-mail addresses
        and phone numbers are masked. ``line`` is the 1-based line number in the
        extracted text.
        """
        spans: list[tuple[int, int]] = []
        for pattern in self._patterns_for(skill):
            spans.extend(m.span() for m in pattern.finditer(text))
        spans.sort()
        results: list[Evidence] = []
        seen_lines: set[int] = set()
        for start, end in spans:
            line_start = text.rfind("\n", 0, start) + 1
            line_end = text.find("\n", end)
            line_end = len(text) if line_end == -1 else line_end
            line_no = text.count("\n", 0, line_start) + 1
            if line_no in seen_lines:
                continue
            seen_lines.add(line_no)
            if line_end - line_start <= max_chars:
                snippet = text[line_start:line_end]
            else:
                half = max_chars // 2
                lo = max(line_start, start - half)
                hi = min(line_end, end + half)
                snippet = ("…" if lo > line_start else "") + text[lo:hi] + ("…" if hi < line_end else "")
            snippet = redact_contact_info(snippet.strip())
            if snippet:
                results.append(Evidence(skill=skill, snippet=snippet, line=line_no))
            if len(results) >= max_snippets:
                break
        return results
