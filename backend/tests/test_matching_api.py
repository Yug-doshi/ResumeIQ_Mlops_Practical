import csv
import io

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.semantic_matcher import SemanticMatcher
from tests.conftest import (
    JAVA_RESUME, PYTHON_RESUME, FakeBackend, files, form, make_blank_pdf, make_docx, make_pdf,
)


def post(client, data=None, items=()):
    return client.post("/api/v1/match", data=data if data is not None else form(), files=files(*items))


def test_multiple_resumes_ranked(client):
    r = post(client, items=[("java.docx", make_docx(JAVA_RESUME)), ("python.pdf", make_pdf(PYTHON_RESUME))])
    assert r.status_code == 200
    body = r.json()
    assert [c["filename"] for c in body["candidates"]] == ["python.pdf", "java.docx"]
    assert [c["rank"] for c in body["candidates"]] == [1, 2]
    top, second = body["candidates"]
    assert top["score"] > second["score"]
    assert top["required_matched"] == ["Python", "Docker", "Kubernetes"] and top["required_not_found"] == []
    assert top["preferred_matched"] == ["AWS"] and top["preferred_not_found"] == ["Apache Airflow"]
    assert second["required_matched"] == [] and second["required_not_found"] == ["Python", "Docker", "Kubernetes"]
    assert 0 <= second["score"] <= top["score"] <= 100
    assert body["summary"] == {"total_uploaded": 2, "processed": 2, "failed": 0, "candidates_with_results": 2,
                               "average_score": round((top["score"] + second["score"]) / 2, 2)}
    assert body["model_id"] == "fake/bag-of-words"
    assert "not probabilities" in body["score_disclaimer"]
    assert body["job"]["required_skills"] == ["Python", "Docker", "Kubernetes"]


def test_breakdown_and_evidence_traceable(client):
    c = post(client, items=[("p.pdf", make_pdf(PYTHON_RESUME))]).json()["candidates"][0]
    assert {x["key"] for x in c["score_breakdown"]["components"]} == {"required_skills", "preferred_skills", "semantic_similarity"}
    assert sum(x["contribution"] for x in c["score_breakdown"]["components"]) == pytest_approx(c["score"])
    assert c["evidence"] and all(e["skill"] in c["required_matched"] + c["preferred_matched"] for e in c["evidence"])
    joined = " ".join(e["snippet"] for e in c["evidence"])
    assert "jane.doe@example.com" not in joined
    assert "Python" in joined


def pytest_approx(v):
    import pytest
    return pytest.approx(v, abs=0.02)


def test_partial_failure_keeps_valid_resumes(client):
    r = post(client, items=[
        ("good.docx", make_docx(PYTHON_RESUME)),
        ("scan.pdf", make_blank_pdf()),
        ("notes.txt", b"plain text file with enough characters inside"),
        ("broken.docx", b"PK\x03\x04 garbage"),
        ("fake.pdf", b"MZ not a pdf"),
    ])
    body = r.json()
    assert r.status_code == 200
    assert [c["filename"] for c in body["candidates"]] == ["good.docx"]
    codes = {e["filename"]: e["code"] for e in body["errors"]}
    assert codes == {"scan.pdf": "no_extractable_text", "notes.txt": "unsupported_file_type",
                     "broken.docx": "corrupted_file", "fake.pdf": "file_type_mismatch"}
    assert body["summary"]["total_uploaded"] == 5 and body["summary"]["failed"] == 4
    assert [e["upload_index"] for e in body["errors"]] == [1, 2, 3, 4]


def test_all_files_invalid_returns_errors_not_crash(client):
    body = post(client, items=[("a.pdf", make_blank_pdf())]).json()
    assert body["candidates"] == [] and body["summary"]["average_score"] is None and len(body["errors"]) == 1


def test_oversized_upload_is_per_file_error(client):
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
    body = post(client, items=[("big.pdf", big), ("ok.docx", make_docx(PYTHON_RESUME))]).json()
    assert [e["code"] for e in body["errors"]] == ["file_too_large"]
    assert len(body["candidates"]) == 1


def test_no_skills_job_relies_on_semantic(client):
    body = post(client, form(required_skills="", preferred_skills=""), [("p.pdf", make_pdf(PYTHON_RESUME))]).json()
    c = body["candidates"][0]
    assert c["score"] == pytest_approx(c["semantic_score"])
    assert "relies entirely on semantic similarity" in c["score_breakdown"]["notes"][0]
    assert c["required_matched"] == [] and c["required_not_found"] == []


def test_experience_reported_separately_and_not_scored(client):
    c = post(client, form(min_experience_years="5"), [("p.pdf", make_pdf(PYTHON_RESUME))]).json()["candidates"][0]
    assert c["experience"]["status"] == "mentions_found" and c["experience"]["max_stated_years"] == 6
    c2 = post(client, form(min_experience_years="5"), [("j.docx", make_docx(JAVA_RESUME))]).json()["candidates"][0]
    assert c2["experience"]["status"] == "no_explicit_mention" and c2["experience"]["max_stated_years"] is None
    c3 = post(client, form(), [("p.pdf", make_pdf(PYTHON_RESUME))]).json()["candidates"][0]
    assert c3["experience"]["status"] == "not_requested"
    assert c["score"] == c3["score"]  # experience does not change the score


def test_validation_errors_are_consistent(client):
    r = post(client, form(job_description="   "), [("p.pdf", make_pdf(PYTHON_RESUME))])
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_job"
    assert "Job description is required" in r.json()["error"]["message"]
    assert post(client, form(job_title=""), [("p.pdf", make_pdf(PYTHON_RESUME))]).status_code == 422
    assert post(client, form(job_description="too short"), [("p.pdf", make_pdf(PYTHON_RESUME))]).json()["error"]["code"] == "job_description_too_short"
    assert post(client, items=[]).json()["error"]["code"] == "no_files"
    assert post(client, form(min_experience_years="-3"), [("p.pdf", make_pdf(PYTHON_RESUME))]).status_code == 422


def test_too_many_files(client):
    items = [(f"r{i}.docx", make_docx(PYTHON_RESUME)) for i in range(6)]
    r = post(client, items=items)
    assert r.status_code == 422 and r.json()["error"]["code"] == "too_many_files"


def test_model_failure_returns_503_not_fake_scores(settings):
    app = create_app(settings, SemanticMatcher(FakeBackend(fail_load=True)))
    with TestClient(app) as c:
        r = post(c, items=[("p.pdf", make_pdf(PYTHON_RESUME))])
        assert r.status_code == 503 and r.json()["error"]["code"] == "model_unavailable"
        assert "secret" not in r.text and "candidates" not in r.json()


def test_model_recovers_after_failed_startup(settings):
    backend = FakeBackend(fail_load=True)
    app = create_app(settings, SemanticMatcher(backend))
    with TestClient(app) as c:
        assert post(c, items=[("p.pdf", make_pdf(PYTHON_RESUME))]).status_code == 503
        backend.fail_load = False  # e.g. model files were downloaded meanwhile
        assert post(c, items=[("p.pdf", make_pdf(PYTHON_RESUME))]).status_code == 200


def test_unhandled_errors_hide_stack_traces(settings, monkeypatch):
    app = create_app(settings, SemanticMatcher(FakeBackend()))
    def boom(*a, **k):
        raise RuntimeError("internal /secret/path detail")
    monkeypatch.setattr(app.state.services.matching_service, "run", boom)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = post(c, items=[("p.pdf", make_pdf(PYTHON_RESUME))])
        assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
        assert "secret" not in r.text and "Traceback" not in r.text


def test_uploads_are_not_persisted(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    post(client, items=[("p.pdf", make_pdf(PYTHON_RESUME))])
    assert list(tmp_path.iterdir()) == []


def test_filename_path_traversal_is_neutralised(client):
    c = post(client, items=[("../../evil.docx", make_docx(PYTHON_RESUME))]).json()["candidates"][0]
    assert c["filename"] == "evil.docx"


def test_csv_export_endpoint(client):
    body = post(client, items=[("=bad.docx", make_docx(PYTHON_RESUME)), ("n.txt", b"x" * 40)]).json()
    r = client.post("/api/v1/export/csv", json={"candidates": body["candidates"], "errors": body["errors"]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[1][2] == "'=bad.docx" and rows[1][-1] == "processed"
    assert rows[2][-1] == "failed: unsupported_file_type"
    assert client.post("/api/v1/export/csv", json={"candidates": "nope"}).status_code == 422


def test_cors_allows_frontend_origin(client):
    r = client.options("/api/v1/match", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    r = client.options("/api/v1/match", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers
