# Tool DB Python — Design

**Date:** 2026-09-21
**Status:** Approved design. Rewrites the Node backend of the tool tracking system
(spec: `2026-09-20-tool-tracking-design.md`) as a Python application packaged as a
PyInstaller onedir executable. The React UI is reused unchanged.

## Purpose

Same tool-tracking application (what/how many/where for a CNC ceramics shop), delivered
as a single distributable: `ToolDB.exe` + support folder. The database location, port,
company name, and auto-backup directory come from a config file. Adds employee admin
roles, a proper attribute editor UI, and verified decimal-number support.

## Project location

`E:\Desktop\Project_files\tooldb-py` — its own git repository. The `client/` React app is
copied from tool_db2 (UI unchanged; same build tooling). The Node backend is not
included.

## Architecture

```
[Employee browsers] ──► ToolDB.exe (PyInstaller onedir)
                          ├─ uvicorn + FastAPI app (API + static UI + SPA fallback)
                          ├─ SQLite (stdlib sqlite3), path from config.ini
                          ├─ config.ini (next to exe, created on first run)
                          └─ client/dist (built React bundle, served statically)
```

- FastAPI + Starlette SessionMiddleware (signed cookie sessions, secret generated on
  first run and persisted next to the exe).
- Single process; uvicorn on the configured port (default 3000), bound 0.0.0.0.
- Same API contract as the Node version: same routes, JSON shapes, status codes, and
  rules. The React frontend works unchanged, and the ported pytest suite (61+ tests)
  is the acceptance bar.

## Config file (config.ini, INI format)

Created with defaults on first run if missing, next to the exe (in dev: repo root):

```ini
[General]
CompanyName = Tool DB
Port = 3000

[Database]
DatabasePath = tooldb.sqlite

[Backup]
BackupDir =
```

- `DatabasePath` — relative values resolve against the exe's folder (dev: repo root);
  absolute paths honored as-is. Parent directories are created if missing.
- `BackupDir` — empty disables auto-backup.
- Changing CompanyName updates the UI header/title (served to the client via `/api/config`).

## Data model

Identical to the Node version (employees, departments, locations, tool_types, tools,
inventory, activity_log) with one addition:

- `employees.is_admin INTEGER NOT NULL DEFAULT 0`

Seeded on every start (INSERT OR IGNORE): the 4 tool types with their attribute
schemas (Cutting tools, Holders & workholding, Grinding/diamond tools, Measuring
tools) and bootstrap admin employees `000`/`Administrator` and
`ADMIN`/`Administrator` with `is_admin = 1` — so the 000 owner account exists
even on databases created before this change, and deactivating one is never
undone by a restart.

## Roles

- Everyone (any active employee) can: log in, search, view, add tools, edit tools and
  quantities, delete tools, export, print.
- **Admins additionally** manage the Admin screens: employees (add/import/
  deactivate/promote), departments & locations, tool types & attribute schemas,
  backup download, and see the backup/auto-backup settings.
- Enforcement is server-side: admin-only routes return 403 for non-admins. The UI
  hides the Admin nav link and guards the route, but the API is the authority.
- **Last-admin guard:** an admin cannot remove admin rights (or deactivate) the last
  active admin. Server returns 409.
- `POST /api/login`, `GET /api/me`, and `GET /api/employee-lookup` include `isAdmin`.

## Attribute editor (UI change)

Admin → Tool Types, for both new types and existing ones: each attribute row is a
**label text input + a Text/Number dropdown**, with an Add button (and remove buttons
per row). Replaces the Node version's `Label|number` textarea. Schema keys are derived
from the label (slugified), exactly as before.

## Decimal numbers

Number attributes accept decimal values end to end (e.g. 0.250, 6.35): validation,
storage, search matching, and CSV export. Explicit tests cover inch-style decimals.

## API

Byte-compatible port of the Node version's API, including all fix-round behavior:
- Auth: login (active check), logout, me, public employee-lookup (≥2 chars, max 5,
  active only, LIKE-escaped).
- Employees: list/create/import/deactivate + `PATCH is_admin` (admin-only; last-admin
  guard). All admin-only routes also require admin.
- Departments/locations: nested list, create/rename (409 collisions), in-use delete
  guards (409).
- Tool types: list/create/patch (schema validated; 409 rename collision; 409 delete
  in use).
- Tools: create (attribute validation against type schema, inventory merge-on-conflict,
  zero-drop, transactional), list/search (LIKE-escaped q across name/description/
  attribute values; typeId/departmentId/locationId filters; per-location breakdown;
  totals; reorder-min flags), detail + history, edit (strip old-type attributes on type
  change; fields-only PATCH preserves attributes), inventory replace, delete.
- Admin: filtered CSV export (RFC-4180, CRLF, attribute columns), SQLite backup
  (VACUUM INTO temp + download), config endpoint (`/api/config` → company name).
- Validation identical: number fields accept finite numbers/decimal strings, reject
  junk; unknown keys stripped; blank allowed.

## Auto-backup

If `BackupDir` is set: a background thread on startup and then once per day writes a
dated copy `tooldb-backup-YYYY-MM-DD.sqlite` (via `VACUUM INTO` / sqlite backup API)
into that directory, keeping the most recent 30. Manual backup button unchanged
(admin-only).

## Packaging

- `build_exe.bat`: builds the React client (npm), then runs PyInstaller **onedir** with
  the client/dist bundle and app source bundled.
- Output `dist/ToolDB/`: `ToolDB.exe`, `_internal/`, plus (created at runtime)
  `config.ini`, database file, and `session-secret` file.
- First run: creates config.ini with defaults + seeds the DB; log in with ADMIN.

## Error handling

Same rules as the Node version: typed validation errors (400 with per-field messages),
in-use delete guards (409), rename collisions (409), no negative quantities, no
orphaned references, transactions for multi-table writes, friendly JSON errors — never
raw tracebacks.

## Testing

- pytest port of the full Node suite (61+ tests), plus new tests: admin gating
  (403s), promote/demote + last-admin guard, decimal values end to end, config
  loading/creation, auto-backup.
- Packaging smoke: run the built exe, verify SPA served, login, seed data, search,
  export, backup, and that config.ini/DB land in the exe's folder (and at a custom
  DatabasePath).
