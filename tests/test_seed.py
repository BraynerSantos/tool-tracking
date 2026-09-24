"""Bootstrap seeding: 000 (owner) and ADMIN both exist as active admins, and a
deactivated bootstrap account is never resurrected by a restart's re-seed."""
from app.db import connect, seed_defaults


def test_seeds_000_and_admin_as_active_admins(tmp_path):
    conn = connect(tmp_path / "fresh.sqlite")
    seed_defaults(conn)
    rows = conn.execute(
        "SELECT badge_id, name, active, is_admin FROM employees WHERE badge_id IN ('000','ADMIN') "
        "ORDER BY badge_id").fetchall()
    assert [tuple(r) for r in rows] == [("000", "Administrator", 1, 1), ("ADMIN", "Administrator", 1, 1)]


def test_production_seed_creates_no_tool_types(tmp_path):
    conn = connect(tmp_path / "fresh.sqlite")
    seed_defaults(conn)  # production call: bootstrap admins only
    assert conn.execute("SELECT COUNT(*) c FROM tool_types").fetchone()["c"] == 0
    with_tool_types = connect(tmp_path / "with-types.sqlite")
    seed_defaults(with_tool_types, seed_tool_types=True)
    assert with_tool_types.execute("SELECT COUNT(*) c FROM tool_types").fetchone()["c"] == 4


def test_reseed_does_not_resurrect_deactivated_000(tmp_path):
    conn = connect(tmp_path / "existing.sqlite")
    conn.execute("INSERT INTO employees (badge_id, name, active, is_admin) "
                 "VALUES ('000', 'Owner', 0, 0)")  # deliberately deactivated
    conn.commit()
    seed_defaults(conn)  # a server restart re-runs the seed
    row = conn.execute("SELECT name, active, is_admin FROM employees WHERE badge_id='000'").fetchone()
    assert tuple(row) == ("Owner", 0, 0)  # untouched
