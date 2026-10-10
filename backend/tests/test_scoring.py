import pytest

from app.config import BACKEND_DIR, ScoringConfig, load_scoring_config
from app.services.scoring_service import compute_score, normalize_semantic


@pytest.fixture(scope="module")
def cfg():
    return load_scoring_config(BACKEND_DIR / "config" / "scoring.json")


def score(cfg, **kw):
    base = dict(required_total=4, required_matched=4, preferred_total=2, preferred_matched=2, semantic_cosine=1.0)
    base.update(kw)
    return compute_score(config=cfg, **base)


def test_weights_from_config(cfg):
    assert (cfg.weights.required_skills, cfg.weights.semantic_similarity, cfg.weights.preferred_skills) == (0.5, 0.35, 0.15)


def test_perfect_and_zero(cfg):
    assert score(cfg).final_score == 100
    assert score(cfg, required_matched=0, preferred_matched=0, semantic_cosine=0.0).final_score == 0


def test_known_value(cfg):
    # 0.5*(2/4) + 0.15*(1/2) + 0.35*0.6 = 0.25 + 0.075 + 0.21 = 0.535
    s = score(cfg, required_matched=2, preferred_matched=1, semantic_cosine=0.6)
    assert s.final_score == pytest.approx(53.5, abs=0.01)
    assert sum(c.contribution for c in s.components) == pytest.approx(s.final_score, abs=0.02)


def test_missing_required_skills_lowers_score(cfg):
    assert score(cfg, required_matched=1).final_score < score(cfg, required_matched=4).final_score


@pytest.mark.parametrize("cos", [-0.5, 0.0, 0.3, 1.0, 2.0])
def test_score_range(cfg, cos):
    assert 0 <= score(cfg, semantic_cosine=cos).final_score <= 100


def test_no_skills_uses_semantic_only_and_explains(cfg):
    s = score(cfg, required_total=0, required_matched=0, preferred_total=0, preferred_matched=0, semantic_cosine=0.42)
    assert s.final_score == pytest.approx(42.0)
    assert [c.available for c in s.components] == [False, False, True]
    assert "relies entirely on semantic similarity" in s.notes[0]


def test_missing_preferred_redistributes_weight(cfg):
    s = score(cfg, preferred_total=0, preferred_matched=0, required_matched=4, semantic_cosine=0.0)
    assert s.final_score == pytest.approx(100 * 0.5 / 0.85, abs=0.01)
    assert any("preferred" in n for n in s.notes)


def test_normalize_semantic_clamps():
    assert normalize_semantic(-1, 0, 1) == 0 and normalize_semantic(5, 0, 1) == 1
    assert normalize_semantic(0.5, 0.2, 0.8) == pytest.approx(0.5)


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        ScoringConfig.model_validate({"version": "x", "weights": {"required_skills": 1, "preferred_skills": 0, "semantic_similarity": 0}})
