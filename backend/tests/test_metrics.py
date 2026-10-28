def test_metrics_expose_request_count_and_duration(client):
    client.get("/health")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'resumeiq_http_requests_total{method="GET",route="/health",status="200"} 1.0' in response.text
    assert 'resumeiq_http_request_duration_seconds_count{method="GET",route="/health"} 1.0' in response.text
    assert 'route="/metrics"' not in response.text
