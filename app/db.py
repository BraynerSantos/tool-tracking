import json
import sqlite3
import threading
from pathlib import Path

from fastapi import Request

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
  badge_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  is_admin INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS departments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS locations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  department_id INTEGER NOT NULL REFERENCES departments(id),
  name TEXT NOT NULL,
  UNIQUE (department_id, name)
);
CREATE TABLE IF NOT EXISTS tool_types (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  attribute_schema TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS tools (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  tool_type_id INTEGER NOT NULL REFERENCES tool_types(id),
  attributes TEXT NOT NULL DEFAULT '{}',
  notes TEXT NOT NULL DEFAULT '',
  reorder_min INTEGER
);
CREATE TABLE IF NOT EXISTS inventory (
  tool_id INTEGER NOT NULL REFERENCES tools(id),
  location_id INTEGER NOT NULL REFERENCES locations(id),
  quantity INTEGER NOT NULL CHECK (quantity >= 0),
  PRIMARY KEY (tool_id, location_id)
);
CREATE TABLE IF NOT EXISTS activity_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL DEFAULT (datetime('now')),
  badge_id TEXT NOT NULL,
  action TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id TEXT NOT NULL DEFAULT '',
  details TEXT NOT NULL DEFAULT ''
);
"""

def connect(db_path) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


# All requests share ONE sqlite connection (see create_app). Sync FastAPI
# endpoints run in a threadpool, so without a guard an HTTPException raised
# inside one request's ``with conn:`` block would roll back another request's
# in-flight statements — silent lost writes on routine 409 collisions. The
# lock is held from dependency resolution until the response finishes, which
# serializes request DB access and also closes the last-admin-guard TOCTOU.
conn_lock = threading.Lock()


def get_conn(request: Request):
    """Yield-dependency handing out the app's shared connection under the lock.

    One callable shared by every route (including require_admin): FastAPI's
    per-request dependency cache resolves it once, so a route that needs both
    the conn and an admin check never acquires the lock twice.
    """
    with conn_lock:
        yield request.app.state.conn

SEED_TOOL_TYPES = [
    ("Cutting tools", [
        {"key": "diameter_mm", "label": "Diameter (mm)", "type": "number"},
        {"key": "flute_count", "label": "Flutes", "type": "number"},
        {"key": "shank_mm", "label": "Shank (mm)", "type": "number"},
        {"key": "corner_radius_mm", "label": "Corner radius (mm)", "type": "number"},
        {"key": "coating", "label": "Coating", "type": "text"},
        {"key": "material", "label": "Material", "type": "text"}]),
    ("Holders & workholding", [
        {"key": "taper_type", "label": "Taper type", "type": "text"},
        {"key": "bore_mm", "label": "Bore (mm)", "type": "number"},
        {"key": "capacity_mm", "label": "Capacity (mm)", "type": "number"},
        {"key": "jaw_type", "label": "Jaw type", "type": "text"}]),
    ("Grinding/diamond tools", [
        {"key": "grit", "label": "Grit", "type": "number"},
        {"key": "bond_type", "label": "Bond type", "type": "text"},
        {"key": "diameter_mm", "label": "Diameter (mm)", "type": "number"},
        {"key": "profile", "label": "Profile", "type": "text"}]),
    ("Measuring tools", [
        {"key": "range", "label": "Range", "type": "text"},
        {"key": "resolution", "label": "Resolution", "type": "text"},
        {"key": "calibration_due", "label": "Calibration due", "type": "text"}]),
]

def seed_defaults(conn: sqlite3.Connection, seed_tool_types: bool = False) -> None:
    """Bootstrap bootstrap admins always; tool types only when asked.

    Production starts with NO tool types (the shop creates its own from the
    Admin screen, and deleted types stay deleted). The pytest suite passes
    seed_tool_types=True because its fixtures are written against the four
    built-in types.
    """
    if seed_tool_types:
        for name, schema in SEED_TOOL_TYPES:
            conn.execute("INSERT OR IGNORE INTO tool_types (name, attribute_schema) VALUES (?, ?)",
                         (name, json.dumps(schema)))
    # Bootstrap admin logins. INSERT OR IGNORE (not the empty-table check) so a
    # database that already has data still gains the 000 owner account; a
    # deliberately deactivated 000/ADMIN is never resurrected by a restart.
    conn.executemany(
        "INSERT OR IGNORE INTO employees (badge_id, name, active, is_admin) VALUES (?, ?, 1, 1)",
        [("000", "Administrator"), ("ADMIN", "Administrator")])
    conn.commit()

def log_action(conn, badge_id, action, entity, entity_id, details=""):
    conn.execute("INSERT INTO activity_log (badge_id, action, entity, entity_id, details) VALUES (?,?,?,?,?)",
                 (badge_id, action, entity, str(entity_id if entity_id is not None else ""), details))
    conn.commit()
