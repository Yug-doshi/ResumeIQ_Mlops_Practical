"""Upload validation: extension, size and real file signature.

Nothing here writes to disk or executes content. File names are only ever used
for display, never to build filesystem paths.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import PurePosixPath, PureWindowsPath

from app.exceptions import ResumeParseError

ALLOWED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx"}


def sanitize_filename(name: str | None) -> str:
    """Return a display-safe base name (no directories, no control characters)."""
    name = name or "unnamed"
    name = PureWindowsPath(PurePosixPath(name).name).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return (name or "unnamed")[:255]


def get_extension(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def validate_upload(
    filename: str,
    content: bytes,
    max_bytes: int,
    max_docx_uncompressed_bytes: int,
) -> str:
    """Validate an upload and return its detected kind (``"pdf"`` or ``"docx"``)."""
    ext = get_extension(filename)
    if ext == ".doc":
        raise ResumeParseError(
            "unsupported_file_type",
            "Legacy .doc files are not supported. Save the resume as .docx or PDF and upload it again.",
        )
    if ext not in ALLOWED_EXTENSIONS:
        raise ResumeParseError(
            "unsupported_file_type",
            f"Unsupported file type '{ext or 'none'}'. Upload PDF or DOCX files.",
        )
    if len(content) == 0:
        raise ResumeParseError("empty_file", "The file is empty.")
    if len(content) > max_bytes:
        raise ResumeParseError(
            "file_too_large",
            f"The file is larger than the {max_bytes / (1024 * 1024):.1f} MB limit.",
        )

    kind = ALLOWED_EXTENSIONS[ext]
    if kind == "pdf":
        if b"%PDF-" not in content[:1024]:
            raise ResumeParseError(
                "file_type_mismatch",
                "The file has a .pdf extension but its contents are not a PDF.",
            )
    else:
        _validate_docx_container(content, max_docx_uncompressed_bytes)
    return kind


def _validate_docx_container(content: bytes, max_uncompressed: int) -> None:
    if not content.startswith(b"PK"):
        raise ResumeParseError(
            "file_type_mismatch",
            "The file has a .docx extension but its contents are not a DOCX document.",
        )
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            if "word/document.xml" not in names:
                raise ResumeParseError(
                    "file_type_mismatch",
                    "The file is a ZIP archive but not a Word (.docx) document.",
                )
            total = sum(info.file_size for info in archive.infolist())
            if total > max_uncompressed:
                raise ResumeParseError(
                    "file_too_large",
                    "The document expands to an unsafe size and was rejected.",
                )
    except zipfile.BadZipFile as exc:
        raise ResumeParseError("corrupted_file", "The DOCX file is corrupted and cannot be opened.") from exc
