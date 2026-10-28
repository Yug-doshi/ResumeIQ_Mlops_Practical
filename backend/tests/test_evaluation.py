from mlops.evaluation import evaluate_ranking


def test_evaluation_metrics_known_example():
    ranked = ["candidate_a", "candidate_b", "candidate_c", "candidate_d"]
    grades = {
        "candidate_a": 0,
        "candidate_b": 2,
        "candidate_c": 1,
        "candidate_d": 2,
    }

    metrics = evaluate_ranking(ranked, grades, k=3)

    assert metrics["precision_at_3"] == 1 / 3
    assert metrics["recall_at_3"] == 0.5
    assert metrics["mrr"] == 0.5
    assert 0 <= metrics["ndcg_at_3"] <= 1


def test_evaluation_handles_zero_relevance():
    metrics = evaluate_ranking(
        ["candidate_a", "candidate_b"],
        {"candidate_a": 0, "candidate_b": 0},
        k=2,
    )

    assert metrics["precision_at_2"] == 0
    assert metrics["recall_at_2"] == 0
    assert metrics["mrr"] == 0
    assert metrics["ndcg_at_2"] == 0
