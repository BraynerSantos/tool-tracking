"""Admin/auxiliary endpoints — port of tool_db2's ``server/routes/admin.js``.

``config_router`` is the public ``GET /api/config``; ``admin_router`` carries
the CSV export (any logged-in user) and the SQLite backup download
(admin-only, gated per-route). Export lets ``build_tool_query``'s
``HTTPException 400`` for bad filters propagate.
"""

import json
import shutil
import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from app.auth import require_admin
from app.backup import backup_to
from app.csv_export import to_csv
from app.search import build_tool_query


def config_router(get_conn, config) -> APIRouter:
    r = APIRouter()

    @r.get("/config")
    def get_config():
        return {"companyName": config.company_name}

    return r


def admin_router(get_conn) -> APIRouter:
    r = APIRouter()

    @r.get("/export.csv")
    def export_csv(request: Request, conn=Depends(get_conn)):
        qp = request.query_params
        result = build_tool_query(
            conn,
            q=qp.get("q"),
            type_id=qp.get("typeId"),
            department_id=qp.get("departmentId"),
            location_id=qp.get("locationId"),
        )
        rows, locations_by_tool = result["rows"], result["locations_by_tool"]

        schemas = {t["name"]: json.loads(t["attribute_schema"]) for t in
                   conn.execute("SELECT name, attribute_schema FROM tool_types")}
        attr_fields = []  # first-seen order across the result set
        for row in rows:
            schema = schemas.get(row["typeName"]) or []
            for f in schema:
                # JS parity: only undefined (missing key) and '' are skipped
                if f["key"] in row["attributes"] and row["attributes"][f["key"]] != "" \
                        and not any(a["key"] == f["key"] for a in attr_fields):
                    attr_fields.append(f)

        headers = ["Name", "Description", "Type", "Total Qty", "Locations",
                   *(f["label"] for f in attr_fields)]
        csv_rows = [[
            row["name"], row["description"], row["typeName"], row["totalQty"],
            "; ".join(f"{l['departmentName']} - {l['locationName']}: {l['quantity']}"
                      for l in locations_by_tool.get(str(row["id"])) or []),
            *(row["attributes"].get(f["key"], "") for f in attr_fields),
        ] for row in rows]

        csv = to_csv(headers, csv_rows)
        return Response(content=csv, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition":
                                 'attachment; filename="tools-export.csv"'})

    @r.get("/backup", dependencies=[Depends(require_admin)])
    def backup(conn=Depends(get_conn)):
        db_path = conn.execute("PRAGMA database_list").fetchone()[2]
        tmp_dir = Path(tempfile.mkdtemp(prefix="tooldb-backup-"))
        target = tmp_dir / "backup.sqlite"
        backup_to(db_path, target)
        filename = f"tooldb-backup-{date.today().isoformat()}.sqlite"
        # Sweep the temp dir after the response body is streamed (starlette
        # runs background tasks once the response finishes).
        return FileResponse(target, media_type="application/x-sqlite3",
                            filename=filename,
                            background=BackgroundTask(shutil.rmtree, tmp_dir, True))

    return r
