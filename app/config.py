import configparser
from dataclasses import dataclass
import sys
from pathlib import Path

DEFAULT_COMPANY = "Insaco"
DEFAULT_PORT = 3000
DEFAULT_BACKUP_DIR = "backup"  # folder next to the exe

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
        parser["Backup"] = {"BackupDir": DEFAULT_BACKUP_DIR}
        with ini_path.open("w", encoding="utf-8") as f:
            parser.write(f)
    parser.read(ini_path, encoding="utf-8")
    db_path = _resolve(parser["Database"]["DatabasePath"], root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # BackupDir: empty string explicitly disables auto-backup; a missing key
    # falls back to the default `backup` folder next to the exe.
    backup_raw = parser["Backup"].get("BackupDir", DEFAULT_BACKUP_DIR).strip()
    backup_dir = _resolve(backup_raw, root) if backup_raw else None
    if backup_dir is not None:
        backup_dir.mkdir(parents=True, exist_ok=True)
    return AppConfig(
        base_dir=root,
        db_path=db_path,
        port=parser["General"].getint("Port", fallback=DEFAULT_PORT),
        company_name=parser["General"].get("CompanyName", fallback=DEFAULT_COMPANY),
        backup_dir=backup_dir,
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
