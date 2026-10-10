import pytest

from app.exceptions import ResumeParseError
from app.services.resume_parser import (
    ParserLimits,
    extract_resume_text,
    extract_text_from_docx,
    extract_text_from_pdf,
)
from app.utils.file_validation import sanitize_filename
from tests.conftest import PYTHON_RESUME, make_blank_pdf, make_docx, make_pdf


def test_valid_pdf():
    text = extract_text_from_pdf(make_pdf(PYTHON_RESUME))
    assert "FastAPI" in text and "Kubernetes" in text


def test_valid_docx():
    text = extract_text_from_docx(make_docx(PYTHON_RESUME))
    assert "scikit-learn" in text


def test_extract_resume_text_normalizes_whitespace():
    parsed = extract_resume_text("a.docx", make_docx("Python    developer\n\n\n\n\nwith   Docker experience   today"))
    assert "Python developer" in parsed.text
    assert "\n\n\n" not in parsed.text and "  " not in parsed.text
    assert parsed.file_type == "docx"


def test_empty_pdf_has_no_extractable_text():
    with pytest.raises(ResumeParseError) as exc:
        extract_resume_text("scan.pdf", make_blank_pdf())
    assert exc.value.code == "no_extractable_text"
    assert "OCR" in exc.value.message


def test_empty_docx():
    with pytest.raises(ResumeParseError) as exc:
        extract_resume_text("e.docx", make_docx(""))
    assert exc.value.code == "empty_document"


def test_zero_byte_file():
    with pytest.raises(ResumeParseError) as exc:
        extract_resume_text("a.pdf", b"")
    assert exc.value.code == "empty_file"


def test_corrupted_pdf_with_valid_header():
    with pytest.raises(ResumeParseError) as exc:
        extract_resume_text("bad.pdf", b"%PDF-1.7\nthis is not really a pdf at all" * 5)
    assert exc.value.code == "corrupted_file"


def test_corrupted_docx():
    with pytest.raises(ResumeParseError) as exc:
        extract_resume_text("bad.docx", b"PK\x03\x04 broken zip data")
    assert exc.value.code == "corrupted_file"


def test_wrong_signature():
    with pytest.raises(ResumeParseError) as exc:
        extract_resume_text("fake.pdf", b"MZ\x90\x00 this is an executable renamed")
    assert exc.value.code == "file_type_mismatch"
    with pytest.raises(ResumeParseError) as exc:
        extract_resume_text("fake.docx", b"%PDF-1.4 not a docx")
    assert exc.value.code == "file_type_mismatch"


@pytest.mark.parametrize("name", ["resume.txt", "resume.exe", "resume", "resume.doc"])
def test_unsupported_extensions(name):
    with pytest.raises(ResumeParseError) as exc:
        extract_resume_text(name, b"hello world hello world hello world")
    assert exc.value.code == "unsupported_file_type"


def test_oversized_file():
    limits = ParserLimits(max_file_bytes=1000)
    with pytest.raises(ResumeParseError) as exc:
        extract_resume_text("big.pdf", make_pdf(PYTHON_RESUME), limits)
    assert exc.value.code == "file_too_large"


def test_too_little_text():
    with pytest.raises(ResumeParseError) as exc:
        extract_resume_text("tiny.docx", make_docx("Hi"))
    assert exc.value.code == "insufficient_text"


def test_short_text_warning():
    parsed = extract_resume_text("short.docx", make_docx("Python developer with Docker experience."))
    assert any("Very little text" in w for w in parsed.warnings)


def test_sanitize_filename_strips_paths():
    assert sanitize_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_filename("C:\\Users\\x\\cv.docx") == "cv.docx"
    assert sanitize_filename("a\x00b.pdf") == "ab.pdf"
