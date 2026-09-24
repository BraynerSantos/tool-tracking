"""Port of tool_db2 tests/toolTypes.test.js with the tooldb-py deltas:

- Reads (GET /api/tool-types) are open to any logged-in user.
- Writes are admin-only (403 for logged-in non-admins, 401 anonymous).
- POST with the ``attributeSchema`` key absent -> 400
  ``{"error": "attributeSchema is required"}`` (Node fix round).
- In-use delete guard: tools referencing the type -> 409.

Conftest seeds E100 'Admin User' (admin) and E200 'Regular User' (non-admin).
"""

SCHEMA = [
    {"key": "grit", "label": "Grit", "type": "number"},
    {"key": "profile", "label": "Profile", "type": "text"},
]


def test_lists_seeded_types_with_schemas(admin_client):
    body = admin_client.get("/api/tool-types").json()
    cutting = next(t for t in body if t["name"] == "Cutting tools")
    assert len(cutting["attributeSchema"]) > 0


def test_creates_a_type_with_schema(admin_client):
    res = admin_client.post("/api/tool-types",
                            json={"name": "Dressing diamonds", "attributeSchema": SCHEMA})
    assert res.status_code == 201
    assert res.json()["attributeSchema"] == SCHEMA


def test_rejects_invalid_schema_and_duplicate_name(admin_client):
    res = admin_client.post("/api/tool-types", json={
        "name": "X",
        "attributeSchema": [{"key": "", "label": "L", "type": "number"}]})
    assert res.status_code == 400
    res = admin_client.post("/api/tool-types", json={
        "name": "X",
        "attributeSchema": [{"key": "a", "label": "A", "type": "number"},
                            {"key": "a", "label": "A2", "type": "text"}]})
    assert res.status_code == 400
    res = admin_client.post("/api/tool-types",
                            json={"name": "Cutting tools", "attributeSchema": []})
    assert res.status_code == 409
    res = admin_client.post("/api/tool-types", json={"name": "X"})
    assert res.status_code == 400
    assert res.json() == {"error": "attributeSchema is required"}


def test_blocks_renaming_a_type_onto_an_existing_name(admin_client):
    t = admin_client.post("/api/tool-types",
                          json={"name": "T1", "attributeSchema": SCHEMA}).json()
    res = admin_client.patch(f"/api/tool-types/{t['id']}", json={"name": "Cutting tools"})
    assert res.status_code == 409
    assert res.json()["error"] == "Tool type already exists"


def test_updates_schema(admin_client):
    t = admin_client.post("/api/tool-types",
                          json={"name": "T1", "attributeSchema": SCHEMA}).json()
    res = admin_client.patch(f"/api/tool-types/{t['id']}", json={
        "attributeSchema": SCHEMA + [{"key": "note", "label": "Note", "type": "text"}]})
    assert res.status_code == 200
    assert len(res.json()["attributeSchema"]) == 3


def test_blocks_delete_when_tools_exist(admin_client, conn):
    type_id = conn.execute("SELECT id FROM tool_types LIMIT 1").fetchone()["id"]
    conn.execute("INSERT INTO tools (name, tool_type_id) VALUES (?, ?)", ("t", type_id))
    conn.commit()
    res = admin_client.delete(f"/api/tool-types/{type_id}")
    assert res.status_code == 409
    assert res.json()["error"] == "Tools of this type exist; remove them first"


def test_reads_open_writes_admin(admin_client, user_client):
    assert user_client.get("/api/tool-types").status_code == 200
    assert user_client.post(
        "/api/tool-types", json={"name": "X", "attributeSchema": SCHEMA}).status_code == 403
    assert user_client.patch("/api/tool-types/1", json={"name": "Y"}).status_code == 403
    assert user_client.delete("/api/tool-types/1").status_code == 403
    assert admin_client.post(
        "/api/tool-types", json={"name": "Admin only", "attributeSchema": SCHEMA}).status_code == 201


def test_writes_require_login(anon_client):
    assert anon_client.get("/api/tool-types").status_code == 401
    assert anon_client.post(
        "/api/tool-types", json={"name": "X", "attributeSchema": SCHEMA}).status_code == 401


def test_audit_log_records_tool_type_actions(admin_client, conn):
    t = admin_client.post("/api/tool-types",
                          json={"name": "T1", "attributeSchema": SCHEMA}).json()
    admin_client.patch(f"/api/tool-types/{t['id']}", json={"name": "T2"})
    admin_client.delete(f"/api/tool-types/{t['id']}")
    rows = conn.execute(
        "SELECT action, entity FROM activity_log WHERE entity='tool_type' ORDER BY id"
    ).fetchall()
    assert [(r["action"], r["entity"]) for r in rows] == [
        ("create", "tool_type"), ("update", "tool_type"), ("delete", "tool_type")]
