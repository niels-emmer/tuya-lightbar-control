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
    # Write atomically so a crash mid-write cannot truncate settings.json.
    tmp = _SETTINGS_FILE.parent / (_SETTINGS_FILE.name + ".tmp")
    tmp.write_text(json.dumps(merged, indent=2))
    tmp.replace(_SETTINGS_FILE)
    return merged


def weather() -> tuple[float, float]:
    """Return the user-configured (lat, lon) for weather-backed effects."""
    s = load()
    return float(s["weather_lat"]), float(s["weather_lon"])
