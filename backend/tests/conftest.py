"""Shared pytest fixtures for the backend test suite.

The backend uses flat imports (``import main``, ``from config import ...``), so
the backend directory must be on ``sys.path``. The SPA route (and its
path-traversal guard) only mounts when a frontend build exists, so we ensure a
minimal ``frontend/dist`` is present before ``main`` is imported.

``API_KEY`` is forced empty so the API tests exercise the unauthenticated path
deterministically; the auth middleware itself is covered in test_security.py.
"""

import os
import sys
from pathlib import Path

# Force auth off for the app under test, regardless of any local .env.
os.environ["API_KEY"] = ""

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DIST_DIR = BACKEND_DIR.parent / "frontend" / "dist"
DIST_DIR.mkdir(parents=True, exist_ok=True)
(DIST_DIR / "assets").mkdir(exist_ok=True)
if not (DIST_DIR / "index.html").exists():
    (DIST_DIR / "index.html").write_text("<!doctype html><title>lightbar</title>")
