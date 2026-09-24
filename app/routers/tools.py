"""Tools API — search, create, detail, edit, inventory replacement, delete.

Port of tool_db2's ``server/routes/tools.js`` plus ``buildToolQuery`` (see
``app/search.py``). Tools are readable AND writable by any logged-in user
(no admin gate — matches the Node app).
"""

import json
import math

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.db import log_action
from app.routers._util import _clean
from app.search import INT64_MAX, build_tool_query
from app.validation import validate_attributes

_BAD_INVENTORY = "Each inventory row needs locationId and a non-negative integer quantity"


def _as_number(raw):
    """Coerce like JS ``Number()``: bool/int/float, or numeric string.

    Non-finite values (NaN/Infinity, e.g. the strings "nan"/"inf") and anything
    beyond the SQLite INTEGER range become None so callers return their own 400
    instead of overflowing the parameter bind.
    """
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw if -INT64_MAX - 1 <= raw <= INT64_MAX else None
    if isinstance(raw, float):
        return raw if math.isfinite(raw) and abs(raw) <= INT64_MAX else None
    if isinstance(raw, str):
        try:
            n = float(raw)
        except ValueError:
            return None
        return n if math.isfinite(n) and abs(n) <= INT64_MAX else None
    return None


def clean_inventory_rows(conn, inventory):
    """Normalize an inventory payload to ``[{locationId, quantity}]``.

    Duplicate locationIds merge by summation, zero/negative totals are dropped,
    and any bad row or unknown location raises HTTP 400.
    """
    merged = {}
    for row in (inventory if isinstance(inventory, list) else []):
        row = row if isinstance(row, dict) else {}
        location_id = _as_number(row.get("locationId"))
        quantity = _as_number(row.get("quantity"))
        if (not location_id
                or not isinstance(quantity, (int, float))
                or (isinstance(quantity, float) and not quantity.is_integer())
                or quantity < 0):
            raise HTTPException(status_code=400, detail=_BAD_INVENTORY)
        location_id, quantity = int(location_id), int(quantity)
        if not conn.execute("SELECT 1 FROM locations WHERE id=?",
                            (location_id,)).fetchone():
            raise HTTPException(
                status_code=400, detail=f"Location {location_id} does not exist")
        merged[location_id] = merged.get(location_id, 0) + quantity
    return [{"locationId": loc, "quantity": qty}
            for loc, qty in merged.items() if qty > 0]


def _reorder_min(body):
    """None/'' -> NULL; otherwise an int or HTTP 400."""
    raw = body.get("reorderMin")
    if raw is None or raw == "":
        return None
    n = _as_number(raw)
    if isinstance(n, int):
        return n
    if n is None or not n.is_integer():
        raise HTTPException(status_code=400, detail="reorderMin must be a number")
    return int(n)


def tools_router(get_conn) -> APIRouter:
    r = APIRouter()

    @r.get("/tools")
    def list_tools(q=None, typeId=None, departmentId=None, locationId=None,
                   conn=Depends(get_conn)):
        result = build_tool_query(conn, q=q, type_id=typeId,
                                  department_id=departmentId, location_id=locationId)
        return {"results": result["rows"], "locationsByTool": result["locations_by_tool"]}

    @r.post("/tools", status_code=201)
    def create_tool(request: Request, body: dict, conn=Depends(get_conn)):
        name = _clean(body.get("name"))
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        type_id = _as_number(body.get("toolTypeId"))
        type_row = conn.execute("SELECT * FROM tool_types WHERE id=?",
                                (type_id,)).fetchone()
        if type_row is None:
            raise HTTPException(status_code=400, detail="Unknown tool type")
        schema = json.loads(type_row["attribute_schema"])
        attrs = validate_attributes(schema, body.get("attributes"))
        if not attrs["ok"]:
            return JSONResponse(status_code=400,
                                content={"error": "Invalid attribute values",
                                         "fields": attrs["errors"]})
        inventory = clean_inventory_rows(conn, body.get("inventory"))
        reorder_min = _reorder_min(body)
        with conn:
            cur = conn.execute(
                "INSERT INTO tools (name, description, tool_type_id, attributes, notes,"
                " reorder_min) VALUES (?, ?, ?, ?, ?, ?)",
                (name, _clean(body.get("description")), type_row["id"],
                 json.dumps(attrs["clean"]),
                 _clean(body.get("notes")), reorder_min))
            tool_id = cur.lastrowid
            for row in inventory:
                conn.execute(
                    "INSERT INTO inventory (tool_id, location_id, quantity) VALUES (?, ?, ?)",
                    (tool_id, row["locationId"], row["quantity"]))
            log_action(conn, request.session.get("badge_id"), "create", "tool",
                       tool_id, f"name: {name}")
        return {"id": tool_id, "name": name, "toolTypeId": type_row["id"]}

    @r.get("/tools/{tool_id}")
    def get_tool(tool_id, conn=Depends(get_conn)):
        t = conn.execute(
            "SELECT t.id, t.name, t.description, t.tool_type_id AS typeId,"
            " tt.name AS typeName, t.attributes, t.notes, t.reorder_min AS reorderMin"
            " FROM tools t JOIN tool_types tt ON tt.id = t.tool_type_id WHERE t.id = ?",
            (tool_id,)).fetchone()
        if t is None:
            raise HTTPException(status_code=404, detail="Tool not found")
        inventory = conn.execute(
            "SELECT i.location_id AS locationId, l.name AS locationName,"
            " d.name AS departmentName, i.quantity"
            " FROM inventory i JOIN locations l ON l.id = i.location_id"
            " JOIN departments d ON d.id = l.department_id"
            " WHERE i.tool_id = ? ORDER BY d.name, l.name", (t["id"],)).fetchall()
        history = conn.execute(
            "SELECT timestamp, badge_id AS badgeId, action, details FROM activity_log"
            " WHERE entity='tool' AND entity_id=? ORDER BY id DESC LIMIT 50",
            (str(t["id"]),)).fetchall()
        return {
            "id": t["id"], "name": t["name"], "description": t["description"],
            "typeId": t["typeId"], "typeName": t["typeName"],
            "attributes": json.loads(t["attributes"]), "notes": t["notes"],
            "reorderMin": t["reorderMin"],
            "inventory": [dict(r) for r in inventory],
            "history": [dict(r) for r in history],
        }

    @r.patch("/tools/{tool_id}")
    def patch_tool(tool_id, request: Request, body: dict, conn=Depends(get_conn)):
        row = conn.execute("SELECT * FROM tools WHERE id=?", (tool_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Tool not found")
        raw_type_id = body.get("toolTypeId")
        type_id = _as_number(raw_type_id) if raw_type_id is not None else row["tool_type_id"]
        type_row = conn.execute("SELECT * FROM tool_types WHERE id=?",
                                (type_id,)).fetchone()
        if type_row is None:
            raise HTTPException(status_code=400, detail="Unknown tool type")
        type_changed = type_id != row["tool_type_id"]
        merged = {**json.loads(row["attributes"]),
                  **(body.get("attributes") if isinstance(body.get("attributes"), dict) else {})}
        stored_attributes = row["attributes"]
        if "attributes" in body or type_changed:
            # Attributes sent or the type changed: persist ONLY the validated set
            # (strips keys the new schema does not know about, keeps omitted
            # fields via the merged set).
            attrs = validate_attributes(json.loads(type_row["attribute_schema"]), merged)
            if not attrs["ok"]:
                return JSONResponse(status_code=400,
                                    content={"error": "Invalid attribute values",
                                             "fields": attrs["errors"]})
            stored_attributes = json.dumps(attrs["clean"])
        name = _clean(body.get("name") if body.get("name") is not None else row["name"])
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        description = body.get("description")
        description = (_clean(description) if description is not None
                       else row["description"])
        notes = body.get("notes")
        notes = _clean(notes) if notes is not None else row["notes"]
        reorder_min = (_reorder_min(body) if "reorderMin" in body
                       else row["reorder_min"])
        with conn:
            conn.execute(
                "UPDATE tools SET name=?, description=?, tool_type_id=?, attributes=?,"
                " notes=?, reorder_min=? WHERE id=?",
                (name, description, type_row["id"], stored_attributes, notes,
                 reorder_min, row["id"]))
            log_action(conn, request.session.get("badge_id"), "update", "tool",
                       row["id"], f"name: {name}")
        return {"id": row["id"], "name": name}

    @r.put("/tools/{tool_id}/inventory")
    def set_tool_inventory(tool_id, request: Request, body: dict,
                           conn=Depends(get_conn)):
        row = conn.execute("SELECT id FROM tools WHERE id=?", (tool_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Tool not found")
        rows = clean_inventory_rows(conn, body.get("inventory"))
        with conn:
            conn.execute("DELETE FROM inventory WHERE tool_id=?", (row["id"],))
            for r in rows:
                conn.execute(
                    "INSERT INTO inventory (tool_id, location_id, quantity)"
                    " VALUES (?, ?, ?)", (row["id"], r["locationId"], r["quantity"]))
            log_action(conn, request.session.get("badge_id"), "set_inventory", "tool",
                       row["id"],
                       ", ".join(f"loc {r['locationId']}: {r['quantity']}" for r in rows))
        return {"ok": True}

    @r.delete("/tools/{tool_id}")
    def delete_tool(tool_id, request: Request, conn=Depends(get_conn)):
        row = conn.execute("SELECT name FROM tools WHERE id=?", (tool_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Tool not found")
        with conn:
            conn.execute("DELETE FROM inventory WHERE tool_id=?", (tool_id,))
            conn.execute("DELETE FROM tools WHERE id=?", (tool_id,))
            log_action(conn, request.session.get("badge_id"), "delete", "tool",
                       tool_id, f"name: {row['name']}")
        return {"ok": True}

    return r
