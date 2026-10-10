import pytest

from app.exceptions import ModelUnavailableError
from app.services.semantic_matcher import SemanticMatcher, chunk_words
from tests.conftest import FakeBackend


def test_one_score_per_resume_in_order():
    m = SemanticMatcher(FakeBackend())
    scores = m.calculate_semantic_similarity("python docker kubernetes", [
        "python docker kubernetes", "cooking baking recipes", "python"])
    assert len(scores) == 3
    assert scores[0] == pytest.approx(1.0) and scores[0] > scores[2] > scores[1]


def test_model_loads_once():
    backend = FakeBackend()
    m = SemanticMatcher(backend)
    m.calculate_semantic_similarity("a b c", ["a b"])
    m.calculate_semantic_similarity("a b c", ["c"])
    assert backend.load_calls == 1 and m.is_ready


def test_load_failure_raises_and_is_not_faked():
    m = SemanticMatcher(FakeBackend(fail_load=True))
    with pytest.raises(ModelUnavailableError) as exc:
        m.calculate_semantic_similarity("job", ["resume"])
    assert exc.value.status_code == 503
    assert m.status == "failed" and not m.is_ready
    assert "secret" not in exc.value.message


def test_empty_inputs():
    m = SemanticMatcher(FakeBackend())
    assert m.calculate_semantic_similarity("job text", []) == []
    with pytest.raises(ValueError):
        m.calculate_semantic_similarity("  ", ["x"])


def test_long_text_is_chunked_not_truncated():
    assert len(chunk_words("w " * 1000, 180, 30)) == 6
    assert len(chunk_words("w " * 100000, 180, 30)) == 30
