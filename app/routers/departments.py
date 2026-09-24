"""Departments & locations API.

Port of tool_db2's ``server/routes/departments.js``. Reads are open to any
logged-in user (the router is mounted behind ``require_user`` in main.py);
every mutation is admin-only via ``require_admin``. Deletes are guarded:
a department with locations and a location holding inventory cannot be
removed (409).
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import require_admin
from app.db import log_action


def _clean(value):
    return str(value).strip() if value is not None else ""


def departments_router(get_conn) -> APIRouter:
    r = APIRouter()

    @r.get("/departments")
    def list_departments(conn=Depends(get_conn)):
        deps = conn.execute("SELECT id, name FROM departments ORDER BY name").fetchall()
        locs = conn.execute(
            "SELECT id, department_id, name FROM locations ORDER BY name").fetchall()
        return [{"id": d["id"], "name": d["name"],
                 "locations": [{"id": l["id"], "name": l["name"],
                                "departmentId": l["department_id"]}
                               for l in locs if l["department_id"] == d["id"]]}
                for d in deps]

    @r.post("/departments", status_code=201, dependencies=[Depends(require_admin)])
    def create_department(request: Request, body: dict, conn=Depends(get_conn)):
        name = _clean(body.get("name"))
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        with conn:
            if conn.execute("SELECT 1 FROM departments WHERE name=?", (name,)).fetchone():
                raise HTTPException(status_code=409, detail="Department already exists")
            cur = conn.execute("INSERT INTO departments (name) VALUES (?)", (name,))
            log_action(conn, request.session.get("badge_id"), "create", "department",
                       cur.lastrowid, name)
        return {"id": cur.lastrowid, "name": name}

    @r.patch("/departments/{dept_id}", dependencies=[Depends(require_admin)])
    def rename_department(dept_id, request: Request, body: dict, conn=Depends(get_conn)):
        name = _clean(body.get("name"))
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        dep = conn.execute("SELECT id FROM departments WHERE id=?", (dept_id,)).fetchone()
        if dep is None:
            raise HTTPException(status_code=404, detail="Not found")
        with conn:
            # collision check excludes the row being renamed (renaming to own name is a no-op)
            if conn.execute("SELECT 1 FROM departments WHERE name=? AND id<>?",
                            (name, dep["id"])).fetchone():
                raise HTTPException(status_code=409, detail="Department already exists")
            conn.execute("UPDATE departments SET name=? WHERE id=?", (name, dep["id"]))
            log_action(conn, request.session.get("badge_id"), "update", "department",
                       dep["id"], name)
        return {"id": dep["id"], "name": name}

    @r.delete("/departments/{dept_id}", dependencies=[Depends(require_admin)])
    def delete_department(dept_id, request: Request, conn=Depends(get_conn)):
        if conn.execute("SELECT 1 FROM locations WHERE department_id=?", (dept_id,)).fetchone():
            raise HTTPException(
                status_code=409, detail="Department has locations; move or delete them first")
        with conn:
            conn.execute("DELETE FROM departments WHERE id=?", (dept_id,))
            log_action(conn, request.session.get("badge_id"), "delete", "department", dept_id)
        return {"ok": True}

    @r.post("/locations", status_code=201, dependencies=[Depends(require_admin)])
    def create_location(request: Request, body: dict, conn=Depends(get_conn)):
        department_id = body.get("departmentId")
        try:
            department_id = int(department_id)
        except (TypeError, ValueError):
            department_id = 0
        name = _clean(body.get("name"))
        if not department_id or not name:
            raise HTTPException(status_code=400, detail="departmentId and name required")
        with conn:
            if not conn.execute("SELECT 1 FROM departments WHERE id=?",
                                (department_id,)).fetchone():
                raise HTTPException(status_code=404, detail="Department not found")
            if conn.execute("SELECT 1 FROM locations WHERE department_id=? AND name=?",
                            (department_id, name)).fetchone():
                raise HTTPException(
                    status_code=409, detail="Location already exists in this department")
            cur = conn.execute("INSERT INTO locations (department_id, name) VALUES (?, ?)",
                               (department_id, name))
            log_action(conn, request.session.get("badge_id"), "create", "location",
                       cur.lastrowid, name)
        return {"id": cur.lastrowid, "name": name, "departmentId": department_id}

    @r.patch("/locations/{loc_id}", dependencies=[Depends(require_admin)])
    def rename_location(loc_id, request: Request, body: dict, conn=Depends(get_conn)):
        name = _clean(body.get("name"))
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        loc = conn.execute("SELECT id, department_id FROM locations WHERE id=?",
                           (loc_id,)).fetchone()
        if loc is None:
            raise HTTPException(status_code=404, detail="Not found")
        with conn:
            # duplicate check is scoped to siblings in the same department
            if conn.execute(
                    "SELECT 1 FROM locations WHERE department_id=? AND name=? AND id<>?",
                    (loc["department_id"], name, loc["id"])).fetchone():
                raise HTTPException(
                    status_code=409, detail="Location already exists in this department")
            conn.execute("UPDATE locations SET name=? WHERE id=?", (name, loc["id"]))
            log_action(conn, request.session.get("badge_id"), "update", "location",
                       loc["id"], name)
        return {"id": loc["id"], "name": name}

    @r.delete("/locations/{loc_id}", dependencies=[Depends(require_admin)])
    def delete_location(loc_id, request: Request, conn=Depends(get_conn)):
        if conn.execute("SELECT 1 FROM inventory WHERE location_id=?", (loc_id,)).fetchone():
            raise HTTPException(status_code=409, detail="Location holds inventory; empty it first")
        with conn:
            conn.execute("DELETE FROM locations WHERE id=?", (loc_id,))
            log_action(conn, request.session.get("badge_id"), "delete", "location", loc_id)
        return {"ok": True}

    return r
