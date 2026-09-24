"""Port of tool_db2 tests/search.test.js (create + search).

Excludes the Node file's "replaces inventory, merging duplicate locations and
dropping zero quantities" case: that exercises PUT /api/tools/:id/inventory and
belongs to the Task 9 tests (tests/test_tools.py).

Conftest seeds E100 'Admin User' (admin) and E200 'Regular User' (non-admin);
tool reads/writes are open to any logged-in user (no admin gate).
"""

from test_tools import make_tools


def test_creates_a_tool_with_multi_location_inventory(admin_client, conn, make_location):
    f = make_tools(admin_client, conn, make_location)
    row = conn.execute("SELECT * FROM tools WHERE id=?", (f["toolId"],)).fetchone()
    assert row["name"] == "6mm end mill"
    import json
    assert json.loads(row["attributes"]) == {"diameter_mm": 6, "coating": "TiAlN"}
    inv = conn.execute(
        "SELECT location_id, quantity FROM inventory WHERE tool_id=? ORDER BY location_id",
        (f["toolId"],)).fetchall()
    got = {r["location_id"]: r["quantity"] for r in inv}
    assert got == {f["a"]["locationId"]: 12, f["b"]["locationId"]: 4}


def test_rejects_invalid_attributes_and_unknown_type(admin_client):
    types = admin_client.get("/api/tool-types").json()
    cutting = next(t for t in types if t["name"] == "Cutting tools")
    res = admin_client.post("/api/tools", json={
        "name": "x", "toolTypeId": cutting["id"], "attributes": {"diameter_mm": "wide"}})
    assert res.status_code == 400
    assert res.json()["error"] == "Invalid attribute values"
    assert res.json()["fields"] == {"diameter_mm": "Must be a number"}
    assert admin_client.post("/api/tools", json={
        "name": "x", "toolTypeId": 99999999}).status_code == 400
    assert admin_client.post("/api/tools", json={
        "toolTypeId": cutting["id"]}).status_code == 400


def test_searches_name_description_and_attribute_values(admin_client, conn, make_location):
    make_tools(admin_client, conn, make_location)

    def names(q):
        return [r["name"] for r in admin_client.get(
            "/api/tools", params={"q": q}).json()["results"]]

    assert names("end mill") == ["6mm end mill"]
    assert names("carbide") == ["6mm end mill"]
    assert names("TiAlN") == ["6mm end mill"]
    assert names("caliper") == ["6in caliper"]
    assert names("zzz") == []


def test_treats_like_wildcards_in_q_as_literal_characters(admin_client, conn, make_location):
    types = admin_client.get("/api/tool-types").json()
    measuring = next(t for t in types if t["name"] == "Measuring tools")
    assert admin_client.post("/api/tools", json={
        "name": "100% dressing pad", "toolTypeId": measuring["id"]}).status_code == 201
    make_tools(admin_client, conn, make_location)

    def names(q):
        return [r["name"] for r in admin_client.get(
            "/api/tools", params={"q": q}).json()["results"]]

    assert names("100%") == ["100% dressing pad"]
    assert names("6_mm") == []
    assert names("milling_qc") == []


def test_rejects_non_numeric_filter_values_with_400(admin_client):
    assert admin_client.get("/api/tools", params={"typeId": "abc"}).status_code == 400
    assert admin_client.get("/api/tools", params={"locationId": "xyz"}).status_code == 400
    assert admin_client.get("/api/tools", params={"departmentId": "1.5"}).status_code == 400
    # finite but beyond the 64-bit INTEGER range must 400, not overflow the bind
    assert admin_client.get("/api/tools", params={"typeId": "1e30"}).status_code == 400


def test_rejects_out_of_range_reorder_min_and_inventory_location(admin_client, conn,
                                                                 make_location):
    types = admin_client.get("/api/tool-types").json()
    cutting = next(t for t in types if t["name"] == "Cutting tools")
    loc = make_location("Milling", "Cab")
    res = admin_client.post("/api/tools", json={
        "name": "x", "toolTypeId": cutting["id"], "reorderMin": 10**30})
    assert res.status_code == 400
    assert res.json()["error"] == "reorderMin must be a number"
    res = admin_client.post("/api/tools", json={
        "name": "x", "toolTypeId": cutting["id"],
        "inventory": [{"locationId": 1e30, "quantity": 3}]})
    assert res.status_code == 400


def test_filters_by_type_department_location_and_returns_breakdown_and_totals(
        admin_client, conn, make_location):
    f = make_tools(admin_client, conn, make_location)
    all_rows = admin_client.get("/api/tools").json()["results"]
    mill = next(r for r in all_rows if r["name"] == "6mm end mill")
    assert mill["totalQty"] == 16
    assert mill["reorderMin"] == 2
    breakdown = admin_client.get("/api/tools").json()["locationsByTool"][str(f["toolId"])]
    assert {"locationId": f["a"]["locationId"], "locationName": "Cabinet 3",
            "departmentName": "Milling", "quantity": 12} in breakdown
    assert {"locationId": f["b"]["locationId"], "locationName": "Shelf 2",
            "departmentName": "QC", "quantity": 4} in breakdown
    by_type = [r["name"] for r in admin_client.get(
        "/api/tools", params={"typeId": f["cutting"]["id"]}).json()["results"]]
    assert by_type == ["6mm end mill"]
    by_loc = [r["name"] for r in admin_client.get(
        "/api/tools", params={"locationId": f["a"]["locationId"]}).json()["results"]]
    assert by_loc == ["6mm end mill"]
    by_dept = [r["name"] for r in admin_client.get(
        "/api/tools", params={"departmentId": f["a"]["departmentId"]}).json()["results"]]
    assert by_dept == ["6mm end mill"]


def test_decimal_attribute_end_to_end(admin_client, conn, make_location):
    types = admin_client.get("/api/tool-types").json()
    cutting = next(t for t in types if t["name"] == "Cutting tools")
    loc = make_location("Milling", "Cab")
    tool = admin_client.post("/api/tools", json={
        "name": '0.250" end mill', "toolTypeId": cutting["id"],
        "attributes": {"diameter_mm": "0.250"},
        "inventory": [{"locationId": loc["locationId"], "quantity": 3}]})
    assert tool.status_code == 201
    found = admin_client.get("/api/tools", params={"q": "0.250"}).json()["results"]
    assert len(found) == 1 and found[0]["attributes"]["diameter_mm"] == 0.25


def test_tools_routes_are_open_to_any_logged_in_user(user_client):
    assert user_client.get("/api/tools").status_code == 200
