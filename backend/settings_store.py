from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from models import AppSettings

logger = logging.getLogger(__name__)

_SETTINGS_FILE = Path(__file__).parent.parent / "settings.json"

# Single source of truth: app-settings defaults live on the AppSettings model.
# settings.json stores only overrides on top of these.
_DEFAULTS: dict[str, Any] = AppSettings().model_dump()


def exists() -> bool:
    """True if a settings.json has been written (i.e. not a first run)."""
    return _SETTINGS_FILE.exists()


def load() -> dict[str, Any]:
    if _SETTINGS_FILE.exists():
        try:
            stored = json.loads(_SETTINGS_FILE.read_text())
            return {**_DEFAULTS, **stored}
        except Exception as e:
            logger.warning(f"Failed to read settings.json: {e}")
    return _DEFAULTS.copy()


def save(partial: dict[str, Any]) -> dict[str, Any]:
    merged = {**load(), **partial}
    payload = json.dumps(merged, indent=2)
    # Prefer an atomic write (tmp + rename). But when settings.json is a
    # single-file bind mount (the documented Docker deploy) renaming onto the
    # mount point fails with EBUSY, so fall back to a direct in-place write.
    tmp = _SETTINGS_FILE.parent / (_SETTINGS_FILE.name + ".tmp")
    try:
        tmp.write_text(payload)
        tmp.replace(_SETTINGS_FILE)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        _SETTINGS_FILE.write_text(payload)
    return merged


def weather() -> tuple[float, float]:
    """Return the user-configured (lat, lon) for weather-backed effects."""
    s = load()
    return float(s["weather_lat"]), float(s["weather_lon"])
