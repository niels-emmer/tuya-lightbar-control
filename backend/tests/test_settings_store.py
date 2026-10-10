"""settings_store tests: defaults, atomic save, corruption fallback."""

import settings_store
from models import AppSettings


def _isolate(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    monkeypatch.setattr(settings_store, "_SETTINGS_FILE", target)
    return target


def test_defaults_match_the_model():
    # Single source of truth: defaults come from AppSettings.
    assert settings_store._DEFAULTS == AppSettings().model_dump()


def test_load_returns_defaults_when_file_missing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert settings_store.load() == settings_store._DEFAULTS
    assert settings_store.exists() is False


def test_save_then_load_round_trip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    settings_store.save({"brightness": 42})
    assert settings_store.load()["brightness"] == 42
    assert settings_store.exists() is True


def test_save_leaves_no_tmp_file(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    settings_store.save({"brightness": 10})
    assert not (tmp_path / "settings.json.tmp").exists()


def test_corrupt_file_falls_back_to_defaults(tmp_path, monkeypatch):
    target = _isolate(tmp_path, monkeypatch)
    target.write_text("{ not valid json")
    assert settings_store.load() == settings_store._DEFAULTS


def test_weather_returns_floats(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    lat, lon = settings_store.weather()
    assert isinstance(lat, float) and isinstance(lon, float)


def test_save_falls_back_when_rename_fails(tmp_path, monkeypatch):
    # Simulate a single-file bind mount, where rename() onto the mount point
    # fails with EBUSY (this is the documented Docker deployment).
    import pathlib

    target = _isolate(tmp_path, monkeypatch)

    def _ebusy(self, other):
        raise OSError(16, "Device or resource busy")

    monkeypatch.setattr(pathlib.Path, "replace", _ebusy)
    settings_store.save({"brightness": 33})
    assert target.exists()
    assert settings_store.load()["brightness"] == 33
