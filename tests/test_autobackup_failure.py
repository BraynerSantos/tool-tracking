"""A failed auto-backup must print to stderr, never raise, and stay "undone"
so the daily loop retries on its next hourly tick."""
import sys
from types import SimpleNamespace

from app.backup import try_backup_once


def test_failed_backup_prints_and_does_not_raise(tmp_path, capsys):
    config = SimpleNamespace(
        db_path=tmp_path / "missing" / "no-database.sqlite",  # mode=ro open fails
        backup_dir=tmp_path / "backups",
        base_dir=tmp_path)  # windowed exe has no console: failures land in tooldb.log
    stamp = object()  # sentinel "last done" marker

    result = try_backup_once(config, stamp)  # must not raise

    assert result is stamp  # not marked done -> retried next hour
    assert "auto-backup failed" in capsys.readouterr().err
    assert "auto-backup failed" in (tmp_path / "tooldb.log").read_text(encoding="utf-8")
    assert not any((tmp_path / "backups").glob("*.sqlite"))  # nothing written
