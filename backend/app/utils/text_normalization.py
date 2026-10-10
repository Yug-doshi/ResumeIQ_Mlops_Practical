"""Text normalisation helpers (pure functions, no I/O)."""
from __future__ import annotations

import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")
_ZERO_WIDTH = re.compile(r"[\u200b-\u200d\u2060\ufeff\u00ad]")
_HSPACE = re.compile(r"[ \t\u00a0\u2000-\u200a\u202f\u205f\u3000]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w])\+?\d[\d\s().-]{7,}\d(?![\w])")


def normalize_text(text: str) -> str:
    """Normalise unicode and whitespace while keeping line structure."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n")
    text = _ZERO_WIDTH.sub("", text)
    text = _CONTROL.sub("", text)
    text = _HSPACE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _redact_phone(match: re.Match) -> str:
    raw = match.group(0)
    groups = re.findall(r"\d+", raw)
    digits = sum(len(g) for g in groups)
    # Leave year ranges such as "2019 - 2023" alone.
    if all(len(g) == 4 and 1950 <= int(g) <= 2100 for g in groups):
        return raw
    if 10 <= digits <= 15:
        return "[phone redacted]"
    return raw


def redact_contact_info(text: str) -> str:
    """Mask e-mail addresses and phone numbers (used for evidence snippets)."""
    text = _EMAIL.sub("[email redacted]", text)
    return _PHONE.sub(_redact_phone, text)


def split_list_input(value) -> list[str]:
    """Turn ``"a, b\\nc"`` or ``["a", "b"]`` or a JSON array string into a list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = [str(v) for v in value]
    else:
        raw = str(value).strip()
        if not raw:
            return []
        if raw.startswith("["):
            import json

            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return split_list_input(parsed)
            except ValueError:
                pass
        items = re.split(r"[,;\n]+", raw)
    return [collapse_whitespace(i) for i in items if collapse_whitespace(i)]
