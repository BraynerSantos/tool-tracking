"""SQLite database backup — stdlib backup API against a read-only source.

``backup_to`` is shared by the admin download route (Task 10) and the
scheduled auto-backup (Task 11).
"""

import sqlite3
import sys
import threading
import time
from datetime import date
from pathlib import Path

from app.applog import append_log

KEEP = 30  # daily copies retained by prune_backups


def backup_to(db_path, dest_path) -> Path:
    """Copy the database at ``db_path`` to ``dest_path``; returns the dest."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return dest


def auto_backup_once(db_path, backup_dir, today=None) -> Path | None:
    """Write today's dated backup into ``backup_dir`` and prune; None if no dir."""
    if not backup_dir:
        return None
    stamp = (today or date.today()).isoformat()
    dest = Path(backup_dir) / f"tooldb-backup-{stamp}.sqlite"
    backup_to(db_path, dest)
    prune_backups(backup_dir)
    return dest


def prune_backups(backup_dir) -> None:
    """Keep only the newest KEEP ``tooldb-backup-*.sqlite`` files.

    Name-sorted works because the ISO-dated names sort chronologically.
    """
    files = sorted(Path(backup_dir).glob("tooldb-backup-*.sqlite"))
    for old in files[:-KEEP]:
        old.unlink(missing_ok=True)


def try_backup_once(config, last) -> object:
    """Run today's backup if not already done; returns the new ``last`` stamp.

    A failure prints to stderr (console runs) and to tooldb.log next to the
    exe (windowed runs have no console), and returns the old stamp so the
    loop retries next hour — a failed backup must never kill the app, but
    the operator must be able to see the data-protection feature is not
    working.
    """
    today = date.today()
    if last == today:
        return last
    try:
        auto_backup_once(config.db_path, config.backup_dir, today)
        return today
    except Exception as e:
        print(f"auto-backup failed: {e}", file=sys.stderr)
        append_log(getattr(config, "base_dir", None), f"auto-backup failed: {e}")
        return last


def run_auto_backup_daily(config) -> None:
    """Start the daemon thread that takes one backup per day, hourly checks.

    Entry-point-only: never called from create_app (tests must not spawn it).
    """
    if not config.backup_dir:
        return

    def loop():
        last = None
        while True:
            last = try_backup_once(config, last)
            time.sleep(3600)

    threading.Thread(target=loop, daemon=True, name="auto-backup").start()
