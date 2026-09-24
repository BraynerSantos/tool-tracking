# Tool DB — CNC Tool Tracking (Python)

A self-hosted tool-tracking web app: employees log in with their badge ID,
search tools by name/attribute/description, and see quantities per location.
Admins manage employees, departments, locations, tool types (with custom
attributes), export CSV, print filtered lists, and download SQLite backups.

Python (FastAPI + uvicorn + SQLite) rewrite of the original Node app, shipped
as a single portable Windows folder — no Node, no Python install needed on the
server PC.

## Deploy (Windows, no installer)

Everything the server needs is in the `dist\ToolDB` folder after a build:

```
dist\ToolDB\
  ToolDB.exe        <- double-click / Task Scheduler entry point
  _internal\        <- runtime + bundled UI (do not edit; keep next to the exe)
  docs\             <- user/admin/troubleshooting guides (plain text)
```

To deploy:

1. Copy the whole `dist\ToolDB` folder to the server PC, e.g. `C:\tooldb`
   (keep `ToolDB.exe` and `_internal\` together).
2. Run `ToolDB.exe`. It runs in the background — no terminal window opens.
   Diagnostics are written to `tooldb.log` next to the exe.
3. Employees open `http://<server-ip>:3000`.

## Documentation

The `docs\guides` folder (copied into `dist\ToolDB` on build) contains:

- **UserGuide.md** — how the app works and how to do everyday tasks
- **AdminGuide.md** — setup, config.ini reference, roles, backups, auto-start
- **Troubleshooting.md** — symptom → cause → fix for common problems
- **DisasterRecovery.md** — restoring backups, dead-PC migration, lockout recovery

### First run

On first start the exe creates, next to itself:

- `config.ini` — settings file (see below)
- `tooldb.sqlite` — the database, seeded with two bootstrap admin logins,
  **000** and **ADMIN** (both named "Administrator"). No departments, locations
  or tool types exist yet — you create those from the Admin screens.
- `session-secret` — random secret used to sign session cookies

Log in with badge **000** (or **ADMIN**) — both are seeded as admins. Then go
to Admin → Employees and add yourself with your real badge ID and name, plus
the rest of the team. Departments, locations and tool types are created from
the Admin screens — the app starts with none of them.

### config.ini

```ini
[General]
companyname = Acme        ; shown in the app header
port = 3000               ; HTTP port the server listens on

[Database]
databasepath = tooldb.sqlite

[Backup]
backupdir = C:\tooldb\backups
```

- `databasepath` — relative paths resolve against the exe's folder; an
  absolute path (e.g. `D:\data\tools.sqlite`) is used as-is. The folder is
  created if missing.
- `backupdir` — empty disables auto-backup. When set, one dated
  `tooldb-backup-YYYY-MM-DD.sqlite` is written per day shortly after startup,
  and only the newest 30 copies are kept.
- If an auto-backup fails (e.g. the backup folder is unreachable), it retries
  hourly and the failure is recorded in `tooldb.log` next to the exe.

Edit `config.ini` while the server is stopped, then start it again for changes
to take effect.

### Auto-start (optional)

To survive reboots: Task Scheduler → Create Task → trigger "At startup"
(run as the user that should own the data) → Actions → New action:

- Program/script: `C:\tooldb\ToolDB.exe`
- Start in: `C:\tooldb`

### Backups

- Manual: Admin → Download database backup (admin only) saves a copy of the
  SQLite database through the browser.
- Automatic: set `backupdir` as above for daily dated copies (keep 30).
- Belt-and-braces: copy the database file while the server is stopped.

### Sessions

Sessions are signed cookies, not server-side storage — they keep working
across server restarts because the signing secret is the stable
`session-secret` file. Only deleting that file (or replacing it) invalidates
everyone's sessions and forces a fresh login.

## Building from source

```
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
npm install --prefix client
build_exe.bat
```

`build_exe.bat` builds the React UI into `client\dist`, then runs PyInstaller
with `tooldb.spec`, producing `dist\ToolDB\ToolDB.exe`.

## API tests

The API test suite lives in `tests\` and runs against a throwaway database:

```
.venv\Scripts\python -m pytest -q
```

## Development

- `.venv\Scripts\pip install -r requirements-dev.txt` — server deps + test tooling
- `npm install --prefix client` — React/Vite client deps
- `.venv\Scripts\python -m uvicorn app.main:app --reload` — API on port 3000
- `npm run dev --prefix client` — Vite dev server (proxies `/api` to 3000)
- `.venv\Scripts\python app\main.py` — production-style run: one server on
  port 3000 serving `client\dist` + API
