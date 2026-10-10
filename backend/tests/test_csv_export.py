import csv
import io

from app.schemas import CandidateResult, ExperienceInfo, FileError, ScoreBreakdown
from app.utils.csv_export import build_results_csv, sanitize_cell


def candidate(filename):
    return CandidateResult(
        resume_id="abc", rank=1, upload_index=0, filename=filename, score=71.234, semantic_score=60.0,
        semantic_cosine=0.6, required_matched=["=cmd|' /C calc'!A0"], required_not_found=["Docker"],
        preferred_matched=[], preferred_not_found=[], extracted_skills=[],
        score_breakdown=ScoreBreakdown(final_score=71.234, components=[], notes=[], scoring_version="1"),
        experience=ExperienceInfo(status="not_requested", note=""), extracted_characters=100, model_id="m")


def test_sanitize_cell():
    for bad in ["=1+1", "+SUM(A1)", "-2+3", "@cmd", "\t=1", "\r=1"]:
        assert sanitize_cell(bad).startswith("'")
    assert sanitize_cell("normal.pdf") == "normal.pdf"
    assert sanitize_cell(42.5) == 42.5


def test_csv_content_and_injection_protection():
    raw = build_results_csv([candidate("=HYPERLINK(\"http://evil\")")], [FileError(upload_index=1, filename="@x.pdf", code="corrupted_file", message="m")])
    assert raw.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert rows[0][0] == "resume_id" and "semantic_score" in rows[0] and "processing_status" in rows[0]
    assert rows[1][2].startswith("'=") and rows[1][3] == "71.2"
    assert rows[1][5].startswith("'=")  # skill cells are sanitised too
    assert rows[2][2] == "'@x.pdf" and rows[2][-1] == "failed: corrupted_file"
    assert "resume_text" not in raw.decode("utf-8-sig")
