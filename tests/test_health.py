def test_health(admin_client):
    res = admin_client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
