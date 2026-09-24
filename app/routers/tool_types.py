"""Tool types API.

Port of tool_db2's ``server/routes/toolTypes.js``. Reads are open to any
logged-in user (the router is mounted behind ``require_user`` in main.py);
every mutation is admin-only via ``require_admin``. Deletes are guarded:
a type that tools still reference cannot be removed (409).
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import require_admin
from app.db import log_action
from app.validation import validate_schema


def _clean(value):
    return str(value).strip() if value is not None else ""


def _row_to_type(row):
    return {"id": row["id"], "name": row["name"],
            "attributeSchema": json.loads(row["attribute_schema"])}


def tool_types_router(get_conn) -> APIRouter:
    r = APIRouter()

    @r.get("/tool-types")
    def list_tool_types(conn=Depends(get_conn)):
        rows = conn.execute("SELECT * FROM tool_types ORDER BY name").fetchall()
        return [_row_to_type(row) for row in rows]

    @r.post("/tool-types", status_code=201, dependencies=[Depends(require_admin)])
    def create_tool_type(request: Request, body: dict, conn=Depends(get_conn)):
        name = _clean(body.get("name"))
        if "attributeSchema" not in body:
            raise HTTPException(status_code=400, detail="attributeSchema is required")
        schema = body["attributeSchema"]
        schema_err = validate_schema(schema)
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        if schema_err:
            raise HTTPException(status_code=400, detail=schema_err)
        with conn:
            if conn.execute("SELECT 1 FROM tool_types WHERE name=?", (name,)).fetchone():
                raise HTTPException(status_code=409, detail="Tool type already exists")
            cur = conn.execute(
                "INSERT INTO tool_types (name, attribute_schema) VALUES (?, ?)",
                (name, json.dumps(schema)))
            log_action(conn, request.session.get("badge_id"), "create", "tool_type",
                       cur.lastrowid, name)
        return {"id": cur.lastrowid, "name": name, "attributeSchema": schema}

    @r.patch("/tool-types/{type_id}", dependencies=[Depends(require_admin)])
    def update_tool_type(type_id, request: Request, body: dict, conn=Depends(get_conn)):
        row = conn.execute("SELECT * FROM tool_types WHERE id=?", (type_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Not found")
        schema = body.get("attributeSchema")
        if schema is None:
            schema = json.loads(row["attribute_schema"])
        schema_err = validate_schema(schema)
        if schema_err:
            raise HTTPException(status_code=400, detail=schema_err)
        raw_name = body.get("name")
        name = _clean(raw_name) if raw_name is not None else row["name"]
        with conn:
            # collision check excludes the row being renamed (renaming to own name is a no-op)
            if name != row["name"] and conn.execute(
                    "SELECT 1 FROM tool_types WHERE name=? AND id<>?",
                    (name, row["id"])).fetchone():
                raise HTTPException(status_code=409, detail="Tool type already exists")
            conn.execute("UPDATE tool_types SET name=?, attribute_schema=? WHERE id=?",
                         (name, json.dumps(schema), row["id"]))
            log_action(conn, request.session.get("badge_id"), "update", "tool_type",
                       row["id"], name)
        return {"id": row["id"], "name": name, "attributeSchema": schema}

    @r.delete("/tool-types/{type_id}", dependencies=[Depends(require_admin)])
    def delete_tool_type(type_id, request: Request, conn=Depends(get_conn)):
        if conn.execute("SELECT 1 FROM tools WHERE tool_type_id=?", (type_id,)).fetchone():
            raise HTTPException(
                status_code=409, detail="Tools of this type exist; remove them first")
        with conn:
            conn.execute("DELETE FROM tool_types WHERE id=?", (type_id,))
            log_action(conn, request.session.get("badge_id"), "delete", "tool_type", type_id)
        return {"ok": True}

    return r
