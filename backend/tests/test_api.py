"""API route tests against the real app (auth disabled via conftest)."""

from fastapi.testclient import TestClient

import main
import settings_store
from lightbar import hsv_to_tuya

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


class _FakeStatusDriver:
    """Reports fixed DPs, like the device would after a red whole-bar write."""

    def __init__(self, *, stale: bool) -> None:
        self._dps = {20: True, 21: "colour", 24: hsv_to_tuya(0, 100, 100)}
        self.whole_bar_stale = stale

    def get_status(self):
        return self._dps


def test_status_reports_active_effect_not_stale_color(monkeypatch):
    # The reported bug: an effect is running (so the bar is per-segment), but
    # DP 24 still holds the red from before it started.
    monkeypatch.setattr(main, "_driver", _FakeStatusDriver(stale=True))
    monkeypatch.setattr(main._runner, "_current", {"name": "polestar", "params": {}})

    body = client.get("/api/status").json()

    assert body["mode"] == "effect"
    assert body["color"] is None
    assert body["effect"] == {"name": "polestar", "params": {}}


def test_status_hides_color_after_segment_write(monkeypatch):
    # No effect, but a per-segment write has made DP 24 meaningless.
    monkeypatch.setattr(main, "_driver", _FakeStatusDriver(stale=True))
    monkeypatch.setattr(main._runner, "_current", None)

    body = client.get("/api/status").json()

    assert body["mode"] == "colour"
    assert body["color"] is None
    assert body["effect"] is None


def test_status_reports_color_when_whole_bar_is_current(monkeypatch):
    monkeypatch.setattr(main, "_driver", _FakeStatusDriver(stale=False))
    monkeypatch.setattr(main._runner, "_current", None)

    body = client.get("/api/status").json()

    assert body["mode"] == "colour"
    assert body["color"] == {"h": 0.0, "s": 100.0, "v": 100.0}
    assert body["effect"] is None


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
