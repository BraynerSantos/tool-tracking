"""Port of tool_db2 tests/export.test.js (toCsv + export/backup endpoints).

The Node file's seed() is ported 1:1 (one location, one 6mm end mill with
diameter_mm/coating attributes and 12 pcs at Milling / Cabinet 3).

Conftest seeds E100 'Admin User' (admin) and E200 'Regular User' (non-admin).
Export is open to any logged-in user; backup is admin-only; /api/config is
public.
"""

import re
import sqlite3

from app.csv_export import to_csv


def seed(agent, make_location):
    types = agent.get("/api/tool-types").json()
    cutting = next(t for t in types if t["name"] == "Cutting tools")
    a = make_location("Milling", "Cabinet 3")
    res = agent.post("/api/tools", json={
        "name": "6mm end mill", "toolTypeId": cutting["id"],
        "attributes": {"diameter_mm": 6, "coating": "TiAlN"},
        "inventory": [{"locationId": a["locationId"], "quantity": 12}]})
    assert res.status_code == 201
    return {"cutting": cutting, "a": a}


def test_escapes_commas_quotes_newlines_and_uses_crlf():
    csv = to_csv(["A", "B"], [["plain", "has,comma"], ['has"quote', "line\nbreak"]])
    assert csv == 'A,B\r\nplain,"has,comma"\r\n"has""quote","line\nbreak"\r\n'


def test_exports_the_filtered_set_as_csv_with_attribute_columns(
        admin_client, make_location):
    seed(admin_client, make_location)
    res = admin_client.get("/api/export.csv", params={"q": "end mill"})
    assert res.status_code == 200
    assert re.search(r"text/csv", res.headers["content-type"])
    lines = res.text.split("\r\n")
    assert "Name" in lines[0]
    assert "Diameter (mm)" in lines[0]
    assert "6mm end mill" in lines[1]
    assert "TiAlN" in lines[1]
    assert "Milling - Cabinet 3: 12" in lines[1]


def test_exports_respect_filters_empty_result_is_header_only(
        admin_client, make_location):
    seed(admin_client, make_location)
    res = admin_client.get("/api/export.csv", params={"q": "zzz"})
    assert res.status_code == 200
    assert len(res.text.split("\r\n")) == 2  # header + trailing empty


def test_downloads_a_sqlite_backup(admin_client, tmp_path, make_location):
    seed(admin_client, make_location)
    res = admin_client.get("/api/backup")
    assert res.status_code == 200
    assert re.search(r"tooldb-backup-.*\.sqlite", res.headers["content-disposition"])
    # SQLite files start with the "SQLite format 3" magic string
    assert res.content[:16].startswith(b"SQLite format 3")
    # the copy contains the seeded tool
    copy = tmp_path / "copy.sqlite"
    copy.write_bytes(res.content)
    c = sqlite3.connect(copy)
    try:
        names = [r[0] for r in c.execute("SELECT name FROM tools").fetchall()]
    finally:
        c.close()
    assert names == ["6mm end mill"]


def test_backup_is_admin_only(user_client):
    assert user_client.get("/api/backup").status_code == 403


def test_export_is_open_to_any_logged_in_user(user_client, make_location):
    seed(user_client, make_location)
    assert user_client.get("/api/export.csv").status_code == 200


def test_config_is_public(anon_client):
    res = anon_client.get("/api/config")
    assert res.status_code == 200
    assert res.json() == {"companyName": "Tool DB"}


def test_invalid_filter_on_export_returns_400_json(admin_client):
    res = admin_client.get("/api/export.csv", params={"typeId": "abc"})
    assert res.status_code == 400
    assert res.json() == {"error": "typeId must be a number"}
