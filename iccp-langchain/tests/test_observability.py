def test_observability_status(client):
    resp = client.get("/api/v1/observability/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "langsmith" in data
    assert "enabled" in data["langsmith"]
