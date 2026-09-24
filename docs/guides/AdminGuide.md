# Admin Guide

For the people who run the app. Admins are regular employees who can also
manage setup: employees, departments & locations, tool types, and backups.
Everything an admin does is recorded in the audit log with their badge ID.

## Getting in the first time

The app seeds two bootstrap admin logins on a fresh database:

| Badge | Name |
|---|---|
| **000** | Administrator |
| **ADMIN** | Administrator |

Log in as **000**, then:

1. **Admin → Employees** → add yourself with your real badge ID → **Make
   admin** on your own row.
2. From now on use your own badge. You may deactivate 000/ADMIN once real
   admins exist — the app never allows removing the *last* active admin, so
   you cannot lock yourself out.
3. **Bulk import users**: paste lines of `EmployeeID,Name` (one per line, from
   Excel). Existing badges with a new name are renamed and reactivated;
   identical rows are skipped.

## Setting up the catalog

**Departments** (Admin → Departments & locations): create one per shop area.
Each holds named **locations**. Rules the app enforces:

- No two departments with the same name; no two locations with the same name
  inside one department.
- A location that still holds inventory cannot be deleted — empty it first.
- A department with locations cannot be deleted — delete its locations first.
- Renaming onto an existing name is refused.

**Tool types** (Admin → Tool types): define each category with the attributes
it needs. Each attribute is a **label + Text/Number** choice — e.g.
`Diameter (mm)` as Number, `Coating` as Text. Number attributes accept
decimals (0.250, 6.35).

- **Rename** any type at any time (renaming onto an existing name is refused).
- **Remove type** only works when *no tools* use it — the app refuses
  otherwise and tells you. Create your types before adding tools.
- Types you delete stay deleted when the app restarts.
- Adding/removing attributes on an existing type is safe; the values on tools
  are validated against the type's current schema.

**The app starts with zero tool types and zero departments** — everything is
created by you, and everything you delete stays deleted across restarts.

## Everyday admin tasks

- **Deactivate** someone who left (Admin → Employees) — their login stops
  working immediately; their past audit entries remain.
- **Make admin / Remove admin** — takes effect the next time the person logs
  in. You cannot demote or deactivate the last active admin.

## config.ini reference

Lives next to the exe; created with defaults on first run. **Edit only while
the app is stopped**, then start it again.

```ini
[General]
CompanyName = Insaco      ; header + browser tab title
Port = 3000               ; HTTP port

[Database]
DatabasePath = tooldb.sqlite

[Backup]
BackupDir = backup
```

- **CompanyName** — shown in the header and tab title.
- **Port** — change if 3000 is taken. Employees then use
  `http://<server-ip>:<port>`.
- **DatabasePath** — where the SQLite file lives. Relative = exe folder;
  absolute paths (e.g. `D:\data\tools.sqlite`) work too. Folder is created if
  missing.
- **BackupDir** — folder for daily automatic backups. Empty = auto-backup
  off. See below.

## Backups

- **Automatic** (default on): one dated file `tooldb-backup-YYYY-MM-DD.sqlite`
  is written to BackupDir shortly after each day's first start; the newest 30
  are kept. Failures retry hourly and are logged in `tooldb.log`.
- **Manual**: Admin → *Download database backup*.
- **Point BackupDir somewhere safe** — a second drive or network share, not
  the same disk as the app.

See `DisasterRecovery.md` for restoring.

## Auto-start on boot

Task Scheduler → Create Task → trigger **At startup** → Action: program
`ToolDB.exe`, **Start in** = its folder (e.g. `C:\tooldb`). The app is
windowless; `tooldb.log` next to the exe is your window into it.

## What admins cannot do

- Recover a tool deleted by someone else (only restore a whole-database
  backup).
- See or reset passwords — there are none; the badge ID is the identity.
- Bypass the audit log — every admin action is logged like everyone else's.
