"""Minimal file logging for the windowed (console-less) executable.

With console=False, stdout/stderr vanish — anything an operator must be able
to diagnose later (auto-backup failures, fatal startup errors) is appended to
tooldb.log next to the exe instead.
"""
from datetime import datetime
from pathlib import Path


def append_log(base_dir, message: str) -> None:
    """Append a timestamped line to base_dir/tooldb.log. Never raises."""
    if not base_dir:
        return
    try:
        stamp = datetime.now().isoformat(timespec="seconds")
        with open(Path(base_dir) / "tooldb.log", "a", encoding="utf-8") as f:
            f.write(f"{stamp} {message}\n")
    except OSError:
        pass
