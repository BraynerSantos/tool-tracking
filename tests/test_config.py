from pathlib import Path

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
