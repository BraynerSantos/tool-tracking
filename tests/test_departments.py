"""Port of tool_db2 tests/departments.test.js with the tooldb-py deltas:

- Reads (GET /api/departments) are open to any logged-in user.
- Writes are admin-only (403 for logged-in non-admins, 401 anonymous).
- PATCH duplicate checks exclude the entity being renamed (409 collision).
- In-use delete guards: departments with locations -> 409, locations holding
  inventory -> 409.

Conftest seeds E100 'Admin User' (admin) and E200 'Regular User' (non-admin).
"""


def test_creates_department_and_location_lists_nested(admin_client, make_location):
    make_location("Milling", "Cabinet 3")
    res = admin_client.get("/api/departments")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["name"] == "Milling"
    assert len(body[0]["locations"]) == 1
    loc = body[0]["locations"][0]
    assert loc["name"] == "Cabinet 3"
    assert loc["departmentId"] == body[0]["id"]


def test_rejects_duplicate_department_and_duplicate_location_in_same_department(
        admin_client, make_location):
    make_location("Milling", "Cabinet 3")
    assert admin_client.post("/api/departments", json={"name": "Milling"}).status_code == 409
    d = admin_client.get("/api/departments").json()[0]
    assert admin_client.post(
        "/api/locations", json={"departmentId": d["id"], "name": "Cabinet 3"}).status_code == 409
    # same name in a different department is fine
    other = admin_client.post("/api/departments", json={"name": "Turning"}).json()
    assert admin_client.post(
        "/api/locations", json={"departmentId": other["id"], "name": "Cabinet 3"}).status_code == 201


def test_renames_department_and_location(admin_client, make_location):
    ids = make_location("Milling", "Cabinet 3")
    assert admin_client.patch(
        f"/api/departments/{ids['departmentId']}", json={"name": "Milling Dept"}).status_code == 200
    assert admin_client.patch(
        f"/api/locations/{ids['locationId']}", json={"name": "Cabinet 4"}).status_code == 200
    d = admin_client.get("/api/departments").json()[0]
    assert d["name"] == "Milling Dept"
    assert d["locations"][0]["name"] == "Cabinet 4"


def test_blocks_deleting_a_location_in_use(admin_client, conn, make_location):
    ids = make_location("Milling", "Cabinet 3")
    type_id = conn.execute("SELECT id FROM tool_types LIMIT 1").fetchone()["id"]
    cur = conn.execute("INSERT INTO tools (name, tool_type_id) VALUES (?, ?)",
                       ("6mm end mill", type_id))
    conn.commit()
    conn.execute("INSERT INTO inventory (tool_id, location_id, quantity) VALUES (?, ?, 5)",
                 (cur.lastrowid, ids["locationId"]))
    conn.commit()
    res = admin_client.delete(f"/api/locations/{ids['locationId']}")
    assert res.status_code == 409
    assert res.json()["error"] == "Location holds inventory; empty it first"


def test_blocks_deleting_a_department_that_has_locations(admin_client, make_location):
    ids = make_location("Milling", "Cabinet 3")
    res = admin_client.delete(f"/api/departments/{ids['departmentId']}")
    assert res.status_code == 409
    assert res.json()["error"] == "Department has locations; move or delete them first"


def test_rejects_renaming_department_onto_existing_name(admin_client, make_location):
    a = make_location("Milling", "Cabinet 3")
    make_location("Turning", "Cabinet 1")
    res = admin_client.patch(f"/api/departments/{a['departmentId']}", json={"name": "Turning"})
    assert res.status_code == 409
    assert res.json()["error"] == "Department already exists"


def test_rename_department_to_own_name_is_allowed(admin_client, make_location):
    ids = make_location("Milling", "Cabinet 3")
    res = admin_client.patch(f"/api/departments/{ids['departmentId']}", json={"name": "Milling"})
    assert res.status_code == 200
    assert res.json() == {"id": ids["departmentId"], "name": "Milling"}


def test_rejects_renaming_location_onto_sibling_name(admin_client, make_location):
    ids = make_location("Milling", "Cabinet 3")
    assert admin_client.post(
        "/api/locations",
        json={"departmentId": ids["departmentId"], "name": "Cabinet 4"}).status_code == 201
    res = admin_client.patch(f"/api/locations/{ids['locationId']}", json={"name": "Cabinet 4"})
    assert res.status_code == 409
    assert res.json()["error"] == "Location already exists in this department"


def test_deletes_an_unused_location(admin_client, conn, make_location):
    ids = make_location("Milling", "Cabinet 3")
    res = admin_client.delete(f"/api/locations/{ids['locationId']}")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert conn.execute("SELECT 1 FROM locations WHERE id=?",
                        (ids["locationId"],)).fetchone() is None


def test_deletes_an_unused_department(admin_client, conn, make_location):
    ids = make_location("Milling", "Cabinet 3")
    assert admin_client.delete(f"/api/locations/{ids['locationId']}").status_code == 200
    res = admin_client.delete(f"/api/departments/{ids['departmentId']}")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert conn.execute("SELECT 1 FROM departments WHERE id=?",
                        (ids["departmentId"],)).fetchone() is None


def test_validation_errors(admin_client):
    assert admin_client.post("/api/departments", json={"name": ""}).status_code == 400
    assert admin_client.post("/api/departments", json={}).status_code == 400
    assert admin_client.post("/api/locations", json={"name": "X"}).status_code == 400
    assert admin_client.post(
        "/api/locations", json={"departmentId": 999, "name": "X"}).status_code == 404
    assert admin_client.patch("/api/departments/999", json={"name": "X"}).status_code == 404
    assert admin_client.patch("/api/locations/999", json={"name": "X"}).status_code == 404
    assert admin_client.delete("/api/departments/999").status_code == 200
    assert admin_client.delete("/api/locations/999").status_code == 200


def test_reads_open_writes_admin(admin_client, user_client):
    assert user_client.get("/api/departments").status_code == 200
    assert user_client.post("/api/departments", json={"name": "X"}).status_code == 403
    assert user_client.delete("/api/departments/1").status_code == 403
    d = admin_client.post("/api/departments", json={"name": "Milling"})
    assert d.status_code == 201


def test_writes_require_login(anon_client):
    assert anon_client.get("/api/departments").status_code == 401
    assert anon_client.post("/api/departments", json={"name": "X"}).status_code == 401


def test_audit_log_records_department_and_location_actions(admin_client, conn, make_location):
    ids = make_location("Milling", "Cabinet 3")
    admin_client.patch(f"/api/locations/{ids['locationId']}", json={"name": "Cabinet 4"})
    admin_client.delete(f"/api/locations/{ids['locationId']}")
    rows = conn.execute(
        "SELECT action, entity FROM activity_log WHERE entity IN ('department', 'location') "
        "ORDER BY id").fetchall()
    assert [(r["action"], r["entity"]) for r in rows] == [
        ("create", "department"), ("create", "location"),
        ("update", "location"), ("delete", "location")]
