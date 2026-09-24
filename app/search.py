"""Search helpers.

Port of tool_db2's ``server/search.js``: LIKE-escaping plus the tool query with
per-location inventory breakdown. Non-negative-integer filter validation
mirrors the Node ``filterNumber`` (400 ``"<name> must be a number"``).
"""

import json
import math

from fastapi import HTTPException


def escape_like(s: str) -> str:
    return "".join("\\" + ch if ch in "\\%_" else ch for ch in s)


INT64_MAX = 2**63 - 1  # SQLite INTEGER ceiling; larger values crash at bind time


def _filter_number(name, value):
    """Non-negative finite integer or HTTP 400 — port of Node's ``filterNumber``."""
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(status_code=400, detail=f"{name} must be a number")
    if not math.isfinite(n) or not n.is_integer() or n < 0 or n > INT64_MAX:
        raise HTTPException(status_code=400, detail=f"{name} must be a number")
    return int(n)


def build_tool_query(conn, q=None, type_id=None, department_id=None, location_id=None):
    """Return ``{"rows": [...], "locations_by_tool": {tool_id_str: [...]}}``.

    Rows are camelCase (``typeId``, ``typeName``, ``reorderMin``, ``totalQty``)
    with ``attributes`` decoded to a dict; breakdown rows are
    ``{locationId, locationName, departmentName, quantity}`` ordered by
    department then location name, keyed by the tool's id as a string to match
    the Node JSON shape.
    """
    where = []
    params = {}
    if q:
        where.append("(t.name LIKE :q ESCAPE '\\' OR t.description LIKE :q ESCAPE '\\'"
                     " OR EXISTS (SELECT 1 FROM json_each(t.attributes) je"
                     " WHERE je.value LIKE :q ESCAPE '\\'))")
        params["q"] = f"%{escape_like(str(q))}%"
    if type_id:
        where.append("t.tool_type_id = :typeId")
        params["typeId"] = _filter_number("typeId", type_id)
    if location_id:
        where.append("EXISTS (SELECT 1 FROM inventory i WHERE i.tool_id = t.id"
                     " AND i.location_id = :locationId)")
        params["locationId"] = _filter_number("locationId", location_id)
    if department_id:
        where.append("EXISTS (SELECT 1 FROM inventory i JOIN locations l"
                     " ON l.id = i.location_id WHERE i.tool_id = t.id"
                     " AND l.department_id = :departmentId)")
        params["departmentId"] = _filter_number("departmentId", department_id)
    sql = f"""
    SELECT t.id, t.name, t.description, t.tool_type_id AS typeId, tt.name AS typeName,
           t.attributes, t.notes, t.reorder_min AS reorderMin,
           COALESCE((SELECT SUM(quantity) FROM inventory WHERE tool_id = t.id), 0) AS totalQty
    FROM tools t JOIN tool_types tt ON tt.id = t.tool_type_id
    {'WHERE ' + ' AND '.join(where) if where else ''}
    ORDER BY t.name COLLATE NOCASE"""
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for r in rows:
        r["attributes"] = json.loads(r["attributes"])

    locations_by_tool = {}
    if rows:
        ids = [r["id"] for r in rows]
        placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
        inv_params = {f"id{i}": v for i, v in enumerate(ids)}
        inv = conn.execute(f"""
            SELECT i.tool_id, i.location_id AS locationId, l.name AS locationName,
                   d.name AS departmentName, i.quantity
            FROM inventory i JOIN locations l ON l.id = i.location_id
                             JOIN departments d ON d.id = l.department_id
            WHERE i.tool_id IN ({placeholders})
            ORDER BY d.name, l.name""", inv_params).fetchall()
        for row in inv:
            locations_by_tool.setdefault(str(row["tool_id"]), []).append({
                "locationId": row["locationId"], "locationName": row["locationName"],
                "departmentName": row["departmentName"], "quantity": row["quantity"]})
    return {"rows": rows, "locations_by_tool": locations_by_tool}
