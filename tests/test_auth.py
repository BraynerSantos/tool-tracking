def test_login_success_sets_session(admin_client):
    res = admin_client.post("/api/login", json={"badgeId": "E100"})
    assert res.status_code == 200
    assert res.json() == {"badgeId": "E100", "name": "Admin User", "isAdmin": True}


def test_login_rejects_unknown_and_inactive(anon_client, conn):
    assert anon_client.post("/api/login", json={"badgeId": "NOPE"}).status_code == 401
    conn.execute("UPDATE employees SET active=0 WHERE badge_id='E200'")
    conn.commit()
    res = anon_client.post("/api/login", json={"badgeId": "E200"})
    assert res.status_code == 401


def test_login_rejects_missing_badge(anon_client):
    res = anon_client.post("/api/login", json={})
    assert res.status_code == 401
    assert res.json() == {"error": "Unknown or inactive employee ID"}


def test_me_and_logout(admin_client, anon_client):
    me = admin_client.get("/api/me")
    assert me.status_code == 200
    assert me.json() == {"badgeId": "E100", "name": "Admin User", "isAdmin": True}
    admin_client.post("/api/logout")
    assert admin_client.get("/api/me").status_code == 401
    assert anon_client.get("/api/me").status_code == 401


def test_me_requires_login(anon_client):
    res = anon_client.get("/api/me")
    assert res.status_code == 401
    assert res.json() == {"error": "Not logged in"}
