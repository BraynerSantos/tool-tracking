import sys

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse

from app.auth import auth_router, require_admin, require_user
from app.config import AppConfig, load_config
from app.routers import admin, departments, employees, tool_types, tools
from app.db import connect, seed_defaults


def create_app(config: AppConfig) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=config.session_secret, same_site="lax")

    conn = connect(config.db_path)
    seed_defaults(conn)
    app.state.conn = conn  # single connection per app; routers get it via Depends(get_conn)

    def get_conn():
        return conn

    # Render HTTPException as {"error": detail} to match the Node API body shape.
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        content = {"error": exc.detail} if isinstance(exc.detail, str) else exc.detail
        return JSONResponse(status_code=exc.status_code, content=content)

    app.include_router(auth_router(get_conn), prefix="/api")
    app.include_router(admin.config_router(get_conn, config), prefix="/api")  # public
    # CSV export open to any logged-in user; backup admin-gated per-route
    app.include_router(admin.admin_router(get_conn), prefix="/api",
                       dependencies=[Depends(require_user)])
    app.include_router(employees.lookup_router(get_conn), prefix="/api")  # public
    app.include_router(employees.employees_router(get_conn), prefix="/api",
                       dependencies=[Depends(require_admin)])  # admin-only
    # reads open to any logged-in user; writes are admin-gated per-route
    app.include_router(departments.departments_router(get_conn), prefix="/api",
                       dependencies=[Depends(require_user)])
    # reads open to any logged-in user; writes are admin-gated per-route
    app.include_router(tool_types.tool_types_router(get_conn), prefix="/api",
                       dependencies=[Depends(require_user)])
    # reads AND writes open to any logged-in user (matches the Node app)
    app.include_router(tools.tools_router(get_conn), prefix="/api",
                       dependencies=[Depends(require_user)])

    @app.get("/api/health")
    def health():
        return {"ok": True}

    # Serve the built React UI when it exists (registered after all /api routes,
    # so /api/* matches first). The catch-all falls back to index.html for deep
    # links but never swallows /api misses — those stay JSON 404s.
    dist = config.base_dir / "client" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
        index = dist / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app


if __name__ == "__main__" or getattr(sys, "frozen", False):
    from app.backup import run_auto_backup_daily

    config = load_config()
    application = create_app(config)
    run_auto_backup_daily(config)  # daemon thread; entry block only
    uvicorn.run(app=application, host="0.0.0.0", port=config.port)
