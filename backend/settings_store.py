from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SETTINGS_FILE = Path(__file__).parent.parent / "settings.json"

_DEFAULTS: dict[str, Any] = {
    "brightness": 80,
    "auto_on": None,   # "HH:MM" or null
    "auto_off": None,  # "HH:MM" or null
    "weather_lat": 52.92,
    "weather_lon": 6.43,
}


def load() -> dict[str, Any]:
    if _SETTINGS_FILE.exists():
        try:
            stored = json.loads(_SETTINGS_FILE.read_text())
            return {**_DEFAULTS, **stored}
        except Exception as e:
            logger.warning(f"Failed to read settings.json: {e}")
    return _DEFAULTS.copy()


def save(partial: dict[str, Any]) -> dict[str, Any]:
    current = load()
    merged = {**current, **partial}
    _SETTINGS_FILE.write_text(json.dumps(merged, indent=2))
    return merged
