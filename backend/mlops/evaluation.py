"""Ranking evaluation metrics for ResumeIQ."""

import math
from collections.abc import Sequence


def precision_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int = 5) -> float:
    """Fraction of the top-k results that are relevant."""
    if k < 1:
        raise ValueError("k must be >= 1")
    top_k = list(ranked_ids[:k])
    if not top_k:
        return 0.0
    return sum(item in relevant_ids for item in top_k) / len(top_k)


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], k: int = 5) -> float:
    """Fraction of all known relevant items found in the top-k results."""
    if k < 1:
        raise ValueError("k must be >= 1")
    if not relevant_ids:
        return 0.0
    return len(set(ranked_ids[:k]) & relevant_ids) / len(relevant_ids)


def reciprocal_rank(ranked_ids: Sequence[str], relevant_ids: set[str]) -> float:
    """Reciprocal rank of the first relevant result."""
    for position, item in enumerate(ranked_ids, start=1):
        if item in relevant_ids:
            return 1.0 / position
    return 0.0


def ndcg_at_k(
    ranked_ids: Sequence[str],
    relevance_grades: dict[str, int],
    k: int = 5,
) -> float:
    """Normalized discounted cumulative gain using graded relevance."""
    if k < 1:
        raise ValueError("k must be >= 1")

    def gain(item: str) -> float:
        grade = relevance_grades.get(item, 0)
        return (2**grade - 1) / math.log2(position + 1)

    dcg = sum(
        (2 ** relevance_grades.get(item, 0) - 1) / math.log2(position + 1)
        for position, item in enumerate(ranked_ids[:k], start=1)
    )
    ideal_grades = sorted(relevance_grades.values(), reverse=True)[:k]
    ideal_dcg = sum(
        (2**grade - 1) / math.log2(position + 1)
        for position, grade in enumerate(ideal_grades, start=1)
    )
    return dcg / ideal_dcg if ideal_dcg else 0.0


def evaluate_ranking(
    ranked_ids: Sequence[str],
    relevance_grades: dict[str, int],
    k: int = 5,
) -> dict[str, float]:
    """Calculate ranking metrics against human-assigned relevance grades.

    Grades: 0 = not relevant, 1 = partially relevant, 2 = relevant.
    """
    relevant_ids = {
        item for item, grade in relevance_grades.items() if grade >= 2
    }
    return {
        f"precision_at_{k}": precision_at_k(ranked_ids, relevant_ids, k),
        f"recall_at_{k}": recall_at_k(ranked_ids, relevant_ids, k),
        "mrr": reciprocal_rank(ranked_ids, relevant_ids),
        f"ndcg_at_{k}": ndcg_at_k(ranked_ids, relevance_grades, k),
    }
