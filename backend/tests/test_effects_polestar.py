"""Polestar effect: pure parsing/rendering and the run-loop blink (no network)."""

import asyncio
from types import SimpleNamespace

import pypolestar

import config
from effects.polestar import PolestarEffect, _Frame


class _Enum:
    """Stands in for a pypolestar GraphQL enum member (has a ``.name``)."""

    def __init__(self, name: str) -> None:
        self.name = name


def _telematics(
    *,
    soc: int = 72,
    charging: str | None = "CHARGING_STATUS_CHARGING",
    connection: str | None = "CHARGER_CONNECTION_STATUS_CONNECTED",
    meters: int = 12_345_678,
) -> SimpleNamespace:
    battery = SimpleNamespace(
        battery_charge_level_percentage=soc,
        estimated_distance_to_empty_km=310,
        charging_status=_Enum(charging) if charging else None,
        charger_connection_status=_Enum(connection) if connection else None,
        charging_power_watts=11_000,
        estimated_charging_time_to_full_minutes=45,
    )
    odometer = SimpleNamespace(odometer_meters=meters)
    return SimpleNamespace(battery=battery, odometer=odometer)


def _snapshot(*, soc: int, charging: str, connection: str) -> dict:
    return {"soc": soc, "charging_status": charging, "connection_status": connection}


def _fake_api(calls: dict, vins: list[str]):
    class FakeApi:
        def __init__(self, username: str, password: str) -> None:
            calls["creds"] = (username, password)

        async def async_init(self) -> None:
            calls["init"] = True

        def get_available_vins(self) -> list[str]:
            return vins

        async def update_latest_data(self, vin: str, update_telematics: bool = True) -> None:
            calls["vin"] = vin

        def get_car_telematics(self, vin: str) -> SimpleNamespace:
            return _telematics()

        def get_grpc_battery(self, vin: str) -> None:
            return None

        def get_grpc_target_soc(self, vin: str) -> None:
            return None

        async def async_logout(self) -> None:
            calls["logout"] = True

    return FakeApi


# ── parsing ─────────────────────────────────────────────────────────────────


def test_parse_maps_fields():
    snap = PolestarEffect._parse(_telematics())
    assert snap["soc"] == 72
    assert snap["target_soc"] is None  # gRPC-only
    assert snap["range_km"] == 310
    assert snap["charging_status"] == "CHARGING_STATUS_CHARGING"
    assert snap["connection_status"] == "CHARGER_CONNECTION_STATUS_CONNECTED"
    assert snap["charging_power_watts"] == 11_000
    assert snap["charging_time_min"] == 45
    assert snap["odometer_km"] == 12_346  # metres -> km, rounded


def test_parse_reads_grpc_target_soc():
    target = SimpleNamespace(battery_charge_target_level=90)
    snap = PolestarEffect._parse(_telematics(), None, target)
    assert snap["target_soc"] == 90


def test_parse_handles_missing_data():
    snap = PolestarEffect._parse(SimpleNamespace(battery=None, odometer=None))
    assert snap["soc"] is None
    assert snap["charging_status"] is None
    assert snap["connection_status"] is None
    assert snap["odometer_km"] is None


def test_parse_prefers_grpc_connection_and_power():
    # GraphQL telematics carries neither connection nor power; the gRPC path does.
    grpc = SimpleNamespace(
        charger_connection_status=_Enum("CHARGER_CONNECTION_STATUS_CONNECTED"),
        charging_power_watts=9_900,
        battery_charge_level_percentage=39.0,
    )
    snap = PolestarEffect._parse(_telematics(connection=None), grpc)
    assert snap["connection_status"] == "CHARGER_CONNECTION_STATUS_CONNECTED"
    assert snap["charging_power_watts"] == 9_900
    assert snap["soc"] == 72  # telematics SOC still wins when present


def test_parse_without_grpc_leaves_connection_none():
    snap = PolestarEffect._parse(_telematics(connection=None), None)
    assert snap["connection_status"] is None


def test_charging_and_connection_detection():
    assert PolestarEffect._is_charging("CHARGING_STATUS_CHARGING")
    assert PolestarEffect._is_charging("CHARGING_STATUS_SMART_CHARGING")
    assert not PolestarEffect._is_charging("CHARGING_STATUS_IDLE")
    assert not PolestarEffect._is_charging("CHARGING_STATUS_DONE")
    assert not PolestarEffect._is_charging("CHARGING_STATUS_SCHEDULED")
    # These contain "CHARGING" but are not an active charge.
    assert not PolestarEffect._is_charging("CHARGING_STATUS_DISCHARGING")
    assert not PolestarEffect._is_charging("CHARGING_STATUS_ERROR")
    assert not PolestarEffect._is_charging(None)
    assert PolestarEffect._is_connected("CHARGER_CONNECTION_STATUS_CONNECTED")
    assert not PolestarEffect._is_connected("CHARGER_CONNECTION_STATUS_DISCONNECTED")
    assert not PolestarEffect._is_connected("CHARGER_CONNECTION_STATUS_FAULT")
    assert not PolestarEffect._is_connected(None)


# ── rendering ───────────────────────────────────────────────────────────────


def test_soc_hue_bands():
    assert PolestarEffect._soc_hue(80) == 120  # green
    assert PolestarEffect._soc_hue(60) == 120
    assert PolestarEffect._soc_hue(40) == 40  # amber
    assert PolestarEffect._soc_hue(10) == 0  # red


def test_state_no_data_is_dim_heartbeat():
    assert PolestarEffect._state(None, 80) == (20, 0, 5, False, 0)
    assert PolestarEffect._state({"soc": None}, 100) == (20, 0, 6, False, 0)


def test_state_charging_is_green():
    snap = _snapshot(
        soc=50,
        charging="CHARGING_STATUS_CHARGING",
        connection="CHARGER_CONNECTION_STATUS_CONNECTED",
    )
    assert PolestarEffect._state(snap, 100) == (10, 120, 100, True, 0)


def test_state_disconnected_is_dim():
    snap = _snapshot(
        soc=80,
        charging="CHARGING_STATUS_IDLE",
        connection="CHARGER_CONNECTION_STATUS_DISCONNECTED",
    )
    assert PolestarEffect._state(snap, 100) == (16, 120, 40, False, 0)


def test_state_connected_idle_uses_soc_hue():
    snap = _snapshot(
        soc=40,
        charging="CHARGING_STATUS_IDLE",
        connection="CHARGER_CONNECTION_STATUS_CONNECTED",
    )
    assert PolestarEffect._state(snap, 100) == (8, 40, 100, False, 0)


def test_state_includes_target_lit():
    snap = {
        "soc": 42,
        "target_soc": 90,
        "charging_status": "CHARGING_STATUS_CHARGING",
        "connection_status": "CHARGER_CONNECTION_STATUS_CONNECTED",
    }
    # 90 % -> 18 segments; 42 % -> 8.
    assert PolestarEffect._state(snap, 100) == (8, 120, 100, True, 18)


def test_colors_bar_length():
    colors = PolestarEffect._colors(_Frame(8, 40, 100, False, 0))
    assert len(colors) == 20
    assert colors[:8] == [(40, 100, 100)] * 8
    assert colors[8:] == [None] * 12


def test_colors_draws_marker_ahead_of_fill():
    # 42 % filled, 90 % target -> a dim neutral marker on segment 18 (index 17).
    colors = PolestarEffect._colors(_Frame(8, 120, 100, True, 18))
    assert colors[17] == (0, 0, 40)
    assert colors[8:17] == [None] * 9
    assert colors[18:] == [None] * 2


def test_colors_drops_marker_once_fill_reaches_it():
    # Fill at the target: index 17 is part of the fill, so no marker.
    colors = PolestarEffect._colors(_Frame(18, 120, 100, True, 18))
    assert colors[17] == (120, 100, 100)


# ── run loop ────────────────────────────────────────────────────────────────


class _FakeDriver:
    def __init__(self) -> None:
        self.full_sweeps: list = []
        self.tip_on: list = []
        self.tip_off: list = []

    def set_all_segments(self, colors) -> bool:
        self.full_sweeps.append(colors)
        return True

    def set_segment(self, segment: int, h: float, s: float, v: float) -> bool:
        self.tip_on.append(segment)
        return True

    def set_segment_off(self, segment: int) -> bool:
        self.tip_off.append(segment)
        return True


def _run_briefly(monkeypatch, snapshot: dict, seconds: float) -> _FakeDriver:
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: SimpleNamespace(
            polestar_username="u",
            polestar_password="p",
            polestar_vin="",
            polestar_poll_interval=300,
        ),
    )

    async def fake_fetch(self, cfg):
        return snapshot

    monkeypatch.setattr(PolestarEffect, "_fetch", fake_fetch)

    async def go():
        driver = _FakeDriver()
        task = asyncio.create_task(PolestarEffect().run(driver, 100, {}))
        await asyncio.sleep(seconds)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return driver

    return asyncio.run(go())


def test_run_blinks_tip_while_charging(monkeypatch):
    snap = _snapshot(
        soc=50,
        charging="CHARGING_STATUS_CHARGING",
        connection="CHARGER_CONNECTION_STATUS_CONNECTED",
    )
    driver = _run_briefly(monkeypatch, snap, 0.5)

    # The bar is drawn once (50 % -> 10 segments), then only the tip toggles.
    assert len(driver.full_sweeps) == 1
    assert sum(c is not None for c in driver.full_sweeps[0]) == 10
    assert driver.tip_off == [10]
    assert driver.tip_on == [10]


def test_run_does_not_blink_when_not_charging(monkeypatch):
    snap = _snapshot(
        soc=50,
        charging="CHARGING_STATUS_IDLE",
        connection="CHARGER_CONNECTION_STATUS_CONNECTED",
    )
    driver = _run_briefly(monkeypatch, snap, 0.5)

    assert len(driver.full_sweeps) == 1
    assert driver.tip_on == []
    assert driver.tip_off == []


def test_fetch_uses_first_vin_and_logs_out(monkeypatch):
    calls: dict = {}
    monkeypatch.setattr(pypolestar, "PolestarApi", _fake_api(calls, ["VIN123"]))
    cfg = SimpleNamespace(polestar_username="u", polestar_password="p", polestar_vin="")

    snap = asyncio.run(PolestarEffect()._fetch(cfg))

    assert calls["creds"] == ("u", "p")
    assert calls["vin"] == "VIN123"
    assert calls["logout"] is True
    assert snap["soc"] == 72


def test_fetch_prefers_configured_vin(monkeypatch):
    calls: dict = {}
    monkeypatch.setattr(pypolestar, "PolestarApi", _fake_api(calls, ["AUTO"]))
    cfg = SimpleNamespace(polestar_username="u", polestar_password="p", polestar_vin="CHOSEN")

    asyncio.run(PolestarEffect()._fetch(cfg))

    assert calls["vin"] == "CHOSEN"
