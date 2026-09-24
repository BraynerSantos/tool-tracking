# Troubleshooting

Symptom → likely cause → fix. When in doubt, check `tooldb.log` next to the
exe — startup problems, port conflicts, and backup failures are all written
there.

## The app won't start / nothing happens when I run the exe

- **Port already in use** — another program (or a second copy of ToolDB) is
  listening on the port. `tooldb.log` will show it. Change `Port` in
  `config.ini` and start again, or stop the other program.
- **Old files mixed with new** — after updating, copy the *whole* new
  `dist\ToolDB` folder; don't mix a new exe with an old `_internal\`.
- Any startup crash leaves a traceback in `tooldb.log`.

## The web page doesn't open / can't be reached

- The app opens `http://localhost:<port>` automatically on the machine it
  runs on. Give it a couple of seconds.
- From another PC, use the **server's IP**, not localhost:
  `http://192.168.x.x:3000`. Find it with `ipconfig` on the server.
- Still nothing? Confirm the exe is running (Task Manager) and the port in
  `config.ini` matches the URL you're using.
- Company firewall rules may block the port — that's an IT conversation, not
  an app setting.

## Can't log in

- **"Unknown or inactive employee ID"** — either the badge isn't in the
  employee list (Admin → Employees) or the person was deactivated. Admins
  reactivate from the same screen.
- Typo check: the bootstrap admin is **000** — three zeros, not `00` or `O O O`.
- A deactivated employee is locked out *immediately*, even mid-session.

## The company name didn't change

1. The name is read **once, at startup** — fully stop `ToolDB.exe` (Task
   Manager) and start it again.
2. Edit the `config.ini` **next to the exe you actually run**.
3. `CompanyName` must be inside the `[General]` section, spelled exactly so.
4. Refresh the browser (F5) after restarting.

Check `http://localhost:<port>/api/config` — it shows what the server read.

## Deleted a tool type / department but it's still there

- Deletions are permanent and survive restarts. If it "came back", you're
  looking at a page opened before the delete — refresh (F5).
- A tool **type** refuses to be deleted while tools of that type exist
  (message: *Tools of this type exist; remove them first*). Same for
  departments with locations, and locations holding inventory.

## A type/department/location refuses to be deleted

The app blocks deletions that would orphan data. The alert tells you what's
still using it: delete or move the tools/locations first, then retry.

## Backups aren't happening

- `BackupDir` empty in `config.ini` = auto-backup **off**. Set it to a folder.
- Look at `tooldb.log` for `auto-backup failed` lines — usually an
  unreachable network share, missing permissions, or a full disk.
- The manual button (Admin → Download database backup) always works and is a
  good fallback while fixing the automatic one.

## Two people changed the same tool at once

Last save wins — no warning is shown. The tool's **History** shows what each
of them saved, so the earlier change can be re-entered. (The app never
half-applies a save: a change is all-or-nothing.)

## An employee left the company

Admin → Employees → **Deactivate**. Their login stops working immediately;
their history stays. Don't delete data to "remove" a person.

## Changes vanished / tool count looks old

Refresh the page (F5). The page shows data as of its last load; another
person's change won't appear until then. If data is *really* missing, check
the tool's History, then the backups section of `DisasterRecovery.md`.

## Where things live (next to the exe)

| File/folder | What it is | May delete? |
|---|---|---|
| `tooldb.sqlite` | **The database — everything.** | No |
| `tooldb.sqlite-wal` / `-shm` | Temporary database helpers | No (auto-managed) |
| `config.ini` | Settings | Edit, don't delete |
| `session-secret` | Signs login cookies | No — deleting logs everyone out |
| `tooldb.log` | Diagnostics | Yes, safe to delete |
| `backup\` | Automatic daily backups | Keep |
| `_internal\` | Program files | No |
