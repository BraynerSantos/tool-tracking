from datetime import date
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
