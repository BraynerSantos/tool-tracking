import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.config import AppConfig
from app.main import create_app
from app.db import connect, seed_defaults

@pytest.fixture()
def engine(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = connect(db_path)
    seed_defaults(conn, seed_tool_types=True)  # test fixtures use the 4 built-in types
    conn.close()
    return db_path

def make_client(engine, badge, is_admin, secret="test-secret"):
    c = sqlite3.connect(engine)
    c.execute("INSERT OR IGNORE INTO employees (badge_id, name, is_admin) VALUES (?, ?, ?)",
              ("E100", "Admin User", 1))
    c.execute("INSERT OR IGNORE INTO employees (badge_id, name, is_admin) VALUES (?, ?, ?)",
              ("E200", "Regular User", 0))
    c.commit(); c.close()
    config = AppConfig(base_dir=engine.parent, db_path=engine, port=3000,
                       company_name="Tool DB", backup_dir=None, session_secret=secret)
    app = create_app(config)
    client = TestClient(app)
    if badge:
        res = client.post("/api/login", json={"badgeId": badge})
        assert res.status_code == 200
    return client

@pytest.fixture()
def admin_client(engine):
    return make_client(engine, "E100", True)

@pytest.fixture()
def user_client(engine):
    return make_client(engine, "E200", False)

@pytest.fixture()
def anon_client(engine):
    return make_client(engine, None, False)

@pytest.fixture()
def conn(engine):
    c = connect(engine)
    yield c
    c.close()

@pytest.fixture()
def make_location(admin_client):
    """Create a department + location via the API; returns both ids."""
    def _make(dept, loc):
        d = admin_client.post("/api/departments", json={"name": dept}).json()
        l = admin_client.post("/api/locations", json={"departmentId": d["id"], "name": loc}).json()
        return {"departmentId": d["id"], "locationId": l["id"]}
    return _make
