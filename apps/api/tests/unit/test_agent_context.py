from app.services.agent_runs import MAX_CONTEXT_ANOMALIES, _strongest_anomalies


def test_model_context_keeps_only_the_strongest_anomalies() -> None:
    anomalies = [
        {"transaction_id": f"txn-{index}", "robust_score_milli": score}
        for index, score in enumerate([4_000, -9_000, 3_500, *range(100, 1_300, 100)])
    ]
    kept = _strongest_anomalies(anomalies)
    assert len(kept) == MAX_CONTEXT_ANOMALIES
    assert [item["transaction_id"] for item in kept[:3]] == ["txn-1", "txn-0", "txn-2"]
    assert _strongest_anomalies([{"transaction_id": "unscored"}]) == [
        {"transaction_id": "unscored"}
    ]
