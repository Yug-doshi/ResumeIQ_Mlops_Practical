"""Resume text extraction (PDF and DOCX).

Kept independent of FastAPI so it can be reused from tests, batch jobs or a
future Airflow task. To add OCR later, implement another ``_extract_*``
function and register it in ``extract_resume_text``.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

import pymupdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.exceptions import ResumeParseError
from app.utils.file_validation import validate_upload
from app.utils.text_normalization import normalize_text

SHORT_TEXT_WARNING_CHARS = 300


@dataclass(frozen=True)
class ParserLimits:
    max_file_bytes: int = 5 * 1024 * 1024
    max_docx_uncompressed_bytes: int = 50 * 1024 * 1024
    max_pdf_pages: int = 30
    max_extracted_chars: int = 200_000
    min_extracted_chars: int = 30


@dataclass
class ParsedResume:
    text: str
    file_type: str
    warnings: list[str] = field(default_factory=list)


def _extract_pdf(file_bytes: bytes, max_pages: int) -> tuple[str, list[str]]:
    warnings: list[str] = []
    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ResumeParseError("corrupted_file", "The PDF is corrupted and cannot be opened.") from exc
    try:
        if doc.needs_pass:
            raise ResumeParseError(
                "encrypted_file", "The PDF is password-protected. Remove the password and upload it again."
            )
        total_pages = doc.page_count
        pages = min(total_pages, max_pages)
        parts = []
        try:
            for index in range(pages):
                parts.append(doc[index].get_text("text"))
        except Exception as exc:
            raise ResumeParseError("corrupted_file", "The PDF is damaged and its text could not be read.") from exc
        if total_pages > pages:
            warnings.append(f"Only the first {pages} of {total_pages} pages were read.")
    finally:
        doc.close()
    return "\n\n".join(parts), warnings


def extract_text_from_pdf(file_bytes: bytes, max_pages: int = 30) -> str:
    """Extract normalised text from PDF bytes. Raises ``ResumeParseError`` if empty."""
    text, _ = _extract_pdf(file_bytes, max_pages)
    text = normalize_text(text)
    if not text:
        raise ResumeParseError(
            "no_extractable_text",
            "No text could be extracted. The PDF may be a scan or image; OCR is not supported yet.",
        )
    return text


def _iter_docx_blocks(document):
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            yield Paragraph(child, document)
        elif tag == "tbl":
            yield Table(child, document)


def _extract_docx(file_bytes: bytes) -> str:
    try:
        document = Document(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ResumeParseError("corrupted_file", "The DOCX file is corrupted and cannot be opened.") from exc
    parts: list[str] = []
    try:
        for block in _iter_docx_blocks(document):
            if isinstance(block, Paragraph):
                parts.append(block.text)
            else:
                for row in block.rows:
                    seen = []
                    cells = []
                    for cell in row.cells:
                        if any(cell._tc is other for other in seen):
                            continue  # merged cell repeated
                        seen.append(cell._tc)
                        cells.append(cell.text.strip())
                    parts.append(" | ".join(c for c in cells if c))
    except Exception as exc:
        raise ResumeParseError("corrupted_file", "The DOCX file is damaged and its text could not be read.") from exc
    return "\n".join(parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract normalised text from DOCX bytes. Raises ``ResumeParseError`` if empty."""
    text = normalize_text(_extract_docx(file_bytes))
    if not text:
        raise ResumeParseError("empty_document", "The document contains no text.")
    return text


def extract_resume_text(filename: str, file_bytes: bytes, limits: ParserLimits | None = None) -> ParsedResume:
    """Validate and extract text from an uploaded resume."""
    limits = limits or ParserLimits()
    kind = validate_upload(
        filename, file_bytes, limits.max_file_bytes, limits.max_docx_uncompressed_bytes
    )
    warnings: list[str] = []
    if kind == "pdf":
        raw, warnings = _extract_pdf(file_bytes, limits.max_pdf_pages)
        text = normalize_text(raw)
        empty_code, empty_message = (
            "no_extractable_text",
            "No text could be extracted. The PDF may be a scan or image; OCR is not supported yet.",
        )
    else:
        text = normalize_text(_extract_docx(file_bytes))
        empty_code, empty_message = "empty_document", "The document contains no text."

    if len(text) < limits.min_extracted_chars:
        if not text:
            raise ResumeParseError(empty_code, empty_message)
        raise ResumeParseError(
            "insufficient_text",
            "Too little text was extracted to analyse this resume.",
        )
    if len(text) > limits.max_extracted_chars:
        text = text[: limits.max_extracted_chars]
        warnings.append("The document was very long; only the first part of its text was analysed.")
    if len(text) < SHORT_TEXT_WARNING_CHARS:
        warnings.append("Very little text was extracted; results may be unreliable.")
    return ParsedResume(text=text, file_type=kind, warnings=warnings)
