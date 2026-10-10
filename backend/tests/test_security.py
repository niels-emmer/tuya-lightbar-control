"""Security regression tests: the API-key middleware and the SPA traversal guard."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import main
from auth import ApiKeyMiddleware, _keys_match


def _client(api_key: str) -> TestClient:
    app = FastAPI()

    @app.get("/api/status")
    def _status():  # pragma: no cover - trivial
        return {"ok": True}

    @app.get("/healthz")
    def _healthz():  # pragma: no cover - trivial
        return {"ok": True}

    app.add_middleware(ApiKeyMiddleware, api_key=api_key)
    return TestClient(app)


class TestApiKeyAuth:
    def test_rejects_missing_key(self):
        assert _client("s3cret").get("/api/status").status_code == 401

    def test_rejects_wrong_key(self):
        c = _client("s3cret")
        assert c.get("/api/status", headers={"X-API-Key": "nope"}).status_code == 401

    def test_accepts_x_api_key_header(self):
        c = _client("s3cret")
        assert c.get("/api/status", headers={"X-API-Key": "s3cret"}).status_code == 200

    def test_accepts_bearer_token(self):
        c = _client("s3cret")
        r = c.get("/api/status", headers={"Authorization": "Bearer s3cret"})
        assert r.status_code == 200

    def test_healthz_is_never_protected(self):
        assert _client("s3cret").get("/healthz").status_code == 200

    def test_docs_are_protected(self):
        assert _client("s3cret").get("/docs").status_code == 401

    def test_empty_key_disables_auth(self):
        assert _client("").get("/api/status").status_code == 200


class TestKeysMatch:
    """hmac.compare_digest raises on non-ASCII str — the guard must not."""

    def test_equal(self):
        assert _keys_match("s3cret", "s3cret") is True

    def test_different(self):
        assert _keys_match("nope", "s3cret") is False

    def test_non_ascii_degrades_to_false(self):
        assert _keys_match("caf\u00e9", "s3cret") is False
        assert _keys_match("s3cret", "caf\u00e9") is False


class TestSpaTraversal:
    def test_unknown_path_serves_index(self):
        resp = main.serve_spa("does-not-exist")
        assert Path(resp.path).name == "index.html"

    @pytest.mark.parametrize(
        "attack",
        [
            "../../.env",
            "../config.py",
            "../../../etc/passwd",
            "/etc/passwd",  # absolute path replaces the base in pathlib
        ],
    )
    def test_traversal_is_confined_to_dist(self, attack):
        resp = main.serve_spa(attack)
        # Anything outside the dist directory must fall back to index.html.
        assert Path(resp.path).name == "index.html"

    def test_serves_real_file_inside_dist(self):
        target = main._DIST / "robots.txt"
        target.write_text("User-agent: *")
        try:
            resp = main.serve_spa("robots.txt")
            assert Path(resp.path).name == "robots.txt"
        finally:
            target.unlink()
