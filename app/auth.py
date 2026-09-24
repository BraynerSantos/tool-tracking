from fastapi import APIRouter, Depends, HTTPException, Request


def require_user(request: Request):
    if not request.session.get("badge_id"):
        raise HTTPException(status_code=401, detail="Not logged in")


def _request_conn(request: Request):
    """The app's single connection, resolvable by FastAPI's dependency system.

    Routers receive the connection via a closure-provided ``get_conn``; guards that
    are used both as dependencies (``Depends(require_admin)``) and as plain calls
    (``require_admin(request, conn)``) read the same object off ``app.state``.
    """
    return request.app.state.conn


def get_employee(request: Request, conn):
    badge = request.session.get("badge_id")
    if not badge:
        return None
    return conn.execute(
        "SELECT * FROM employees WHERE badge_id=? AND active=1", (badge,)
    ).fetchone()


def require_admin(request: Request, conn=Depends(_request_conn)):
    emp = get_employee(request, conn)
    if emp is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    if not emp["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return emp


def auth_router(get_conn) -> APIRouter:
    r = APIRouter()

    @r.post("/login")
    def login(request: Request, body: dict, conn=Depends(get_conn)):
        badge = str(body.get("badgeId", "")).strip()
        emp = None
        if badge:
            emp = conn.execute(
                "SELECT * FROM employees WHERE badge_id=? AND active=1", (badge,)
            ).fetchone()
        if emp is None:
            raise HTTPException(status_code=401, detail="Unknown or inactive employee ID")
        request.session["badge_id"] = emp["badge_id"]
        request.session["name"] = emp["name"]
        return {"badgeId": emp["badge_id"], "name": emp["name"], "isAdmin": bool(emp["is_admin"])}

    @r.post("/logout")
    def logout(request: Request):
        request.session.clear()
        return {"ok": True}

    @r.get("/me")
    def me(request: Request, conn=Depends(get_conn)):
        emp = get_employee(request, conn)
        if emp is None:
            raise HTTPException(status_code=401, detail="Not logged in")
        return {"badgeId": emp["badge_id"], "name": emp["name"], "isAdmin": bool(emp["is_admin"])}

    return r
