"""Employees API.

Port of tool_db2's ``server/routes/employees.js`` with the tooldb-py deltas:

- Responses include ``isAdmin`` (bool) wherever employees appear.
- All management routes (list/create/import/patch) are admin-only.
- PATCH accepts ``{active?, isAdmin?}`` and enforces a last-admin guard (409).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.auth import require_admin
from app.db import log_action
from app.search import escape_like


def _parse_bool(raw):
    """Return 1/0 for true/false (booleans or the ints 1/0), else None.

    Matches the Node port's strictness: strings like "false" are never coerced.
    """
    if raw is True or (isinstance(raw, int) and not isinstance(raw, bool) and raw == 1):
        return 1
    if raw is False or (isinstance(raw, int) and not isinstance(raw, bool) and raw == 0):
        return 0
    return None


def _emp_json(r):
    return {"badgeId": r["badge_id"], "name": r["name"], "active": r["active"],
            "isAdmin": bool(r["is_admin"])}


def _clean(value):
    return str(value).strip() if value is not None else ""


def employees_router(get_conn) -> APIRouter:
    r = APIRouter()

    @r.get("/employees")
    def list_employees(q: str = "", conn=Depends(get_conn)):
        pat = f"%{escape_like(q or '')}%"
        rows = conn.execute(
            "SELECT * FROM employees "
            "WHERE name LIKE ? ESCAPE '\\' OR badge_id LIKE ? ESCAPE '\\' "
            "ORDER BY active DESC, badge_id", (pat, pat)).fetchall()
        return [_emp_json(r) for r in rows]

    @r.post("/employees", status_code=201)
    def create_employee(request: Request, body: dict, conn=Depends(get_conn)):
        badge_id = _clean(body.get("badgeId"))
        name = _clean(body.get("name"))
        if not badge_id or not name:
            raise HTTPException(status_code=400, detail="badgeId and name required")
        with conn:
            if conn.execute("SELECT 1 FROM employees WHERE badge_id=?", (badge_id,)).fetchone():
                raise HTTPException(status_code=409, detail="Employee ID already exists")
            conn.execute("INSERT INTO employees (badge_id, name) VALUES (?, ?)", (badge_id, name))
            log_action(conn, request.session.get("badge_id"), "create", "employee", badge_id,
                       f"name: {name}")
        return {"badgeId": badge_id, "name": name, "active": 1, "isAdmin": False}

    @r.post("/employees/import")
    def import_employees(request: Request, body: dict, conn=Depends(get_conn)):
        rows = body.get("rows")
        rows = rows if isinstance(rows, list) else []
        imported = skipped = 0
        with conn:
            existing = {r["badge_id"]: r["name"] for r in
                        conn.execute("SELECT badge_id, name FROM employees")}
            for row in rows:
                if not isinstance(row, dict):
                    skipped += 1
                    continue
                badge_id = _clean(row.get("badgeId"))
                name = _clean(row.get("name"))
                if not badge_id or not name:
                    skipped += 1
                    continue
                if badge_id in existing:
                    if existing[badge_id] != name:
                        conn.execute("UPDATE employees SET name = ?, active = 1 WHERE badge_id = ?",
                                     (name, badge_id))
                        existing[badge_id] = name
                        imported += 1
                    else:
                        skipped += 1
                else:
                    conn.execute("INSERT INTO employees (badge_id, name) VALUES (?, ?)",
                                 (badge_id, name))
                    existing[badge_id] = name
                    imported += 1
            log_action(conn, request.session.get("badge_id"), "import", "employee", "",
                       f"{imported} imported, {skipped} skipped")
        return {"imported": imported, "skipped": skipped}

    @r.patch("/employees/{badge_id}")
    def patch_employee(badge_id: str, request: Request, body: dict, conn=Depends(get_conn)):
        # Each present field must be true/false or 1/0; anything else — missing,
        # {}, "false" — is rejected, never coerced.
        updates = {}
        for field in ("active", "isAdmin"):
            if field in body:
                value = _parse_bool(body[field])
                if value is None:
                    raise HTTPException(status_code=400, detail=f"{field} must be a boolean")
                updates[field] = value
        if not updates:
            raise HTTPException(status_code=400, detail="active (boolean) is required")
        emp = conn.execute("SELECT * FROM employees WHERE badge_id=?", (badge_id,)).fetchone()
        if emp is None:
            raise HTTPException(status_code=404, detail="Employee not found")
        # Last-admin guard, pre-checked before any write: deactivating or demoting
        # the only remaining active admin must fail.
        leaving_admin_state = (emp["is_admin"] == 1 and emp["active"] == 1) and any(
            updates.get(f) == 0 for f in ("active", "isAdmin") if f in updates)
        if leaving_admin_state:
            would_be = conn.execute(
                "SELECT COUNT(*) c FROM employees WHERE is_admin=1 AND active=1 AND badge_id != ?",
                (badge_id,)).fetchone()["c"]
            if would_be == 0:
                return JSONResponse(status_code=409,
                                    content={"error": "Cannot remove the last active admin"})
        with conn:
            columns = {f: {"active": "active", "isAdmin": "is_admin"}[f] for f in updates}
            conn.execute(
                f"UPDATE employees SET {', '.join(f'{col} = ?' for col in columns.values())} "
                "WHERE badge_id = ?",
                (*updates.values(), badge_id))
            log_action(conn, request.session.get("badge_id"), "update", "employee", badge_id,
                       ", ".join(f"{f}: {v}" for f, v in updates.items()))
        updated = conn.execute("SELECT * FROM employees WHERE badge_id=?", (badge_id,)).fetchone()
        return _emp_json(updated)

    return r


def lookup_router(get_conn) -> APIRouter:
    r = APIRouter()

    @r.get("/employee-lookup")
    def employee_lookup(q: str = "", conn=Depends(get_conn)):
        # Mirror the UI's >=2-char rule server-side: this endpoint is unauthenticated,
        # so short/empty queries must not serve as a roster-enumeration oracle.
        raw = (q or "").strip()
        if len(raw) < 2:
            return []
        pat = f"%{escape_like(raw)}%"
        rows = conn.execute(
            "SELECT badge_id, name, is_admin FROM employees "
            "WHERE active = 1 AND (name LIKE ? ESCAPE '\\' OR badge_id LIKE ? ESCAPE '\\') "
            "ORDER BY badge_id LIMIT 5", (pat, pat)).fetchall()
        return [{"badgeId": r["badge_id"], "name": r["name"], "isAdmin": bool(r["is_admin"])}
                for r in rows]

    return r
