"""Opt-in smoke test with the real pretrained model.

Run after the model files are available (first run downloads ~90 MB):

    pytest -m integration -s
"""
import pytest

from app.services.semantic_matcher import SemanticMatcher, SentenceTransformerBackend

pytestmark = pytest.mark.integration


def test_real_model_ranks_related_text_higher():
    pytest.importorskip("sentence_transformers")
    matcher = SemanticMatcher(SentenceTransformerBackend("sentence-transformers/all-MiniLM-L6-v2"))
    matcher.load()
    job = "Machine learning engineer building Python APIs and deploying models with Docker and Kubernetes."
    related = "I deploy machine learning models as Python REST services packaged in Docker containers on Kubernetes."
    unrelated = "Experienced pastry chef specialising in sourdough bread, croissants and wedding cakes."
    s_related, s_unrelated = matcher.calculate_semantic_similarity(job, [related, unrelated])
    assert matcher.is_ready
    assert -1 <= s_unrelated < s_related <= 1
    assert s_related - s_unrelated > 0.2
