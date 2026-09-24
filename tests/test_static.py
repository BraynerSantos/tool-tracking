"""SPA static serving: index.html fallback + /api misses stay JSON 404s."""
import json

from conftest import make_client  # noqa: F401  (used via fixtures below)


def _build_dist(engine, html='<html><body>SPA</body></html>\n'):
    dist = engine.parent / "client" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(html, encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)\n", encoding="utf-8")
    return dist


def test_spa_fallback_serves_index(engine):
    _build_dist(engine)
    client = make_client(engine, "E100", True)

    for path in ("/", "/admin"):
        res = client.get(path)
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/html")
        assert res.headers["cache-control"] == "no-cache"
        assert "SPA" in res.text


def test_assets_are_served(engine):
    _build_dist(engine)
    client = make_client(engine, "E100", True)

    res = client.get("/assets/app.js")
    assert res.status_code == 200
    assert "console.log" in res.text


def test_api_miss_is_json_404_not_html(engine):
    _build_dist(engine)
    client = make_client(engine, "E100", True)

    res = client.get("/api/missing")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/json")
    assert res.json() == {"error": "Not found"}


def test_no_dist_means_no_fallback(engine):
    # no client/dist -> unknown paths 404 as JSON via the exception handler
    client = make_client(engine, None, False)

    res = client.get("/admin")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/json")


def test_api_still_works_with_dist_present(engine):
    _build_dist(engine)
    client = make_client(engine, "E100", True)

    res = client.get("/api/health")
    assert res.status_code == 200
    assert json.loads(res.content) == {"ok": True}
