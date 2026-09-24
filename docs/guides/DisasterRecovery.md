# Disaster Recovery

What to do when things go seriously wrong. Read this **before** you need it —
every scenario below ends with "restore a backup", so step zero is: make sure
automatic backups are on (`BackupDir` in `config.ini`) and pointed somewhere
that isn't the same disk as the app.

## The one restore procedure everything funnels into

**Restoring the database from a backup file:**

1. Stop the app (Task Manager → end `ToolDB.exe`, or stop the scheduled task).
2. In the folder with the database, rename the current files:
   - `tooldb.sqlite` → `tooldb-damaged.sqlite`
   - delete `tooldb.sqlite-wal` and `tooldb.sqlite-shm` if present
3. Copy the backup you want (e.g. `backup\tooldb-backup-2026-09-22.sqlite`)
   into the folder and rename it to `tooldb.sqlite`.
4. Start the app. Log in and spot-check a few tools.

Everything is now as it was when that backup was taken — tools, quantities,
and the full change history (it lives in the same file). Anything entered
after that backup is gone; if you need it, the `tooldb-damaged.sqlite` you
saved in step 2 can often be mined for it later.

## Scenario: disk died / PC died

1. Set up the replacement PC (install nothing — just copy the `dist\ToolDB`
   folder from wherever it is, ideally a network share or USB stick).
2. Copy your **latest backup file** into the folder as `tooldb.sqlite`.
3. Copy `session-secret` too if you want everyone's logins to keep working.
4. Start `ToolDB.exe`. Update the IP in bookmarks if the PC's address changed.

This is why the automatic `BackupDir` should point **off the app's disk**.

## Scenario: someone deleted tools by mistake

1. Stop the app.
2. Restore yesterday's (or the most recent pre-mistake) backup per the
   procedure above — the mistake won't be in it.
3. Start the app and manually re-enter anything *good* that happened after
   that backup (the damaged file's History sections tell you what those
   were).

There is no per-tool undo — restoring a backup is all-or-nothing, which is
exactly why the app makes one every day.

## Scenario: the database file is corrupted

Symptom: the app starts but tools are missing/garbled, or `tooldb.log` shows
`database disk image is malformed`.

1. Stop the app. Rename `tooldb.sqlite` → `tooldb-damaged.sqlite` (keep it —
   partially readable copies can sometimes be salvaged).
2. Delete `tooldb.sqlite-wal` / `-shm`.
3. Restore the newest backup per the procedure above.

## Scenario: locked out — no working admin login

You can't be fully locked out: **000** is re-created as an active admin if it
ever disappears entirely. Two cases:

- **000 exists but was demoted/deactivated and no other admin remains** —
  impossible by design (the last-admin guard blocks it). If it somehow
  happened through hand-editing the database: any admin can re-promote from
  Admin → Employees; otherwise restore a backup from before the change.
- **You lost track of who the admins are** — log in as 000 or ADMIN, both are
  always admins unless explicitly deactivated.

## Scenario: moving to a new server PC

1. Stop the app on the old PC.
2. Copy `tooldb.sqlite` (and `session-secret` to preserve logins) from the
   old folder into the new `dist\ToolDB` folder on the new PC.
3. Set up the scheduled task / shortcut on the new PC, start it, and update
   everyone's bookmark with the new IP if it changed.

## Scenario: ransomware / virus on the server

If the app's disk is encrypted, the database and any backups on the *same
disk* are lost — this is the one scenario the app cannot fix, and the reason
`BackupDir` should be a **network share or second drive**. Restore from the
off-disk backups per the top procedure, then rebuild the PC.

## Prevention checklist (5 minutes, once)

- [ ] `BackupDir` set to a folder **off the app's disk** (or a network share).
- [ ] Confirmed at least one dated file appears in that folder after a start.
- [ ] More than one person is an active admin.
- [ ] `tooldb.log` checked occasionally (it's the early-warning system).
- [ ] A copy of the newest backup taken off-site or onto a USB drive monthly.
