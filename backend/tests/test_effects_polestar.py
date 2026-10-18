"""Polestar effect: pure parsing and rendering (no network, no device)."""

from types import SimpleNamespace

from effects.polestar import PolestarEffect


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


def test_parse_maps_fields():
    snap = PolestarEffect._parse(_telematics())
    assert snap["soc"] == 72
    assert snap["range_km"] == 310
    assert snap["charging_status"] == "CHARGING_STATUS_CHARGING"
    assert snap["connection_status"] == "CHARGER_CONNECTION_STATUS_CONNECTED"
    assert snap["charging_power_watts"] == 11_000
    assert snap["charging_time_min"] == 45
    assert snap["odometer_km"] == 12_346  # metres -> km, rounded


def test_parse_handles_missing_data():
    snap = PolestarEffect._parse(SimpleNamespace(battery=None, odometer=None))
    assert snap["soc"] is None
    assert snap["charging_status"] is None
    assert snap["connection_status"] is None
    assert snap["odometer_km"] is None


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


def test_soc_hue_bands():
    assert PolestarEffect._soc_hue(80) == 120  # green
    assert PolestarEffect._soc_hue(60) == 120
    assert PolestarEffect._soc_hue(40) == 40  # amber
    assert PolestarEffect._soc_hue(10) == 0  # red


def test_compute_no_data_is_dim_heartbeat():
    e = PolestarEffect()
    assert e._compute(None, 80, True) == [(0, 0, 5)] * 20
    # A snapshot without an SOC also falls back to the heartbeat.
    assert e._compute({"soc": None}, 100, True) == [(0, 0, 6)] * 20


def test_compute_charging_is_green_with_pulsing_tip():
    e = PolestarEffect()
    snap = {
        "soc": 50,
        "charging_status": "CHARGING_STATUS_CHARGING",
        "connection_status": "CHARGER_CONNECTION_STATUS_CONNECTED",
    }
    lit = e._compute(snap, 100, True)
    assert sum(c is not None for c in lit) == 10  # 50 % -> 10 segments
    assert lit[0] == (120, 100, 100)  # green while charging
    assert lit[9] == (120, 100, 100)  # tip full on this tick
    # Next tick dims the tip so an active charge is visibly alive.
    dim = e._compute(snap, 100, False)
    assert dim[9][2] < lit[9][2]


def test_compute_disconnected_is_dim_and_static():
    e = PolestarEffect()
    snap = {
        "soc": 80,
        "charging_status": "CHARGING_STATUS_IDLE",
        "connection_status": "CHARGER_CONNECTION_STATUS_DISCONNECTED",
    }
    colors = e._compute(snap, 100, True)
    assert sum(c is not None for c in colors) == 16  # 80 % -> 16 segments
    assert colors[0] == (120, 100, 40)  # green hue, dimmed
    assert colors[15] == colors[14]  # no tip pulse when not charging


def test_compute_connected_idle_uses_soc_hue():
    e = PolestarEffect()
    snap = {
        "soc": 40,
        "charging_status": "CHARGING_STATUS_IDLE",
        "connection_status": "CHARGER_CONNECTION_STATUS_CONNECTED",
    }
    colors = e._compute(snap, 100, True)
    assert colors[0] == (40, 100, 100)  # amber, full brightness
    assert sum(c is not None for c in colors) == 8


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

        async def async_logout(self) -> None:
            calls["logout"] = True

    return FakeApi


def test_fetch_uses_first_vin_and_logs_out(monkeypatch):
    import asyncio

    import pypolestar

    calls: dict = {}
    monkeypatch.setattr(pypolestar, "PolestarApi", _fake_api(calls, ["VIN123"]))
    cfg = SimpleNamespace(polestar_username="u", polestar_password="p", polestar_vin="")

    snap = asyncio.run(PolestarEffect()._fetch(cfg))

    assert calls["creds"] == ("u", "p")
    assert calls["vin"] == "VIN123"
    assert calls["logout"] is True
    assert snap["soc"] == 72


def test_fetch_prefers_configured_vin(monkeypatch):
    import asyncio

    import pypolestar

    calls: dict = {}
    monkeypatch.setattr(pypolestar, "PolestarApi", _fake_api(calls, ["AUTO"]))
    cfg = SimpleNamespace(polestar_username="u", polestar_password="p", polestar_vin="CHOSEN")

    asyncio.run(PolestarEffect()._fetch(cfg))

    assert calls["vin"] == "CHOSEN"
