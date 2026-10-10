from fastapi.testclient import TestClient

from app.main import create_app
from app.services.semantic_matcher import SemanticMatcher
from tests.conftest import FakeBackend


def test_health_ready(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["live"] is True and body["ready"] is True
    assert body["model"]["status"] == "ready"
    assert body["version"] and body["api_version"] == "v1"
    assert "path" not in str(body).lower()


def test_health_alive_but_not_ready_when_model_fails(settings):
    app = create_app(settings, SemanticMatcher(FakeBackend(fail_load=True)))
    with TestClient(app) as c:
        health = c.get("/health")
        assert health.status_code == 200  # liveness unaffected
        assert health.json()["ready"] is False
        assert health.json()["model"]["status"] == "failed"
        assert "secret" not in health.text  # internal details are not exposed
        assert c.get("/health/ready").status_code == 503


def test_model_info_config_version(client):
    info = client.get("/api/v1/model-info").json()
    assert info["ready"] is True and info["model_id"] == "fake/bag-of-words"
    assert info["scoring_config_version"]
    assert "mlflow" not in str(info).lower()
    cfg = client.get("/api/v1/config").json()
    assert cfg["scoring_weights"]["required_skills"] == 0.5
    assert cfg["supported_extensions"] == [".docx", ".pdf"]
    ver = client.get("/api/v1/version").json()
    assert ver["api_version"] == "v1"
