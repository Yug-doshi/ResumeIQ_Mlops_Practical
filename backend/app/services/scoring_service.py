"""Explainable composite score.

final = sum(effective_weight_i * component_score_i) * 100

Components: required-skill coverage, preferred-skill coverage, semantic
similarity. Components that cannot be computed (no required / no preferred
skills specified) are excluded and their weight is redistributed
proportionally, which is stated in the breakdown notes. The result is an
estimate of similarity to the job description, not a probability of hiring
success.
"""
from __future__ import annotations

from app.config import ScoringConfig
from app.schemas import ScoreBreakdown, ScoreComponent


def normalize_semantic(cosine: float, floor: float, ceiling: float) -> float:
    """Map a cosine similarity to [0, 1] using the configured floor/ceiling."""
    value = (cosine - floor) / (ceiling - floor)
    return max(0.0, min(1.0, value))


def _coverage(matched: int, total: int) -> float | None:
    if total <= 0:
        return None
    return max(0.0, min(1.0, matched / total))


def compute_score(
    *,
    required_total: int,
    required_matched: int,
    preferred_total: int,
    preferred_matched: int,
    semantic_cosine: float,
    config: ScoringConfig,
) -> ScoreBreakdown:
    w = config.weights
    required = _coverage(required_matched, required_total)
    preferred = _coverage(preferred_matched, preferred_total)
    semantic = normalize_semantic(semantic_cosine, config.semantic.floor, config.semantic.ceiling)

    raw = [
        ("required_skills", "Required-skill coverage", required, w.required_skills,
         f"{required_matched} of {required_total} required skills found in resume" if required is not None
         else "No required skills specified"),
        ("preferred_skills", "Preferred-skill coverage", preferred, w.preferred_skills,
         f"{preferred_matched} of {preferred_total} preferred skills found in resume" if preferred is not None
         else "No preferred skills specified"),
        ("semantic_similarity", "Semantic similarity", semantic, w.semantic_similarity,
         "Embedding similarity between the resume text and the job description"),
    ]
    available_weight = sum(weight for _, _, score, weight, _ in raw if score is not None)
    # semantic is always available and its weight is validated > 0, so this is > 0.

    components: list[ScoreComponent] = []
    final = 0.0
    for key, label, score, weight, detail in raw:
        if score is None:
            components.append(
                ScoreComponent(key=key, label=label, score=None, configured_weight=weight,
                               effective_weight=0.0, contribution=0.0, available=False, detail=detail)
            )
            continue
        effective = weight / available_weight
        contribution = effective * score * 100
        final += contribution
        components.append(
            ScoreComponent(key=key, label=label, score=round(score * 100, 2), configured_weight=weight,
                           effective_weight=round(effective, 4), contribution=round(contribution, 2),
                           available=True, detail=detail)
        )

    notes: list[str] = []
    if required is None and preferred is None:
        notes.append(
            "No required or preferred skills were specified, so this score relies entirely on "
            "semantic similarity to the job description."
        )
    elif required is None:
        notes.append("No required skills were specified; their weight was redistributed to the other components.")
    elif preferred is None:
        notes.append("No preferred skills were specified; their weight was redistributed to the other components.")

    return ScoreBreakdown(
        final_score=round(max(0.0, min(100.0, final)), 2),
        components=components,
        notes=notes,
        scoring_version=config.version,
    )
