"""Port of tool_db2 tests/employees.test.js with the tooldb-py deltas:

- All management routes are admin-only (403 for logged-in non-admins).
- Responses include isAdmin wherever employees appear.
- Lookup responses are {badgeId, name, isAdmin}.
- PATCH accepts active and/or isAdmin, with a last-admin guard (409).

Conftest seeds ADMIN (bootstrap), E100 'Admin User' (admin) and
E200 'Regular User' (non-admin).
"""


def test_lists_employees_with_roles(admin_client):
    res = admin_client.get("/api/employees")
    assert res.status_code == 200
    assert res.json() == [
        {"badgeId": "ADMIN", "name": "Administrator", "active": 1, "isAdmin": True},
        {"badgeId": "E100", "name": "Admin User", "active": 1, "isAdmin": True},
        {"badgeId": "E200", "name": "Regular User", "active": 1, "isAdmin": False},
    ]


def test_management_routes_reject_non_admins(user_client, anon_client):
    assert user_client.get("/api/employees").status_code == 403
    assert user_client.post("/api/employees", json={"badgeId": "E300", "name": "X"}).status_code == 403
    assert user_client.post("/api/employees/import", json={"rows": []}).status_code == 403
    assert user_client.patch("/api/employees/E200", json={"active": False}).status_code == 403
    # unauthenticated callers get 401 from the same guard
    assert anon_client.get("/api/employees").status_code == 401


def test_creates_an_employee(admin_client, conn):
    res = admin_client.post("/api/employees", json={"badgeId": "E300", "name": "New Person"})
    assert res.status_code == 201
    assert res.json() == {"badgeId": "E300", "name": "New Person", "active": 1, "isAdmin": False}
    assert conn.execute("SELECT name FROM employees WHERE badge_id='E300'").fetchone()["name"] == "New Person"


def test_rejects_duplicate_badge_and_missing_name(admin_client):
    assert admin_client.post("/api/employees", json={"badgeId": "E100", "name": "X"}).status_code == 409
    assert admin_client.post("/api/employees", json={"badgeId": "E301", "name": ""}).status_code == 400


def test_imports_rows_upserting_new_badges(admin_client, conn):
    res = admin_client.post("/api/employees/import", json={"rows": [
        {"badgeId": "E400", "name": "Ann"}, {"badgeId": "E401", "name": "Bob"},
        {"badgeId": "E100", "name": "Admin User"},
    ]})
    assert res.status_code == 200
    assert res.json() == {"imported": 2, "skipped": 1}
    # 3 pre-seeded (ADMIN bootstrap + E100 + E200) + 2 imported
    assert conn.execute("SELECT COUNT(*) c FROM employees").fetchone()["c"] == 5


def test_import_renames_and_reactivates_same_badge_new_name(admin_client, conn):
    conn.execute("UPDATE employees SET active=0 WHERE badge_id='E200'")
    conn.commit()
    res = admin_client.post("/api/employees/import", json={"rows": [
        {"badgeId": "E200", "name": "Renamed User"},   # same badge, new name -> rename+reactivate
        {"badgeId": "E100", "name": "Admin User"},     # identical -> skipped
        {"badgeId": "", "name": "No Badge"},           # invalid -> skipped
        {"badgeId": "E402", "name": "  "},             # whitespace name -> skipped
        None,                                          # not an object -> skipped
    ]})
    assert res.json() == {"imported": 1, "skipped": 4}
    row = conn.execute("SELECT name, active FROM employees WHERE badge_id='E200'").fetchone()
    assert row["name"] == "Renamed User" and row["active"] == 1
    assert conn.execute("SELECT active FROM employees WHERE badge_id='E100'").fetchone()["active"] == 1


def test_deactivates_and_reactivates(admin_client, conn):
    res = admin_client.patch("/api/employees/E200", json={"active": 0})
    assert res.status_code == 200
    assert conn.execute("SELECT active FROM employees WHERE badge_id='E200'").fetchone()["active"] == 0
    res = admin_client.patch("/api/employees/E200", json={"active": 1})
    assert res.status_code == 200
    assert conn.execute("SELECT active FROM employees WHERE badge_id='E200'").fetchone()["active"] == 1


def test_public_lookup_returns_active_employees_with_roles(anon_client, conn):
    conn.execute("UPDATE employees SET active=0 WHERE badge_id='E200'")
    conn.commit()
    res = anon_client.get("/api/employee-lookup", params={"q": "Regular"})
    assert res.status_code == 200
    assert res.json() == []
    res2 = anon_client.get("/api/employee-lookup", params={"q": "Admin User"})
    assert res2.status_code == 200
    # "Admin" alone would also match the ADMIN bootstrap row; the full name only fits E100
    assert res2.json() == [{"badgeId": "E100", "name": "Admin User", "isAdmin": True}]
    assert set(res2.json()[0].keys()) == {"badgeId", "name", "isAdmin"}


def test_public_lookup_caps_at_five(anon_client, conn):
    for i in range(1, 7):
        conn.execute("INSERT INTO employees (badge_id, name) VALUES (?, ?)", (f"X{i}", f"Extra Person {i}"))
    conn.commit()
    res = anon_client.get("/api/employee-lookup", params={"q": "Extra"})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 5
    for row in body:
        assert set(row.keys()) == {"badgeId", "name", "isAdmin"}


def test_public_lookup_rejects_short_and_empty_queries(anon_client):
    assert anon_client.get("/api/employee-lookup", params={"q": "E"}).json() == []
    assert anon_client.get("/api/employee-lookup", params={"q": " "}).json() == []
    assert anon_client.get("/api/employee-lookup").json() == []


def test_public_lookup_treats_percent_as_literal(anon_client, conn):
    conn.execute("INSERT INTO employees (badge_id, name) VALUES ('E10', 'Wilder One')")
    conn.execute("INSERT INTO employees (badge_id, name) VALUES ('E11', 'Wilder Two')")
    conn.execute("INSERT INTO employees (badge_id, name) VALUES ('E1%', 'Literal Percent')")
    conn.commit()
    # as a wildcard, 'E1%' would match E10 and E11 too; literally it only matches E1%
    res = anon_client.get("/api/employee-lookup", params={"q": "E1%"})
    assert res.status_code == 200
    assert res.json() == [{"badgeId": "E1%", "name": "Literal Percent", "isAdmin": False}]


def test_employee_list_treats_percent_as_literal(admin_client, conn):
    conn.execute("INSERT INTO employees (badge_id, name) VALUES ('E10', 'Wilder One')")
    conn.commit()
    # '%' unescaped would match every row; literally it matches nothing
    assert admin_client.get("/api/employees", params={"q": "%"}).json() == []
    res2 = admin_client.get("/api/employees", params={"q": "Wilder"})
    assert res2.json() == [{"badgeId": "E10", "name": "Wilder One", "active": 1, "isAdmin": False}]


def test_patch_type_validation(admin_client, conn):
    assert admin_client.patch("/api/employees/E200", json={}).status_code == 400
    assert admin_client.patch("/api/employees/E200", json={"active": "false"}).status_code == 400
    assert admin_client.patch("/api/employees/E200", json={"isAdmin": "yes"}).status_code == 400
    row = conn.execute("SELECT active, is_admin FROM employees WHERE badge_id='E200'").fetchone()
    assert row["active"] == 1 and row["is_admin"] == 0
    # 1/0 accepted alongside true/false, per field
    assert admin_client.patch("/api/employees/E200", json={"active": 0}).status_code == 200


def test_patch_unknown_badge_is_404_after_body_validation(admin_client):
    assert admin_client.patch("/api/employees/NOPE", json={"active": False}).status_code == 404
    # invalid body is rejected before the 404, matching the Node ordering
    assert admin_client.patch("/api/employees/NOPE", json={"active": "nope"}).status_code == 400


def test_promote_and_demote(admin_client, user_client, conn):
    res = admin_client.patch("/api/employees/E200", json={"isAdmin": True})
    assert res.status_code == 200 and res.json()["isAdmin"] is True
    assert conn.execute("SELECT is_admin FROM employees WHERE badge_id='E200'").fetchone()[0] == 1
    res = admin_client.patch("/api/employees/E200", json={"isAdmin": False})
    assert res.status_code == 200 and res.json()["isAdmin"] is False


def test_last_admin_guard(admin_client, conn):
    # conftest seeds the ADMIN bootstrap account; make E100 the only *active* admin
    conn.execute("UPDATE employees SET active=0 WHERE badge_id='ADMIN'")
    conn.commit()
    assert admin_client.patch("/api/employees/E100", json={"isAdmin": False}).status_code == 409
    assert admin_client.patch("/api/employees/E100", json={"active": False}).status_code == 409
    assert admin_client.patch("/api/employees/E100",
                              json={"isAdmin": False, "active": False}).status_code == 409
    assert conn.execute("SELECT is_admin, active FROM employees WHERE badge_id='E100'").fetchone()[:2] == (1, 1)
    # with a second active admin, demotion works
    conn.execute("INSERT INTO employees (badge_id, name, active, is_admin) VALUES ('E900', 'Second', 1, 1)")
    conn.commit()
    assert admin_client.patch("/api/employees/E100", json={"isAdmin": False}).status_code == 200


def test_mutations_are_audited(admin_client, conn):
    admin_client.post("/api/employees", json={"badgeId": "E300", "name": "New Person"})
    admin_client.post("/api/employees/import", json={"rows": [{"badgeId": "E400", "name": "Ann"}]})
    admin_client.patch("/api/employees/E200", json={"active": 0, "isAdmin": True})
    rows = conn.execute(
        "SELECT badge_id, action, entity, entity_id, details FROM activity_log "
        "WHERE action IN ('create','import','update') ORDER BY id").fetchall()
    assert [(r["action"], r["entity"], r["entity_id"], r["details"]) for r in rows] == [
        ("create", "employee", "E300", "name: New Person"),
        ("import", "employee", "", "1 imported, 0 skipped"),
        ("update", "employee", "E200", "active: 0, isAdmin: 1"),
    ]
    assert rows[0]["badge_id"] == "E100"  # acting admin, from the session
