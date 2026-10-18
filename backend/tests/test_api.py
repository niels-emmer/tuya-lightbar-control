"""API route tests against the real app (auth disabled via conftest)."""

from fastapi.testclient import TestClient

import main
import settings_store

client = TestClient(main.app)


def test_healthz_is_open():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_effects_list():
    r = client.get("/api/effects")
    assert r.status_code == 200
    assert isinstance(r.json(), list) and r.json()


def test_root_serves_spa():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_unknown_path_is_404():
    # No SPA catch-all: a probe for a spec file that does not exist must get an
    # honest 404, not 200 + index.html.
    assert client.get("/llms.txt").status_code == 404
    assert client.get("/.well-known/ai-plugin.json").status_code == 404
    assert client.get("/api/does-not-exist").status_code == 404


def test_device_route_503_without_driver(monkeypatch):
    monkeypatch.setattr(main, "_driver", None)
    assert client.post("/api/power", json={"on": True}).status_code == 503


def test_segment_index_validation():
    body = {"h": 1, "s": 1, "v": 1}
    assert client.post("/api/segment/0", json=body).status_code == 422
    assert client.post("/api/segment/21", json=body).status_code == 422


def test_color_validation():
    assert client.post("/api/color", json={"h": 400, "s": 1, "v": 1}).status_code == 422


def test_settings_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "_SETTINGS_FILE", tmp_path / "settings.json")
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    body["brightness"] = 55
    r2 = client.put("/api/settings", json=body)
    assert r2.status_code == 200
    assert r2.json()["brightness"] == 55
