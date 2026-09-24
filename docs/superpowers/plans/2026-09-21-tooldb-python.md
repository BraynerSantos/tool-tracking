# Tool DB Python (tooldb-py) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the tool-tracking backend in Python (FastAPI), byte-compatible with the Node API, packaged as a PyInstaller onedir executable with a config file (database path, port, company name, auto-backup dir), admin roles, and an improved attribute editor.

**Architecture:** FastAPI app serving the existing React bundle + JSON API, stdlib `sqlite3` with the same schema, signed-cookie sessions, config.ini next to the executable. Behavior is ported verbatim from the tested Node implementation in `E:\Desktop\Project_files\tool_db2\server\` (source of truth); the ported pytest suite is the acceptance bar. New code (config, roles, auto-backup, packaging) is specified in full below.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, starlette SessionMiddleware (itsdangerous), pytest, PyInstaller (onedir). sqlite3/configparser/threads from stdlib.

**Spec:** `docs/superpowers/specs/2026-09-21-tooldb-python-design.md` (copy into the new repo in Task 1)

## Global Constraints

- **API byte-compatibility with the Node version**: same routes (`/api/...`), same JSON key names (camelCase in responses: `badgeId`, `toolTypeId`, `attributeSchema`, `totalQty`, `locationsByTool`, `reorderMin`, `isAdmin`), same status codes (400/401/403/404/409/500 semantics), same error body shape `{"error": "..."}` (+ `{"fields": {...}}` on attribute validation).
- **Port, don't redesign**: behavior comes from `E:\Desktop\Project_files\tool_db2\server\*.js` and `client/src/` — read them; where this plan shows exact code, use it verbatim.
- Roles: tools CRUD/search/export = any logged-in employee; employees, departments/locations, tool-types mutations, and backup = **admin only (403 otherwise)**; reads of departments/tool-types stay available to all logged-in users (search + add-tool forms need them); employees list is admin-only.
- Last-admin guard: cannot demote or deactivate the last active admin (409).
- Number attributes: finite numbers and decimal strings (`0.250`, `6.35`) accepted and stored as numbers; junk/whitespace/other types rejected with per-field error "Must be a number".
- Search: `q` LIKE-escaped (`\`, `%`, `_`, `ESCAPE '\'`), matches name/description/attribute values; numeric filters validated (non-negative integer or 400).
- Config: INI with sections `[General]` (CompanyName, Port), `[Database]` (DatabasePath), `[Backup]` (BackupDir); created with defaults on first run next to the exe (dev: repo root); relative DatabasePath resolves against the exe/repo dir.
- Auto-backup: daily dated copy when BackupDir set, keep last 30; only when launched via the real entry point (never during tests).
- Tests: pytest, one temp DB per test, no network — FastAPI TestClient only; auto-backup thread never runs in tests.
- Windows-first: pure stdlib + wheels only (PyInstaller-friendly); paths via `pathlib`.

## File Structure (new repo `E:\Desktop\Project_files\tooldb-py`)

```
client/                    — copied verbatim from tool_db2 (Task 1); modified in Task 13
app/
  __init__.py
  config.py                — AppConfig: load/create config.ini, base dir resolution
  db.py                    — connect(), SCHEMA, seed_defaults(), log_action()
  validation.py            — validate_schema(), validate_attributes()  (port of server/validation.js)
  search.py                — escape_like(), build_tool_query()          (port of server/search.js)
  csv_export.py            — to_csv()                                   (port of server/csv.js)
  backup.py                — backup_to(), auto_backup_loop()            (new)
  auth.py                  — session secret resolution + auth router
  routers/
    __init__.py
    employees.py           — public lookup router + admin-only employees router
    departments.py         — departments/locations (reads open, writes admin)
    tool_types.py          — tool types (reads open, writes admin)
    tools.py               — tools CRUD/search/export-adjacent (all logged-in)
    admin.py               — /api/config, /api/export.csv, /api/backup (admin)
  main.py                  — create_app(config), static+SPA, entry point with auto-backup
tests/
  conftest.py              — client fixtures (temp DB, logged-in admin + non-admin)
  test_config.py test_db.py test_validation.py test_auth.py test_employees.py
  test_departments.py test_tool_types.py test_tools.py test_search.py
  test_export.py test_autobackup.py
build_exe.bat              — npm build + pyinstaller
tooldb.spec                — PyInstaller spec (onedir)
requirements.txt requirements-dev.txt README.md .gitignore
```

**Execution-time note for the controller:** the plan file and spec are committed in tool_db2's `docs/`; Task 1 copies them into the new repo. Dispatch briefs reference this plan file path in tool_db2.

---

### Task 1: New repo scaffold — copy sources, deps, app skeleton, test harness

**Files:**
- Create: `E:\Desktop\Project_files\tooldb-py\` with git repo, `client/` (copied), `app/__init__.py`, `app/main.py`, `tests/conftest.py`, `tests/test_health.py`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `README.md` (placeholder), plus copies of the spec and this plan into `docs/superpowers/`.

**Interfaces:**
- Produces: `create_app(config: AppConfig) -> FastAPI` (extended over later tasks); `tests/conftest.py` fixtures `admin_client` (logged-in, is_admin=1, badge E100), `user_client` (logged-in, is_admin=0, badge E200), `engine` (path to temp sqlite file) — later tasks reuse these exact names. `GET /api/health` → `{"ok": true}`.

- [ ] **Step 1: Create the repo**

```bash
mkdir "E:/Desktop/Project_files/tooldb-py" && cd "E:/Desktop/Project_files/tooldb-py"
git init -b master
mkdir -p app/routers tests docs/superpowers/specs docs/superpowers/plans
cp "E:/Desktop/Project_files/tool_db2/docs/superpowers/specs/2026-09-21-tooldb-python-design.md" docs/superpowers/specs/
cp "E:/Desktop/Project_files/tool_db2/docs/superpowers/plans/2026-09-21-tooldb-python.md" docs/superpowers/plans/
cp -r "E:/Desktop/Project_files/tool_db2/client" client
rm -rf client/node_modules client/dist
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
node_modules/
client/dist/
data/
dist/
build/
*.sqlite
session-secret
config.ini
```

`requirements.txt`:
```
fastapi>=0.111
uvicorn>=0.30
itsdangerous>=2.0
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.0
httpx>=0.27
pyinstaller>=6.9
```

`README.md` (placeholder, replaced in Task 14): `# Tool DB (Python)\n\nSee docs/superpowers/specs/.`

Python deps (run from the repo): `python -m venv .venv` then `.venv/Scripts/pip install -r requirements-dev.txt` (Windows). All later commands assume the venv is active or use `.venv/Scripts/python -m pytest`.

- [ ] **Step 2: Write failing test** — `tests/test_health.py`:
```python
def test_health(admin_client):
    res = admin_client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
```

`tests/conftest.py`:
```python
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.config import AppConfig
from app.main import create_app
from app.db import connect, seed_defaults

@pytest.fixture()
def engine(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = connect(db_path)
    seed_defaults(conn)
    conn.close()
    return db_path

def make_client(engine, badge, is_admin, secret="test-secret"):
    config = AppConfig(base_dir=engine.parent, db_path=engine, port=3000,
                       company_name="Tool DB", backup_dir=None, session_secret=secret)
    app = create_app(config)
    client = TestClient(app)
    if badge:
        res = client.post("/api/login", json={"badgeId": badge})
        assert res.status_code == 200
    return client

@pytest.fixture()
def admin_client(engine):
    return make_client(engine, "E100", True)

@pytest.fixture()
def user_client(engine):
    return make_client(engine, "E200", False)

@pytest.fixture()
def anon_client(engine):
    return make_client(engine, None, False)

@pytest.fixture()
def conn(engine):
    c = connect(engine)
    yield c
    c.close()
```

- [ ] **Step 3: Implement minimal `app/config.py`** (full implementation — final):
```python
import configparser
from dataclasses import dataclass
import sys
from pathlib import Path

DEFAULT_COMPANY = "Tool DB"
DEFAULT_PORT = 3000

def base_dir() -> Path:
    """Folder the exe lives in (frozen) or the repo root (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

@dataclass
class AppConfig:
    base_dir: Path
    db_path: Path
    port: int
    company_name: str
    backup_dir: Path | None
    session_secret: str

def _resolve(p: str, root: Path) -> Path:
    path = Path(p).expanduser()
    return path if path.is_absolute() else (root / path)

def load_config(base: Path | None = None) -> AppConfig:
    """Load config.ini from `base` (default: exe/repo dir), creating it with defaults."""
    root = base if base is not None else base_dir()
    ini_path = root / "config.ini"
    parser = configparser.ConfigParser()
    if not ini_path.exists():
        parser["General"] = {"CompanyName": DEFAULT_COMPANY, "Port": str(DEFAULT_PORT)}
        parser["Database"] = {"DatabasePath": "tooldb.sqlite"}
        parser["Backup"] = {"BackupDir": ""}
        with ini_path.open("w", encoding="utf-8") as f:
            parser.write(f)
    parser.read(ini_path, encoding="utf-8")
    db_path = _resolve(parser["Database"]["DatabasePath"], root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_raw = parser["Backup"].get("BackupDir", "").strip()
    return AppConfig(
        base_dir=root,
        db_path=db_path,
        port=parser["General"].getint("Port", fallback=DEFAULT_PORT),
        company_name=parser["General"].get("CompanyName", fallback=DEFAULT_COMPANY),
        backup_dir=_resolve(backup_raw, root) if backup_raw else None,
        session_secret=_load_or_create_secret(root),
    )

def _load_or_create_secret(root: Path) -> str:
    import secrets
    secret_file = root / "session-secret"
    if secret_file.exists():
        text = secret_file.read_text(encoding="utf-8").strip()
        if text:
            return text
    secret = secrets.token_hex(32)
    secret_file.write_text(secret, encoding="utf-8")
    return secret
```

Minimal `app/main.py` (extended in Task 2+; final assembly in Task 12):
```python
from fastapi import FastAPI
from app.config import AppConfig

def create_app(config: AppConfig) -> FastAPI:
    app = FastAPI()
    @app.get("/api/health")
    def health():
        return {"ok": True}
    return app
```

Empty `app/__init__.py`, `app/routers/__init__.py`, `tests/__init__.py` not needed (pytest rootdir). Create `app/__init__.py` and `app/routers/__init__.py` as empty files.

- [ ] **Step 4: Run tests** — `.venv/Scripts/python -m pytest -q` → health test FAILS (SessionMiddleware not configured yet makes login 500 in conftest; acceptable interim: implement `create_app` with SessionMiddleware immediately using `config.session_secret`):
```python
from starlette.middleware.sessions import SessionMiddleware
# inside create_app, first line:
app.add_middleware(SessionMiddleware, secret_key=config.session_secret, same_site="lax")
```
Then health passes and login succeeds (404 for /api/login is fine at this stage — conftest asserts 200, so add the auth router now? No: change conftest's login assert to `in (200, 404)` is NOT allowed (fixture contract). Instead Task 1 ships a trivial auth router stub:)

`app/auth.py`:
```python
from fastapi import APIRouter, Request

def auth_router(config) -> APIRouter:
    r = APIRouter()
    @r.post("/login")
    def login(request: Request, body: dict):
        return {"badgeId": "", "name": "", "isAdmin": False}  # stub, replaced in Task 4
    return r
```
Mount in `create_app`: `app.include_router(auth_router(config), prefix="/api")`. Conftest login then returns 200 with empty session (fixtures work; Task 4 replaces the stub and conftest gains seeded employees).

**Adjustment to conftest (final form now):** `make_client` also inserts the two employees directly:
```python
def make_client(engine, badge, is_admin, secret="test-secret"):
    c = sqlite3.connect(engine)
    c.execute("INSERT OR IGNORE INTO employees (badge_id, name, is_admin) VALUES (?, ?, ?)",
              ("E100", "Admin User", 1))
    c.execute("INSERT OR IGNORE INTO employees (badge_id, name, is_admin) VALUES (?, ?, ?)",
              ("E200", "Regular User", 0))
    c.commit(); c.close()
    ...
```
(This requires the schema — so Step 4 order is: write db.py schema below, then conftest works.)

`app/db.py` (schema now, seed/log in Task 2 — include both now to keep conftest valid):
```python
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
  badge_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  is_admin INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS departments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS locations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  department_id INTEGER NOT NULL REFERENCES departments(id),
  name TEXT NOT NULL,
  UNIQUE (department_id, name)
);
CREATE TABLE IF NOT EXISTS tool_types (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  attribute_schema TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS tools (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  tool_type_id INTEGER NOT NULL REFERENCES tool_types(id),
  attributes TEXT NOT NULL DEFAULT '{}',
  notes TEXT NOT NULL DEFAULT '',
  reorder_min INTEGER
);
CREATE TABLE IF NOT EXISTS inventory (
  tool_id INTEGER NOT NULL REFERENCES tools(id),
  location_id INTEGER NOT NULL REFERENCES locations(id),
  quantity INTEGER NOT NULL CHECK (quantity >= 0),
  PRIMARY KEY (tool_id, location_id)
);
CREATE TABLE IF NOT EXISTS activity_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL DEFAULT (datetime('now')),
  badge_id TEXT NOT NULL,
  action TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id TEXT NOT NULL DEFAULT '',
  details TEXT NOT NULL DEFAULT ''
);
"""

def connect(db_path) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn

SEED_TOOL_TYPES = [
    ("Cutting tools", [
        {"key": "diameter_mm", "label": "Diameter (mm)", "type": "number"},
        {"key": "flute_count", "label": "Flutes", "type": "number"},
        {"key": "shank_mm", "label": "Shank (mm)", "type": "number"},
        {"key": "corner_radius_mm", "label": "Corner radius (mm)", "type": "number"},
        {"key": "coating", "label": "Coating", "type": "text"},
        {"key": "material", "label": "Material", "type": "text"}]),
    ("Holders & workholding", [
        {"key": "taper_type", "label": "Taper type", "type": "text"},
        {"key": "bore_mm", "label": "Bore (mm)", "type": "number"},
        {"key": "capacity_mm", "label": "Capacity (mm)", "type": "number"},
        {"key": "jaw_type", "label": "Jaw type", "type": "text"}]),
    ("Grinding/diamond tools", [
        {"key": "grit", "label": "Grit", "type": "number"},
        {"key": "bond_type", "label": "Bond type", "type": "text"},
        {"key": "diameter_mm", "label": "Diameter (mm)", "type": "number"},
        {"key": "profile", "label": "Profile", "type": "text"}]),
    ("Measuring tools", [
        {"key": "range", "label": "Range", "type": "text"},
        {"key": "resolution", "label": "Resolution", "type": "text"},
        {"key": "calibration_due", "label": "Calibration due", "type": "text"}]),
]

def seed_defaults(conn: sqlite3.Connection) -> None:
    for name, schema in SEED_TOOL_TYPES:
        conn.execute("INSERT OR IGNORE INTO tool_types (name, attribute_schema) VALUES (?, ?)",
                     (name, json.dumps(schema)))
    if conn.execute("SELECT COUNT(*) c FROM employees").fetchone()["c"] == 0:
        conn.execute("INSERT INTO employees (badge_id, name, active, is_admin) VALUES ('ADMIN', 'Administrator', 1, 1)")
    conn.commit()

def log_action(conn, badge_id, action, entity, entity_id, details=""):
    conn.execute("INSERT INTO activity_log (badge_id, action, entity, entity_id, details) VALUES (?,?,?,?,?)",
                 (badge_id, action, entity, str(entity_id ?? ""), details))
    conn.commit()
```
(`import json` at top. `str(entity_id ?? "")` is pseudocode — write `str(entity_id if entity_id is not None else "")`.)

- [ ] **Step 5: Run tests, verify PASS** — `.venv/Scripts/python -m pytest -q` → 1 passed.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "chore: scaffold tooldb-py with FastAPI skeleton, schema, test fixtures"`

> **Task 1 note:** Task 1 is intentionally fat — scaffold tasks fold into the deliverable that needs them (per plan task-sizing), so config.py/db.py/auth-stub/conftest land there to make the test harness real.

---

### Task 2: Config — load/create config.ini, defaults, resolution, session secret

**Files:**
- Test: `tests/test_config.py`
- Modify: `app/config.py` (already implemented in Task 1 — this task adds the tests that pin it; fix code only if a test fails)

**Interfaces:**
- Consumes: `load_config(base: Path | None) -> AppConfig`, `AppConfig(base_dir, db_path, port, company_name, backup_dir, session_secret)`, `base_dir()`.
- Produces: pinned behavior — missing config.ini is created with defaults (`CompanyName=Tool DB`, `Port=3000`, `DatabasePath=tooldb.sqlite`, empty BackupDir); relative DatabasePath resolves against base; absolute honored; missing DB parent dirs created; session-secret file created when absent, reused when present.

- [ ] **Step 1: Write tests** — `tests/test_config.py`:
```python
from app.config import load_config

def test_creates_defaults(tmp_path):
    config = load_config(tmp_path)
    assert config.company_name == "Tool DB"
    assert config.port == 3000
    assert config.db_path == tmp_path / "tooldb.sqlite"
    assert config.backup_dir is None
    assert (tmp_path / "config.ini").exists()
    assert config.db_path.parent.exists()

def test_reads_existing_values(tmp_path):
    (tmp_path / "config.ini").write_text(
        "[General]\nCompanyName = Acme Ceramics\nPort = 8080\n"
        "[Database]\nDatabasePath = D:\\Data\\tools.sqlite\n"
        "[Backup]\nBackupDir = backups\n", encoding="utf-8")
    config = load_config(tmp_path)
    assert config.company_name == "Acme Ceramics"
    assert config.port == 8080
    assert config.db_path == Path("D:/Data/tools.sqlite")
    assert config.backup_dir == tmp_path / "backups"
    assert (tmp_path / "backups").exists() is False  # backup dir not auto-created

def test_relative_db_path_resolves_against_base(tmp_path):
    (tmp_path / "config.ini").write_text(
        "[General]\nPort = 3000\n[Database]\nDatabasePath = data\\db.sqlite\n[Backup]\nBackupDir =\n",
        encoding="utf-8")
    config = load_config(tmp_path)
    assert config.db_path == tmp_path / "data" / "db.sqlite"
    assert (tmp_path / "data").exists()  # parent created

def test_session_secret_persisted_and_reused(tmp_path):
    first = load_config(tmp_path)
    again = load_config(tmp_path)
    assert first.session_secret == again.session_secret
    assert len(first.session_secret) >= 32
```

- [ ] **Step 2: Run** — `python -m pytest tests/test_config.py -q` → should PASS (Task 1 code); fix `app/config.py` if any fail (do not change the documented behavior).

- [ ] **Step 3: Commit** — `git commit -am "test: pin config loading behavior"`

---

### Task 3: Auth — real login/logout/me with roles

**Files:**
- Modify: `app/auth.py` (replace stub), `app/main.py` (mount)
- Test: `tests/test_auth.py`

**Interfaces:**
- Produces: `POST /api/login {badgeId}` → 200 `{badgeId, name, isAdmin}` | 401 `{"error": "Unknown or inactive employee ID"}` (session stores `badge_id`); `POST /api/logout` → `{ok: true}`; `GET /api/me` → `{badgeId, name, isAdmin}` | 401; `require_user(request)` dependency (raises 401 `{"error": "Not logged in"}`); `require_admin(request)` dependency (401 if not logged in, 403 `{"error": "Admin access required"}` if `is_admin=0`).
- Produces (for later tasks): `current_employee(request, conn) -> sqlite3.Row | None` helper reading `request.session.get("badge_id")`.

- [ ] **Step 1: Write failing tests** — `tests/test_auth.py`:
```python
def test_login_success_sets_session(admin_client):
    res = admin_client.post("/api/login", json={"badgeId": "E100"})
    assert res.status_code == 200
    assert res.json() == {"badgeId": "E100", "name": "Admin User", "isAdmin": True}

def test_login_rejects_unknown_and_inactive(anon_client, conn):
    assert anon_client.post("/api/login", json={"badgeId": "NOPE"}).status_code == 401
    conn.execute("UPDATE employees SET active=0 WHERE badge_id='E200'"); conn.commit()
    res = anon_client.post("/api/login", json={"badgeId": "E200"})
    assert res.status_code == 401

def test_me_and_logout(admin_client, anon_client):
    me = admin_client.get("/api/me").json()
    assert me == {"badgeId": "E100", "name": "Admin User", "isAdmin": True}
    admin_client.post("/api/logout")
    assert admin_client.get("/api/me").status_code == 401
    assert anon_client.get("/api/me").status_code == 401

def test_role_dependencies(anon_client, user_client, admin_client, conn):
    conn.execute("INSERT INTO departments (name) VALUES ('D')"); conn.commit()
    # require_user probe route:
    assert user_client.get("/api/departments").status_code == 200
    assert anon_client.get("/api/departments").status_code == 401
    # require_admin probe route (employees list is admin-only):
    assert admin_client.get("/api/employees").status_code == 200
    assert user_client.get("/api/employees").status_code == 403
    assert anon_client.get("/api/employees").status_code == 401
```
(The `/api/departments` and `/api/employees` routes don't exist yet — this test pins the dependency contract and goes green in Tasks 6–7. To keep the suite green per-task, put the two role-probe assertions in a dedicated test marked with `@pytest.mark.xfail(strict=False, reason="routes arrive in Tasks 6-7")`… NO — instead: keep only `/api/me`-related tests in this file and move the dependency-probe assertions into Tasks 6/7 tests. Final rule: this task's test file contains only login/logout/me tests.)

- [ ] **Step 2: Run, verify FAIL** (stub login returns empty dict).

- [ ] **Step 3: Implement `app/auth.py`** (final):
```python
from fastapi import APIRouter, Request
from app.db import log_action

def require_user(request: Request):
    if not request.session.get("badge_id"):
        raise HTTPException(status_code=401, detail="Not logged in")

def get_employee(request: Request, conn):
    badge = request.session.get("badge_id")
    if not badge:
        return None
    return conn.execute("SELECT * FROM employees WHERE badge_id=? AND active=1", (badge,)).fetchone()

def require_admin(request: Request, conn):
    emp = get_employee(request, conn)
    if emp is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    if not emp["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return emp
```
(`from fastapi import HTTPException` at top.) Router:
```python
def auth_router(conn) -> APIRouter:
    r = APIRouter()
    @r.post("/login")
    def login(request: Request, body: dict):
        badge = str(body.get("badgeId", "")).strip()
        emp = None
        if badge:
            emp = conn.execute("SELECT * FROM employees WHERE badge_id=? AND active=1", (badge,)).fetchone()
        if emp is None:
            raise HTTPException(status_code=401, detail="Unknown or inactive employee ID")
        request.session["badge_id"] = emp["badge_id"]
        return {"badgeId": emp["badge_id"], "name": emp["name"], "isAdmin": bool(emp["is_admin"])}

    @r.post("/logout")
    def logout(request: Request):
        request.session.clear()
        return {"ok": True}

    @r.get("/me")
    def me(request: Request):
        emp = get_employee(request, conn)
        if emp is None:
            raise HTTPException(status_code=401, detail="Not logged in")
        return {"badgeId": emp["badge_id"], "name": emp["name"], "isAdmin": bool(emp["is_admin"])}
    return r
```
DB dependency: `app/main.py` holds one module-level connection per app via `conn_dependency`:
```python
def create_app(config: AppConfig) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=config.session_secret, same_site="lax")
    conn = connect(config.db_path)
    seed_defaults(conn)
    def get_conn():
        return conn
    app.include_router(auth_router(get_conn), prefix="/api")
    @app.get("/api/health")
    def health(): return {"ok": True}
    return app
```
Later tasks follow the same pattern: each router factory takes `get_conn` (and uses `Depends`).

HTTPException detail renders as `{"detail": "..."}` — to match the Node body `{"error": "..."}` EXACTLY, add an exception handler in `create_app`:
```python
from fastapi.exceptions import RequestValidationError
@app.exception_handler(HTTPException)
async def http_exception(request, exc):
    return JSONResponse(status_code=exc.status_code,
                        content={"error": exc.detail} if isinstance(exc.detail, str) else exc.detail)
```
(For attribute validation errors routers return `JSONResponse` directly with `{"error": ..., "fields": {...}}`.)

- [ ] **Step 4: Run** — `python -m pytest tests/test_auth.py tests/test_health.py tests/test_config.py -q` → green.

- [ ] **Step 5: Commit** — `git commit -am "feat: login/logout/me with roles and error-shape handler"`

---

### Task 4: Validation module — port with decimal guarantees

**Files:**
- Create: `app/validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Produces: `validate_schema(schema: list) -> str | None` (None = valid); `validate_attributes(schema: list, attrs: dict) -> dict` = `{"ok": True, "clean": {...}}` or `{"ok": False, "errors": {key: "Must be a number"}}`.
- Behavior pinned by tests: schema = list of `{key: nonempty str, label: nonempty str, type: 'text'|'number'}`, unique keys; numbers accept int/float and numeric strings (trimmed, incl. `' 6.35 '` → 6.35, `'0.250'` → 0.25), reject `''`/`'   '`/`'wide'`/`[]`/`{}`/`None`/`NaN`/`Infinity`/bools; text coerced via `str(value ?? '')`; unknown keys stripped; missing fields skipped. **Decimal tests are mandatory** (`0.250`, `6.35`, `' 0.5 '`).

- [ ] **Step 1: Write tests** — `tests/test_validation.py` (port assertions 1:1 from `E:\Desktop\Project_files\tool_db2\tests\validation.test.js`, plus):
```python
import math
from app.validation import validate_schema, validate_attributes

SCHEMA = [{"key": "diameter_mm", "label": "Diameter (mm)", "type": "number"},
          {"key": "coating", "label": "Coating", "type": "text"}]

def test_decimal_values_accepted():
    r = validate_attributes(SCHEMA, {"diameter_mm": "0.250"})
    assert r == {"ok": True, "clean": {"diameter_mm": 0.25}}
    r = validate_attributes(SCHEMA, {"diameter_mm": " 6.35 "})
    assert r["clean"]["diameter_mm"] == 6.35
    r = validate_attributes(SCHEMA, {"diameter_mm": 0.5})
    assert r["clean"]["diameter_mm"] == 0.5

def test_junk_rejected():
    for junk in ["", "   ", "wide", [], {}, None, math.nan, math.inf, True]:
        assert validate_attributes(SCHEMA, {"diameter_mm": junk})["ok"] is False

def test_unknown_keys_stripped_and_text_coerced():
    r = validate_attributes(SCHEMA, {"coating": "TiAlN", "hack": "x", "diameter_mm": "6"})
    assert r == {"ok": True, "clean": {"diameter_mm": 6.0, "coating": "TiAlN"}}
```
Plus the schema tests ported from the Node test file (valid → None; non-array → error mentioning array; empty key/label → error; bad type → error; duplicate keys → error; missing fields allowed; blank text allowed).

- [ ] **Step 2: Run, verify FAIL** (module missing).

- [ ] **Step 3: Implement `app/validation.py`** — port `server/validation.js` faithfully:
```python
import math

def validate_schema(schema):
    if not isinstance(schema, list):
        return "Attribute schema must be an array"
    seen = set()
    for f in schema:
        if not isinstance(f, dict): return "Attribute schema must be an array"
        key = f.get("key"); label = f.get("label"); ftype = f.get("type")
        if not isinstance(key, str) or not key.strip(): return "Every attribute needs a key"
        if not isinstance(label, str) or not label.strip(): return "Every attribute needs a label"
        if ftype not in ("text", "number"): return f'Attribute "{key}" has invalid type (use text or number)'
        if key in seen: return f'Duplicate attribute key "{key}"'
        seen.add(key)
    return None

def _to_number(raw):
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if not s: return None
        raw = s
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None

def validate_attributes(schema, attrs):
    source = attrs if isinstance(attrs, dict) else {}
    clean, errors = {}, {}
    for f in schema:
        if f["key"] not in source: continue
        raw = source[f["key"]]
        if f["type"] == "number":
            n = _to_number(raw)
            if n is None:
                errors[f["key"]] = "Must be a number"; continue
            clean[f["key"]] = int(n) if float(n).is_integer() and abs(n) < 1e15 else n
        else:
            clean[f["key"]] = "" if raw is None else str(raw)
    return {"ok": False, "errors": errors} if errors else {"ok": True, "clean": clean}
```
(Rationale for int-ifying whole numbers: JSON `6.0` vs `6` — Node stored what JS Number gave; either is byte-fine, but int keeps payloads tidy. Keep this rule.)

- [ ] **Step 4: Run** — full suite green. **Step 5: Commit** — `git commit -am "feat: attribute validation with decimal number support"`

---

### Task 5: Employees — public lookup + admin-only management with roles

**Files:**
- Create: `app/routers/employees.py`
- Test: `tests/test_employees.py`
- Modify: `app/main.py` (mount both routers)

**Interfaces:**
- Consumes: `get_conn` dependency, `require_admin` (Task 3), `escape_like` (Task 8 — not yet available; implement a local `_escape_like` in this router now, replace with the shared one in Task 8. To avoid the double implementation entirely: create `app/search.py` NOW containing only `escape_like` (final code in Task 9), and import it here).
- Produces: **public** `GET /api/employee-lookup?q=` (no auth; trimmed q < 2 → `[]`; max 5 active, LIKE-escaped match on name/badge_id; returns `[{badgeId, name, isAdmin}]`); **admin-only** `GET /api/employees?q=` → `[{badgeId, name, active, isAdmin}]` (active first, then badge_id); `POST /api/employees {badgeId, name}` (400 missing / 409 dup); `POST /api/employees/import {rows: [{badgeId, name}]}` → `{imported, skipped}` (transactional upsert: new insert; same badge different name → rename+reactivate counts imported; same badge same name → skipped; invalid rows skipped; audit `import`); `PATCH /api/employees/{badge_id} {active?, isAdmin?}` — booleans required per-field (accept `true/1/false/0`, reject other values with 400 `{"error": "active must be a boolean"}` / `"isAdmin must be a boolean"`); **last-admin guard**: deactivating or demoting what would leave zero active admins → 409 `{"error": "Cannot remove the last active admin"}`; audit all mutations.

- [ ] **Step 1: Create `app/search.py` with just `escape_like`** (final):
```python
def escape_like(s: str) -> str:
    return "".join("\\" + ch if ch in "\\%_" else ch for ch in s)
```

- [ ] **Step 2: Write failing tests** — `tests/test_employees.py` (port from `E:\Desktop\Project_files\tool_db2\tests\employees.test.js`, with these deltas):
- All management calls use `admin_client`; add role checks: `user_client.post("/api/employees", ...)` → 403, `user_client.get("/api/employees")` → 403.
- Lookup tests (public, via `anon_client`): seeded E100 has `"isAdmin": True`, E200 `False`; `q=E` → `[]`; `q=%20` (space) → `[]`; no q → `[]`; `q=E1%` literal-match only; cap: insert 6 active 'Extra Person N' with badge X1..X6 (via `conn`), `q=Extra` → exactly 5, keys `== {"badgeId","name","isAdmin"}`.
- Import: upsert counting identical to Node (badge same + name same → skipped; same badge new name → renamed+reactivated, counted imported); duplicate badge in DB with same name → skipped.
- New role tests:
```python
def test_promote_and_demote(admin_client, user_client, conn):
    res = admin_client.patch("/api/employees/E200", json={"isAdmin": True})
    assert res.status_code == 200 and res.json()["isAdmin"] is True
    assert conn.execute("SELECT is_admin FROM employees WHERE badge_id='E200'").fetchone()[0] == 1
    res = admin_client.patch("/api/employees/E200", json={"isAdmin": False})
    assert res.status_code == 200 and res.json()["isAdmin"] is False

def test_last_admin_guard(admin_client, conn):
    # only active admin is E100
    assert admin_client.patch("/api/employees/E100", json={"isAdmin": False}).status_code == 409
    assert admin_client.patch("/api/employees/E100", json={"active": False}).status_code == 409
    # with a second active admin, demotion works
    conn.execute("INSERT INTO employees (badge_id, name, active, is_admin) VALUES ('E900', 'Second', 1, 1)")
    conn.commit()
    assert admin_client.patch("/api/employees/E100", json={"isAdmin": False}).status_code == 200

def test_patch_type_validation(admin_client, conn):
    assert admin_client.patch("/api/employees/E200", json={}).status_code == 400
    assert admin_client.patch("/api/employees/E200", json={"active": "false"}).status_code == 400
    assert admin_client.patch("/api/employees/E200", json={"isAdmin": "yes"}).status_code == 400
    assert conn.execute("SELECT is_admin FROM employees WHERE badge_id='E200'").fetchone()[0] == 0
```

- [ ] **Step 3: Run, verify FAIL**, then **Step 4: Implement `app/routers/employees.py`** — port `server/routes/employees.js` 1:1 with the deltas above. Key port notes (SQL and logic identical; adapt only syntax):
- Row → JSON: `{"badgeId": r["badge_id"], "name": r["name"], "active": r["active"], "isAdmin": bool(r["is_admin"])}`; lookup rows `{"badgeId", "name", "isAdmin"}`.
- Lookup query: `WHERE active=1 AND (name LIKE ? ESCAPE '\' OR badge_id LIKE ? ESCAPE '\') ORDER BY badge_id LIMIT 5` with `f"%{escape_like(q)}%"`.
- List: `ORDER BY active DESC, badge_id`, same LIKE escape.
- PATCH: parse both optional fields; for each present field accept value in `(True, 1)` → 1, `(False, 0)` → 0, else 400 naming the field; compute post-update state for the last-admin guard BEFORE writing:
```python
would_be = conn.execute(
    "SELECT COUNT(*) c FROM employees WHERE is_admin=1 AND active=1 AND badge_id != ?",
    (badge,)).fetchone()["c"]
if leaving_admin_state and would_be == 0:
    return JSONResponse(status_code=409, content={"error": "Cannot remove the last active admin"})
```
where `leaving_admin_state` is True iff (active present and becomes 0) or (isAdmin present and becomes 0), and the target currently `is_admin=1 AND active=1`.
- 404 on unknown badge (after body validation, matching the Node behavior).
- Import: single transaction (`with conn:` or explicit BEGIN/COMMIT), audit row after loop.
- Audit actions: `create`, `import`, `update` (details e.g. `active: 0`, `isAdmin: 1`).

- [ ] **Step 5: Mount in `app/main.py`:**
```python
from app.routers import employees
app.include_router(employees.lookup_router(get_conn), prefix="/api")            # public
app.include_router(employees.employees_router(get_conn), prefix="/api",
                   dependencies=[Depends(require_admin)])                        # admin-only
```
Note: `require_admin` needs `get_conn` too — use `Depends(require_admin)` with `require_admin(request: Request, conn=Depends(get_conn))`. Also keep a `require_user`-guarded probe: add `GET /api/departments` is Task 6; until then, any `user_client.get("/api/employees")` returning 403 is the role proof.

- [ ] **Step 6: Run full suite green. Commit** — `git commit -am "feat: employees API with admin roles, promote/demote, last-admin guard"`

---

### Task 6: Departments & locations — reads open, writes admin-only

**Files:**
- Create: `app/routers/departments.py`
- Test: `tests/test_departments.py`
- Modify: `app/main.py` (mount behind `require_user`)

**Interfaces:**
- Produces: `GET /api/departments` (any logged-in user) → `[{id, name, locations: [{id, name, departmentId}]}]`; admin-only mutations: `POST /api/departments {name}` (400/409), `POST /api/locations {departmentId, name}` (400/404/409), `PATCH /api/departments/{id} {name}` (400/404/409 rename collision excluding self), `PATCH /api/locations/{id} {name}` (same, sibling-scoped), `DELETE /api/departments/{id}` (409 if has locations), `DELETE /api/locations/{id}` (409 if holding inventory). Audit entities `department`/`location`.

- [ ] **Step 1: Write failing tests** — `tests/test_departments.py`: port `E:\Desktop\Project_files\tool_db2\tests\departments.test.js` 1:1 (create/rename/rename-collision/dup guards/delete-in-use 409/delete-unused 200), plus:
```python
def test_reads_open_writes_admin(admin_client, user_client):
    assert user_client.get("/api/departments").status_code == 200
    assert user_client.post("/api/departments", json={"name": "X"}).status_code == 403
    assert user_client.delete("/api/departments/1").status_code == 403
    d = admin_client.post("/api/departments", json={"name": "Milling"})
    assert d.status_code == 201
```
Fixture helper (add to `tests/conftest.py`, name exact):
```python
@pytest.fixture()
def make_location(admin_client):
    def _make(dept, loc):
        d = admin_client.post("/api/departments", json={"name": dept}).json()
        l = admin_client.post("/api/locations", json={"departmentId": d["id"], "name": loc}).json()
        return {"departmentId": d["id"], "locationId": l["id"]}
    return _make
```

- [ ] **Step 2: Implement** — port `server/routes/departments.js` 1:1. Router factory `departments_router(get_conn)`; reads: plain route; writes: `dependencies=[Depends(require_admin)]` via a nested `APIRouter` or per-route `Depends`. PATCH duplicate checks: `SELECT 1 FROM departments WHERE name=? AND id<>?`; locations: `WHERE department_id=? AND name=? AND id<>?`. Error bodies `{"error": "..."}` via `HTTPException` (handler renders `error`).

- [ ] **Step 3: Mount** behind `require_user`: `app.include_router(departments_router(get_conn), prefix="/api", dependencies=[Depends(require_user)])`.

- [ ] **Step 4: Run full suite green. Commit** — `git commit -am "feat: departments/locations with admin-gated writes"`

---

### Task 7: Tool types — reads open, writes admin-only

**Files:**
- Create: `app/routers/tool_types.py`
- Test: `tests/test_tool_types.py`
- Modify: `app/main.py`

**Interfaces:**
- Produces: `GET /api/tool-types` (logged-in) → `[{id, name, attributeSchema: [...]}]` (admin flag not needed here); admin-only: `POST {name, attributeSchema}` (400 missing name/missing schema/invalid schema via `validate_schema`; 409 dup name), `PATCH /{id} {name?, attributeSchema?}` (404; 400 invalid schema; 409 rename onto existing excluding self), `DELETE /{id}` (409 if tools reference). Audit entity `tool_type`.

- [ ] **Step 1: Write failing tests** — port `E:\Desktop\Project_files\tool_db2\tests\toolTypes.test.js` 1:1 (seeded types present with schemas; create; 400s incl. missing attributeSchema key and duplicate schema keys; 409 dup; patch schema; patch rename → 409; delete-in-use → 409), plus role checks (`user_client.post("/api/tool-types", ...)` → 403; `user_client.get("/api/tool-types")` → 200).

- [ ] **Step 2: Implement** — port `server/routes/toolTypes.js` 1:1 using `app/validation.validate_schema`. `rowToType`: `{"id": r["id"], "name": r["name"], "attributeSchema": json.loads(r["attribute_schema"])}`.

- [ ] **Step 3: Mount** behind `require_user` (writes individually `Depends(require_admin)`).

- [ ] **Step 4: Run full suite green. Commit** — `git commit -am "feat: tool types API with admin-gated mutations"`

---

### Task 8: Search + tools create/list — the core port

**Files:**
- Modify: `app/search.py` (add `build_tool_query`)
- Create: `app/routers/tools.py` (create + list + `clean_inventory_rows`)
- Test: `tests/test_search.py`, `tests/test_tools.py` (create/search parts)
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `escape_like` (Task 5), `validate_attributes` (Task 4), `get_conn`.
- Produces: `build_tool_query(conn, q=None, type_id=None, department_id=None, location_id=None) -> {"rows": [...], "locations_by_tool": {tool_id_str: [...]}}` — rows `[{id, name, description, typeId, typeName, attributes (dict), notes, reorderMin, totalQty}]` ordered `name COLLATE NOCASE`; breakdown rows `{locationId, locationName, departmentName, quantity}` ordered department then location. Filters: numeric-or-400 (non-negative int; error message `"<name> must be a number"`), thrown as `HTTPException(400)`. `clean_inventory_rows(conn, inventory) -> [{locationId, quantity}]` (merge dup locations by sum, drop zeros, 400 on non-int-negative quantity or unknown location). `POST /api/tools` → 201 `{id, name, toolTypeId}` (transactional; audit `create`); `GET /api/tools?q=&typeId=&departmentId=&locationId=` → `{results, locationsByTool}`.

- [ ] **Step 1: Write failing tests** — port `E:\Desktop\Project_files\tool_db2\tests\search.test.js` **excluding** its final "inventory replacement" test (that belongs to Task 9; that test lives in the Node file's search test only historically — check: if the Node file has it under tests/search.test.js, put it in tests/test_tools.py in Task 9 instead). Keep every other case 1:1: create with 2 locations; invalid attribute → 400 with `fields`; unknown type → 400; missing name → 400; searches by name/description/attribute (`end mill`, `carbide`, `TiAlN`, `caliper`, `zzz`→[]); wildcard literals (`100%`, `6_mm`); filter 400s (`typeId=abc`, `locationId=xyz`, `departmentId=1.5`); filter by type/location; totals + breakdown + reorderMin. Test fixture helper (port of `fixture()`):
```python
def make_tools(admin_client, conn, make_location):
    types = admin_client.get("/api/tool-types").json()
    cutting = next(t for t in types if t["name"] == "Cutting tools")
    a = make_location("Milling", "Cabinet 3")
    b = make_location("QC", "Shelf 2")
    tool = admin_client.post("/api/tools", json={
        "name": "6mm end mill", "description": "carbide", "toolTypeId": cutting["id"],
        "attributes": {"diameter_mm": 6, "coating": "TiAlN"}, "reorderMin": 2,
        "inventory": [{"locationId": a["locationId"], "quantity": 12},
                      {"locationId": b["locationId"], "quantity": 4}]})
    cal = admin_client.post("/api/tools", json={
        "name": "6in caliper", "toolTypeId": next(t["id"] for t in types if t["name"] == "Measuring tools"),
        "attributes": {"range": "0-150mm"},
        "inventory": [{"locationId": b["locationId"], "quantity": 1}]})
    return {"toolId": tool.json()["id"], "cutting": cutting, "a": a, "b": b}
```
Also add a decimal end-to-end test (spec requirement):
```python
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
```

- [ ] **Step 2: Implement `app/search.py` `build_tool_query`** — port `server/search.js` 1:1 (named params `:q` etc., `json_each(t.attributes)`, `ESCAPE '\'`, totalQty subquery, IN-clause breakdown with generated placeholders, invalid filter → `raise HTTPException(400, f"{name} must be a number")` for non-finite/negative/non-integer). Keys camelCase in row dicts (rename with SQL `AS`).

- [ ] **Step 3: Implement `app/routers/tools.py` create + list** — port `server/routes/tools.js` (the create/list part) 1:1: `clean_inventory_rows` identical semantics; POST validates name/type/attributes (`validate_attributes`; on failure `JSONResponse(400, {"error": "Invalid attribute values", "fields": attrs["errors"]})`), `reorderMin` None/'' → NULL else `int()` (non-int → 400 `reorderMin must be a number`), transaction over tool insert + inventory inserts + audit.

- [ ] **Step 4: Mount** behind `require_user`. Run full suite green. Commit — `git commit -am "feat: tools create + search with per-location breakdown"`

---

### Task 9: Tools detail, edit, inventory replace, delete + history

**Files:**
- Modify: `app/routers/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Produces: `GET /api/tools/{id}` → detail (404; `inventory` rows + `history` newest-first limit 50 `{timestamp, badgeId, action, details}`); `PATCH /api/tools/{id}` — merges current+patched attrs, validates full merged set against (new) type; when `attributes` provided OR type changed → persist ONLY `attrs["clean"]`; fields-only PATCH preserves stored attributes verbatim; invalid merged → 400 `{error, fields}`; `reorderMin` None/''→NULL else int-or-400. `PUT /api/tools/{id}/inventory` → replace via `clean_inventory_rows`, transaction, audit `set_inventory`. `DELETE /api/tools/{id}` → transactional delete (inventory + tool), audit `delete` retained.

- [ ] **Step 1: Write failing tests** — port `E:\Desktop\Project_files\tool_db2\tests\tools.test.js` 1:1: detail shape + history has `create`; 404; edit fields (rename, attrs merge `6.35` + DLC, reorderMin 3); invalid attr → 400; inventory replace (5+2 merge, zero dropped, `[{locA: 7}]`); negative/non-integer → 400; delete removes rows and keeps audit. Plus Task 8's decimal/type-change strip tests: type change strips old-type attrs; fields-only PATCH preserves attrs; type change with invalid merged value → 400. And the converted search test (PUT merge) lives here if it isn't already in tests/test_tools.py.

- [ ] **Step 2: Implement** — port `server/routes/tools.js` detail/patch/inventory/delete 1:1 including the stale-attribute fix semantics:
```python
type_changed = type_id != row["tool_type_id"]
stored_attributes = row["attributes"]
if "attributes" in body or type_changed:
    merged = {**json.loads(row["attributes"]), **(body.get("attributes") or {})}
    attrs = validate_attributes(json.loads(type_row["attribute_schema"]), merged)
    if not attrs["ok"]:
        return JSONResponse(400, {"error": "Invalid attribute values", "fields": attrs["errors"]})
    stored_attributes = json.dumps(attrs["clean"])
```
(Fields-only PATCH: `stored_attributes` stays the original string, unchanged.)

- [ ] **Step 3: Run full suite green. Commit** — `git commit -am "feat: tool detail/edit/inventory/delete with history"`

---

### Task 10: CSV export + backup download + config endpoint

**Files:**
- Create: `app/csv_export.py`, `app/routers/admin.py`
- Test: `tests/test_export.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `build_tool_query` (Task 8).
- Produces: `to_csv(headers, rows) -> str` (RFC-4180 escaping, `\r\n` after every line including the last). `GET /api/export.csv?<same params>` (any logged-in user) → `text/csv` attachment `tools-export.csv`, columns Name, Description, Type, Total Qty, Locations (`Dept - Loc: qty` joined `'; '`), then attribute columns (first-seen order across result set, schema labels); invalid filters → 400 JSON. `GET /api/backup` (**admin-only**) → sqlite file download `tooldb-backup-YYYY-MM-DD.sqlite` via `VACUUM INTO` a temp file. `GET /api/config` (public) → `{"companyName": config.company_name}`.
- Produces: `backup_to(conn, dest_path: Path)` in `app/backup.py` — used by both the route and the auto-backup thread (Task 11):
```python
def backup_to(conn, dest_path):
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(conn.execute("PRAGMA database_list").fetchone()[2] if not conn else None)
    # simpler and preferred: use sqlite3's backup API against a fresh connection
    src = sqlite3.connect(str(dest.parent / "unused"))  # placeholder — see implementation note
```
**Implementation note (write it this way):** open a read-only connection to the same DB file and use the stdlib backup API:
```python
def backup_to(db_path, dest_path):
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    dst.close(); src.close()
    return dest
```
The HTTP route still uses `VACUUM INTO` parity is NOT required — the backup API is equivalent and simpler; test asserts the magic header `b"SQLite format 3\x00"` and that the copy contains the seeded tool.

- [ ] **Step 1: Write failing tests** — port `E:\Desktop\Project_files\tool_db2\tests\export.test.js` 1:1 (toCsv escaping incl. `has"quote` case with trailing `\r\n`; export filtered rows with attribute columns incl. Locations column content; empty-result = header only + `\r\n`; backup download valid SQLite with magic header containing seeded data), plus role checks: `user_client.get("/api/backup")` → 403; `user_client.get("/api/export.csv")` → 200; `anon_client.get("/api/config")` → 200 with companyName.

- [ ] **Step 2: Implement `app/csv_export.py`** — port `server/csv.js`:
```python
import re
def _esc(v):
    s = "" if v is None else str(v)
    return f'"{s.replace('"', '""')}"' if re.search(r'[",\n\r]', s) else s

def to_csv(headers, rows):
    lines = [",".join(_esc(h) for h in headers)]
    lines.extend(",".join(_esc(c) for c in row) for row in rows)
    return "\r\n".join(lines) + "\r\n"
```

- [ ] **Step 3: Implement `app/routers/admin.py`** — port `server/routes/admin.js` export route (uses `build_tool_query`, `locations_by_tool.get(tool_id)` for the Locations column, attr columns first-seen by schema label) + backup route (`tempfile.mkdtemp()` + `VACUUM INTO` or `backup_to`, then `FileResponse` with `Content-Disposition: attachment; filename="tooldb-backup-YYYY-MM-DD.sqlite"`) + `GET /api/config` public. Backup route behind `require_admin`.

- [ ] **Step 4: Run full suite green. Commit** — `git commit -am "feat: CSV export, backup download, config endpoint"`

---

### Task 11: Auto-backup thread

**Files:**
- Modify: `app/backup.py` (add loop)
- Test: `tests/test_autobackup.py`
- Modify: `app/main.py` (entry-point wiring only)

**Interfaces:**
- Produces: `auto_backup_once(db_path, backup_dir: Path, today=None) -> Path | None` — writes `tooldb-backup-YYYY-MM-DD.sqlite` into backup_dir (via `backup_to`), prunes to newest 30 `tooldb-backup-*.sqlite` files, returns the path (None if backup_dir falsy). `run_auto_backup_daily(config)` — daemon thread: on start and then every hour checks whether today's dated backup exists; if not, runs `auto_backup_once`; never raises. Started ONLY in the `if __name__ == "__main__"` / frozen entry block of `app/main.py` — never inside `create_app`.

- [ ] **Step 1: Write failing tests** — `tests/test_autobackup.py`:
```python
from datetime import date
from pathlib import Path
from app.backup import auto_backup_once, prune_backups

def test_creates_dated_backup(engine, tmp_path, conn):
    out = auto_backup_once(engine, tmp_path)
    today = date.today().isoformat()
    assert out == tmp_path / f"tooldb-backup-{today}.sqlite"
    assert out.read_bytes()[:16] == b"SQLite format 3\x00"

def test_noop_without_dir(engine):
    assert auto_backup_once(engine, None) is None

def test_prune_keeps_30(engine, tmp_path):
    for i in range(35):
        (tmp_path / f"tooldb-backup-2020-01-{i+1:02d}.sqlite").write_bytes(b"x")
    auto_backup_once(engine, tmp_path)
    remaining = sorted(tmp_path.glob("tooldb-backup-*.sqlite"))
    assert len(remaining) == 30
    assert "tooldb-backup-2020-01-35.sqlite" in [p.name for p in remaining]
```

- [ ] **Step 2: Run, verify FAIL. Implement in `app/backup.py`:**
```python
import threading
import time
from datetime import date
from pathlib import Path

KEEP = 30

def auto_backup_once(db_path, backup_dir, today=None):
    if not backup_dir:
        return None
    stamp = (today or date.today()).isoformat()
    dest = Path(backup_dir) / f"tooldb-backup-{stamp}.sqlite"
    backup_to(db_path, dest)
    prune_backups(backup_dir)
    return dest

def prune_backups(backup_dir):
    files = sorted(Path(backup_dir).glob("tooldb-backup-*.sqlite"))
    for old in files[:-KEEP]:
        old.unlink(missing_ok=True)

def run_auto_backup_daily(config):
    if not config.backup_dir:
        return
    def loop():
        last = None
        while True:
            today = date.today()
            if last != today:
                try:
                    auto_backup_once(config.db_path, config.backup_dir, today)
                    last = today
                except Exception:
                    pass  # retry next hour; a failed backup must never kill the app
            time.sleep(3600)
    threading.Thread(target=loop, daemon=True, name="auto-backup").start()
```
(Note: `auto_backup_once` re-backing-up over today's file when called twice is fine — idempotent content.)

- [ ] **Step 3: Wire entry point** — in `app/main.py`'s `__main__`/frozen block (see Task 12): `run_auto_backup_daily(config)` before `uvicorn.run`.

- [ ] **Step 4: Run full suite green. Commit** — `git commit -am "feat: daily auto-backup with 30-copy retention"`

---

### Task 12: Final assembly — static UI, SPA fallback, entry point

**Files:**
- Modify: `app/main.py` (final form)

**Interfaces:**
- Produces: `create_app` also mounts `client/dist` when it exists: `StaticFiles` at `/assets`, index.html fallback for all non-`/api` GET paths with `Cache-Control: no-cache`; entry block: `load_config()` → `connect`/seed (via create_app) → `run_auto_backup_daily(config)` → `uvicorn.run(app, host="0.0.0.0", port=config.port)`.

- [ ] **Step 1: Implement final `app/main.py`:**
```python
import sys
from pathlib import Path
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as HTTPExceptionBase
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse

from app.auth import auth_router, require_user
from app.backup import run_auto_backup_daily
from app.config import load_config
from app.db import connect, seed_defaults
from app.routers import admin, departments, employees, tool_types, tools

def create_app(config):
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=config.session_secret, same_site="lax")
    conn = connect(config.db_path)
    seed_defaults(conn)
    get_conn = lambda: conn

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        detail = exc.detail
        return JSONResponse(status_code=exc.status_code,
                            content={"error": detail} if isinstance(detail, str) else detail)

    app.include_router(auth_router(get_conn), prefix="/api")
    app.include_router(employees.lookup_router(get_conn), prefix="/api")
    app.include_router(admin.config_router(get_conn, config), prefix="/api")
    app.include_router(tools.tools_router(get_conn), prefix="/api", dependencies=[Depends(require_user)])
    app.include_router(departments.departments_router(get_conn), prefix="/api", dependencies=[Depends(require_user)])
    app.include_router(tool_types.tool_types_router(get_conn), prefix="/api", dependencies=[Depends(require_user)])
    app.include_router(employees.employees_router(get_conn), prefix="/api", dependencies=[Depends(require_admin := __import__("app.auth", fromlist=["require_admin"]).require_admin)])
    app.include_router(admin.admin_router(get_conn), prefix="/api", dependencies=[Depends(require_user)])
    @app.get("/api/health")
    def health(): return {"ok": True}

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
    config = load_config()
    run_auto_backup_daily(config)
    uvicorn.run(create_app(config), host="0.0.0.0", port=config.port)
```
(Write clean imports — the `__import__` line above is a drafting artifact; do `from app.auth import auth_router, require_user, require_admin` at top.) Note the frozen guard: PyInstaller runs the module as `__main__`, so the entry block executes in the exe. Adjust the catch-all so `/api/*` misses 404 as JSON, not HTML.

- [ ] **Step 2: Smoke (dev)** — build the client once (`npm run build` inside client/ — requires `npm install` there, copied from tool_db2), then `python -m app.main`; browse `http://localhost:3000`: login ADMIN → search loads → add tool works → admin page works.

- [ ] **Step 3: Run full suite green** (dist doesn't exist in CI/tests unless built — the guard covers both). Commit — `git commit -am "feat: static serving, SPA fallback, entry point with auto-backup"`

---

### Task 13: Client changes — roles UI, attribute editor, company name

**Files:**
- Modify: `client/src/auth.jsx` (user carries `isAdmin` — no change needed if /me shape flows through; verify), `client/src/App.jsx`, `client/src/Layout.jsx`, `client/src/pages/Admin.jsx`
- Modify (port reference): `E:\Desktop\Project_files\tool_db2\client\src\pages\Admin.jsx`

**Interfaces:**
- Consumes: `/api/me` → `{badgeId, name, isAdmin}`; `/api/config` → `{companyName}`; admin endpoints now 403 for non-admins.

- [ ] **Step 1: Roles in the UI** — `App.jsx`: wrap the admin route in an `AdminRoute` component (uses `useAuth()`; while `user.isAdmin === false` → `<Navigate to="/" replace />`). `Layout.jsx`: render the Admin nav link only when `user?.isAdmin`. Header shows `config.companyName` (fetch `/api/config` once in Layout; also `document.title = companyName`).

- [ ] **Step 2: Attribute editor** — in `Admin.jsx` ToolTypes tab, replace the `Label|number` textarea AND the `newField` text input with proper rows:
```jsx
function AttributeRow({ onAdd }) {
  const [label, setLabel] = useState("");
  const [type, setType] = useState("text");
  return (
    <div className="flex gap-2 items-center">
      <input value={label} onChange={e => setLabel(e.target.value)} placeholder="Attribute label (e.g. Diameter (mm))" className={F} />
      <select value={type} onChange={e => setType(e.target.value)} className={F + " w-32"}>
        <option value="text">Text</option>
        <option value="number">Number</option>
      </select>
      <button className={Btn} onClick={() => { if (label.trim()) { onAdd({ label: label.trim(), type }); setLabel(""); } }}>Add</button>
    </div>
  );
}
```
- Create-type form: name input + one `AttributeRow` list (rows state, remove per row) → POST `{name, attributeSchema}` (keys derived server-side? NO — the Node derive was client-side `parseFields`; keep it client-side: derive `key` from label with `label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "")` before sending).
- Edit type: `AttributeRow` for adding + per-row remove button (existing behavior kept).
- Employees tab: add `Make admin` / `Remove admin` button per row calling `PATCH /api/employees/{badgeId} {isAdmin: bool}`, surfacing 409 errors via the tab message (e.g. last-admin guard).
- Key the attribute list rows by index+key (`key={f.key + i}`) since keys may repeat pre-validation.

- [ ] **Step 3: Verify** — `npm run build` clean; live smoke with the Python server (`python -m app.main`): log in ADMIN → Admin visible → promote E200 → log in as E200 → Admin link hidden, direct URL `/admin` bounces to `/`; search/add/export all still work for E200; attribute editor adds a Text and a Number attribute; company name shows in header; decimal `0.25` tool attribute searchable. Also verify ToolForm's dynamic fields still render from the new schemas.

- [ ] **Step 4: Commit** — `git commit -am "feat: role-aware UI, attribute editor rows, company name"`

---

### Task 14: Packaging — PyInstaller onedir + README + exe smoke test

**Files:**
- Create: `tooldb.spec`, `build_exe.bat`, `README.md` (final)
- Modify: `requirements-dev.txt` (pyinstaller already present)

**Interfaces:**
- Produces: `dist/ToolDB/ToolDB.exe` — double-clickable; creates `config.ini`, DB, `session-secret` in the exe folder on first run; serves the built UI + API on the configured port.

- [ ] **Step 1: `tooldb.spec`** (onedir):
```python
# PyInstaller spec — run from repo root: pyinstaller tooldb.spec
a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=[],
    datas=[("client/dist", "client/dist")],
    hiddenimports=["uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
                   "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
                   "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
                   "uvicorn.lifespan", "uvicorn.lifespan.on"],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ToolDB",
          console=True, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, name="ToolDB")
```
`build_exe.bat`:
```bat
@echo off
cd /d "%~dp0"
pushd client && call npm run build && popd
.venv\Scripts\pyinstaller tooldb.spec --noconfirm
echo Done: dist\ToolDB\ToolDB.exe
```
- [ ] **Step 2: Build and smoke the exe** — `build_exe.bat`, then copy `dist/ToolDB` to a scratch dir, run `ToolDB.exe`, verify: `config.ini` + `session-secret` + `tooldb.sqlite` created next to the exe; browser login ADMIN works; company name from config shows; edit `config.ini` (`Port=3001`, `DatabasePath=C:\temp\tooldb-test.sqlite`, `CompanyName=Acme`) → restart → listens on 3001, DB created at the custom path, header shows Acme; search/add/export/backup all work from the exe; set `BackupDir` → dated backup appears after startup. Kill the process.
- [ ] **Step 3: Full suite + final commit** — `python -m pytest -q` green; write the final `README.md` (deployment: copy dist folder, optional config edits, auto-start via Task Scheduler pointing at the exe; first login ADMIN; backup notes; "sessions are in-memory — restart logs everyone out"); `git add -A && git commit -m "feat: PyInstaller onedir packaging and deployment README"`

---

## Self-Review Notes

- Spec coverage: config (Tasks 2, 12, 14), schema+seed+ADMIN admin bootstrap (Task 1), auth/roles/last-admin (Tasks 3, 5), lookup incl. isAdmin (Task 5), departments/tool-types gating (Tasks 6–7), tools/search/decimals (Tasks 8–9), export/backup/config endpoint (Task 10), auto-backup (Task 11), static/SPA/entry (Task 12), client roles + attribute editor + company name (Task 13), packaging + README + smoke (Task 14).
- Port sourcing: Node files in `E:\Desktop\Project_files\tool_db2\server\` + tests are the behavioral reference; exact code in this plan covers everything new or where Python differs structurally.
- Byte-compat watchpoints handed to implementers: `{error: ...}` exception handler (Task 3), camelCase response keys, `{"fields": {...}}` on attribute errors, CSV CRLF + trailing newline, 409/400 semantics per route.

