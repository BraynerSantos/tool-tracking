"""Port of tool_db2 tests/tools.test.js (detail, edit, inventory, delete).

``make_tools`` is the 1:1 port of ``fixture()`` in tool_db2's
``tests/search.test.js``; the create/list/search endpoint tests that consume it
live in ``tests/test_search.py`` (Task 8).

Conftest seeds E100 'Admin User' (admin) and E200 'Regular User' (non-admin);
tool reads/writes are open to any logged-in user (no admin gate).
"""

import json

TYPE_NAME_IDS = ("Cutting tools", "Measuring tools")


def make_tools(admin_client, conn, make_location):
    types = admin_client.get("/api/tool-types").json()
    cutting = next(t for t in types if t["name"] == "Cutting tools")
    a = make_location("Milling", "Cabinet 3")
    b = make_location("QC", "Shelf 2")
    tool = admin_client.post("/api/tools", json={
        "name": "6mm end mill", "description": "carbide", "toolTypeId": cutting["id"],
        "attributes": {"diameter_mm": 6, "coating": "TiAlN"}, "reorderMin": 2,
        "inventory": [{"locationId": a["locationId"], "quantity": 12},
                      {"locationId": b["locationId"], "quantity": 4}]})
    assert tool.status_code == 201
    cal = admin_client.post("/api/tools", json={
        "name": "6in caliper",
        "toolTypeId": next(t["id"] for t in types if t["name"] == "Measuring tools"),
        "attributes": {"range": "0-150mm"},
        "inventory": [{"locationId": b["locationId"], "quantity": 1}]})
    assert cal.status_code == 201
    return {"toolId": tool.json()["id"], "cutting": cutting, "a": a, "b": b}


def test_returns_full_detail_with_inventory_and_history(admin_client, conn, make_location):
    f = make_tools(admin_client, conn, make_location)
    res = admin_client.get(f"/api/tools/{f['toolId']}")
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == f["toolId"]
    assert body["name"] == "6mm end mill"
    assert body["typeName"] == "Cutting tools"
    assert body["attributes"] == {"diameter_mm": 6, "coating": "TiAlN"}
    assert body["reorderMin"] == 2
    assert len(body["inventory"]) == 2
    assert {"locationId": f["a"]["locationId"], "locationName": "Cabinet 3",
            "departmentName": "Milling", "quantity": 12} in body["inventory"]
    assert body["history"][0]["action"] == "create"
    assert set(body["history"][0]) == {"timestamp", "badgeId", "action", "details"}


def test_404s_on_missing_tool(admin_client):
    assert admin_client.get("/api/tools/99999").status_code == 404
    assert admin_client.get("/api/tools/99999").json() == {"error": "Tool not found"}


def test_edits_fields_and_validates_attributes(admin_client, conn, make_location):
    f = make_tools(admin_client, conn, make_location)
    res = admin_client.patch(f"/api/tools/{f['toolId']}", json={
        "attributes": {"diameter_mm": "oops"}})
    assert res.status_code == 400
    assert res.json()["error"] == "Invalid attribute values"
    assert res.json()["fields"] == {"diameter_mm": "Must be a number"}

    res = admin_client.patch(f"/api/tools/{f['toolId']}", json={
        "name": "6.35mm end mill",
        "attributes": {"diameter_mm": 6.35, "coating": "DLC"}, "reorderMin": 3})
    assert res.status_code == 200
    assert res.json() == {"id": f["toolId"], "name": "6.35mm end mill"}
    row = conn.execute("SELECT * FROM tools WHERE id=?", (f["toolId"],)).fetchone()
    assert row["name"] == "6.35mm end mill"
    assert json.loads(row["attributes"]) == {"diameter_mm": 6.35, "coating": "DLC"}
    assert row["reorder_min"] == 3


def test_replaces_inventory_merging_duplicate_rows_and_dropping_zeros(
        admin_client, conn, make_location):
    f = make_tools(admin_client, conn, make_location)
    loc_a = f["a"]["locationId"]
    res = admin_client.put(f"/api/tools/{f['toolId']}/inventory", json={
        "inventory": [{"locationId": loc_a, "quantity": 5},
                      {"locationId": loc_a, "quantity": 2},
                      {"locationId": loc_a, "quantity": 0}]})
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    inv = conn.execute(
        "SELECT location_id, quantity FROM inventory WHERE tool_id=?",
        (f["toolId"],)).fetchall()
    assert [dict(r) for r in inv] == [{"location_id": loc_a, "quantity": 7}]
    audit = conn.execute(
        "SELECT * FROM activity_log WHERE entity='tool' AND entity_id=? AND action='set_inventory'",
        (str(f["toolId"]),)).fetchall()
    assert len(audit) == 1
    assert audit[0]["details"] == f"loc {loc_a}: 7"


def test_strips_old_type_attributes_when_the_type_changes(admin_client, conn,
                                                          make_location):
    types = admin_client.get("/api/tool-types").json()
    cutting = next(t for t in types if t["name"] == "Cutting tools")
    measuring = next(t for t in types if t["name"] == "Measuring tools")
    a = make_location("Milling", "Cabinet 3")
    res = admin_client.post("/api/tools", json={
        "name": "6mm end mill", "toolTypeId": cutting["id"],
        "attributes": {"diameter_mm": 6, "coating": "TiAlN"},
        "inventory": [{"locationId": a["locationId"], "quantity": 1}]})
    tool_id = res.json()["id"]
    r = admin_client.patch(f"/api/tools/{tool_id}", json={"toolTypeId": measuring["id"]})
    assert r.status_code == 200
    row = conn.execute("SELECT attributes FROM tools WHERE id=?", (tool_id,)).fetchone()
    assert json.loads(row["attributes"]) == {}


def test_keeps_attributes_untouched_on_a_fields_only_patch(admin_client, conn,
                                                           make_location):
    f = make_tools(admin_client, conn, make_location)
    r = admin_client.patch(f"/api/tools/{f['toolId']}", json={"name": "renamed end mill"})
    assert r.status_code == 200
    row = conn.execute("SELECT attributes FROM tools WHERE id=?",
                       (f["toolId"],)).fetchone()
    assert json.loads(row["attributes"]) == {"diameter_mm": 6, "coating": "TiAlN"}


def test_rejects_a_type_change_with_an_invalid_merged_attribute_value(admin_client,
                                                                      make_location):
    types = admin_client.get("/api/tool-types").json()
    cutting = next(t for t in types if t["name"] == "Cutting tools")
    grinding = next(t for t in types if t["name"] == "Grinding/diamond tools")
    f = make_tools(admin_client, None, make_location)
    r = admin_client.patch(f"/api/tools/{f['toolId']}", json={
        "toolTypeId": grinding["id"], "attributes": {"diameter_mm": "wide"}})
    assert r.status_code == 400
    assert r.json()["fields"] == {"diameter_mm": "Must be a number"}


def test_rejects_negative_or_non_integer_quantities(admin_client, conn, make_location):
    f = make_tools(admin_client, conn, make_location)
    r1 = admin_client.put(f"/api/tools/{f['toolId']}/inventory", json={
        "inventory": [{"locationId": f["a"]["locationId"], "quantity": -2}]})
    assert r1.status_code == 400
    r2 = admin_client.put(f"/api/tools/{f['toolId']}/inventory", json={
        "inventory": [{"locationId": f["a"]["locationId"], "quantity": 1.5}]})
    assert r2.status_code == 400


def test_deletes_a_tool_and_its_inventory_rows(admin_client, conn, make_location):
    f = make_tools(admin_client, conn, make_location)
    assert admin_client.delete(f"/api/tools/{f['toolId']}").status_code == 200
    assert conn.execute("SELECT 1 FROM tools WHERE id=?", (f["toolId"],)).fetchone() is None
    assert conn.execute("SELECT 1 FROM inventory WHERE tool_id=?",
                        (f["toolId"],)).fetchone() is None
    audit = conn.execute(
        "SELECT * FROM activity_log WHERE entity='tool' AND entity_id=?",
        (str(f["toolId"]),)).fetchall()
    assert len(audit) > 0
    assert audit[-1]["action"] == "delete"
