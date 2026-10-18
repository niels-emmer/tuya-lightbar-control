from __future__ import annotations

import asyncio
import logging
from typing import Any, NamedTuple, Optional

from .base import BaseEffect

logger = logging.getLogger(__name__)

# A full 20-segment DP 61 sweep takes ~5 s, so the SOC bar is drawn only when it
# actually changes. An active charge is shown by blinking the tip with
# single-segment DP 61 writes (~200 ms each) — fast enough to read as a pulse,
# where a whole-bar redraw every frame would not be.
_PULSE_INTERVAL = 0.3  # seconds between tip blinks while charging
_IDLE_INTERVAL = 2.0  # seconds between checks when not charging
# Never hammer the Polestar login endpoint: each fetch is a full OIDC login.
_MIN_POLL_INTERVAL = 30
_N_SEGMENTS = 20
# pypolestar GraphQL enum members (see pypolestar.models). An allow-list rather
# than a substring match: CHARGING_STATUS_DISCHARGING / _ERROR also contain
# "CHARGING" but are not an active charge.
_CHARGING_STATUSES = frozenset({"CHARGING_STATUS_CHARGING", "CHARGING_STATUS_SMART_CHARGING"})
_CONNECTED_STATUSES = frozenset({"CHARGER_CONNECTION_STATUS_CONNECTED"})
_CHARGING_HUE = 120
_HEARTBEAT_HUE = 0
# Neutral (white) marker for the charge limit set in the Polestar app.
_MARKER_HUE = 0
_MARKER_SAT = 0


class _Frame(NamedTuple):
    """What the bar should show right now.

    ``target_lit`` is the number of segments the charge limit corresponds to,
    or 0 when unknown / no marker.
    """

    n_lit: int
    hue: int
    value: int
    charging: bool
    target_lit: int = 0


class PolestarEffect(BaseEffect):
    name = "polestar"
    label = "Polestar"
    description = (
        "Charging state of a Polestar EV, read directly via pypolestar. The bar "
        "fills with state-of-charge; the hue is green (≥ 60 %), amber (≥ 25 %) "
        "or red below. While the car is actively charging the bar is green and "
        "its tip blinks; plugged in but idle shows a static SOC bar; unplugged "
        "dims it. A dim marker shows the charge limit set in the app. With no "
        "data it shows a dim heartbeat. Requires POLESTAR_USERNAME / "
        "POLESTAR_PASSWORD (and optionally POLESTAR_VIN)."
    )

    async def run(self, driver, brightness: int, params: dict) -> None:
        from config import get_settings

        cfg = get_settings()
        loop = asyncio.get_running_loop()
        poll_interval = max(_MIN_POLL_INTERVAL, int(cfg.polestar_poll_interval))
        configured = bool(cfg.polestar_username and cfg.polestar_password)
        if not configured:
            logger.warning(
                "polestar: POLESTAR_USERNAME / POLESTAR_PASSWORD not set — "
                "showing the no-data heartbeat"
            )

        snapshot: Optional[dict] = None
        last_poll: Optional[float] = None
        drawn: Optional[_Frame] = None
        tip_on = True

        while True:
            now = loop.time()
            if configured and (last_poll is None or now - last_poll >= poll_interval):
                try:
                    snapshot = await self._fetch(cfg)
                    logger.info(
                        "polestar: soc=%s target=%s charging=%s connection=%s",
                        snapshot.get("soc"),
                        snapshot.get("target_soc"),
                        snapshot.get("charging_status"),
                        snapshot.get("connection_status"),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    # Log the type and chained cause: pypolestar raises
                    # PolestarApiException with an empty message, hiding the
                    # real GraphQL error underneath it.
                    logger.warning(
                        f"polestar fetch error: {type(e).__name__}: {e}", exc_info=True
                    )
                last_poll = loop.time()

            frame = self._state(snapshot, brightness)

            # Redraw the whole bar only when it changes — a sweep is ~5 s, so
            # this must not run every frame.
            if frame != drawn:
                colors = self._colors(frame)
                await loop.run_in_executor(None, lambda c=colors: driver.set_all_segments(c))
                drawn = frame
                tip_on = True

            if frame.charging and frame.n_lit > 0:
                # Blink the tip so an active charge is visible. Single-segment
                # writes are ~200 ms; a whole-bar redraw would be ~5 s.
                tip_on = not tip_on
                tip = frame.n_lit
                if tip_on:
                    await loop.run_in_executor(
                        None,
                        lambda s=tip, h=frame.hue, v=frame.value: driver.set_segment(s, h, 100, v),
                    )
                else:
                    await loop.run_in_executor(None, lambda s=tip: driver.set_segment_off(s))
                await asyncio.sleep(_PULSE_INTERVAL)
            else:
                await asyncio.sleep(_IDLE_INTERVAL)

    async def _fetch(self, cfg: Any) -> dict:
        # Imported lazily so the app (and its tests) don't require pypolestar
        # unless this effect is actually used.
        from pypolestar import PolestarApi

        # pypolestar's gql session spawns a persistent reconnect task that
        # async_logout() closes the socket for but never cancels. Snapshot the
        # task set and cancel whatever it leaks, or every poll leaks a task.
        tasks_before = set(asyncio.all_tasks())
        api = PolestarApi(username=cfg.polestar_username, password=cfg.polestar_password)
        try:
            await api.async_init()
            vin = cfg.polestar_vin or self._first_vin(api)
            await api.update_latest_data(vin=vin, update_telematics=True)
            telematics = api.get_car_telematics(vin)
            if telematics is None:
                raise RuntimeError("telematics returned None after update")
            # The GraphQL telematics query carries no charger-connection,
            # power or charge-limit data; pypolestar's optional gRPC path does.
            # Not every vehicle supports it, so treat it as best-effort.
            return self._parse(telematics, self._grpc(api, "get_grpc_battery", vin),
                               self._grpc(api, "get_grpc_target_soc", vin))
        finally:
            try:
                await api.async_logout()
            except Exception:
                pass
            leaked = set(asyncio.all_tasks()) - tasks_before
            for task in leaked:
                task.cancel()
            if leaked:
                await asyncio.gather(*leaked, return_exceptions=True)

    @staticmethod
    def _grpc(api: Any, method: str, vin: str) -> Any:
        """Call an optional pypolestar gRPC getter, tolerating any failure."""
        try:
            return getattr(api, method)(vin)
        except Exception:
            return None

    @staticmethod
    def _first_vin(api: Any) -> str:
        vins = api.get_available_vins()
        if not vins:
            raise RuntimeError("no vehicles found on this Polestar account")
        return vins[0]

    @staticmethod
    def _parse(telematics: Any, grpc_battery: Any = None, grpc_target: Any = None) -> dict:
        battery = getattr(telematics, "battery", None)
        odometer = getattr(telematics, "odometer", None)

        def _pick(*values: Any) -> Any:
            for value in values:
                if value is not None:
                    return value
            return None

        def _battery(attr: str) -> Any:
            return getattr(battery, attr, None) if battery is not None else None

        def _grpc(attr: str) -> Any:
            return getattr(grpc_battery, attr, None) if grpc_battery is not None else None

        def _target(attr: str) -> Any:
            return getattr(grpc_target, attr, None) if grpc_target is not None else None

        def _enum_name(value: Any) -> Optional[str]:
            return getattr(value, "name", None)

        odometer_m = getattr(odometer, "odometer_meters", None) if odometer is not None else None
        return {
            "soc": _pick(
                _battery("battery_charge_level_percentage"),
                _grpc("battery_charge_level_percentage"),
            ),
            "target_soc": _target("battery_charge_target_level"),
            "range_km": _battery("estimated_distance_to_empty_km"),
            "charging_status": _enum_name(_battery("charging_status")),
            "connection_status": _enum_name(
                _pick(_grpc("charger_connection_status"), _battery("charger_connection_status"))
            ),
            "charging_power_watts": _pick(
                _grpc("charging_power_watts"), _battery("charging_power_watts")
            ),
            "charging_time_min": _battery("estimated_charging_time_to_full_minutes"),
            "odometer_km": round(odometer_m / 1000) if odometer_m is not None else None,
        }

    @staticmethod
    def _is_charging(status: Optional[str]) -> bool:
        return status in _CHARGING_STATUSES

    @staticmethod
    def _is_connected(status: Optional[str]) -> bool:
        return status in _CONNECTED_STATUSES

    @staticmethod
    def _soc_hue(soc: float) -> int:
        if soc >= 60:
            return 120  # green
        if soc >= 25:
            return 40  # amber
        return 0  # red

    @staticmethod
    def _lit_for(pct: Any) -> int:
        """Segments a 0–100 percentage fills, clamped to the bar."""
        value = max(0.0, min(100.0, float(pct)))
        return round(value / 100 * _N_SEGMENTS)

    @staticmethod
    def _state(snapshot: Optional[dict], brightness: int) -> _Frame:
        if snapshot is None or snapshot.get("soc") is None:
            # No data yet / fetch failing / no credentials — dim heartbeat.
            return _Frame(_N_SEGMENTS, _HEARTBEAT_HUE, max(2, round(brightness * 0.06)), False)

        n_lit = PolestarEffect._lit_for(snapshot["soc"])
        target_lit = 0
        if snapshot.get("target_soc") is not None:
            target_lit = PolestarEffect._lit_for(snapshot["target_soc"])

        if PolestarEffect._is_charging(snapshot.get("charging_status")):
            # While charging the bar reads green; the tip blinks (in run()).
            return _Frame(n_lit, _CHARGING_HUE, brightness, True, target_lit)

        hue = PolestarEffect._soc_hue(float(snapshot["soc"]))
        connected = PolestarEffect._is_connected(snapshot.get("connection_status"))
        value = brightness if connected else max(2, round(brightness * 0.4))
        return _Frame(n_lit, hue, value, False, target_lit)

    @staticmethod
    def _colors(frame: _Frame) -> list:
        """The static bar: the SOC fill, plus a dim marker at the charge limit."""
        marker_v = max(3, round(frame.value * 0.4))
        colors: list = []
        for i in range(_N_SEGMENTS):
            if i < frame.n_lit:
                colors.append((frame.hue, 100, frame.value))
            elif frame.target_lit and i == frame.target_lit - 1:
                # Charge limit sits ahead of the fill — mark it so you can see
                # how close you are (it disappears once the fill reaches it).
                colors.append((_MARKER_HUE, _MARKER_SAT, marker_v))
            else:
                colors.append(None)
        return colors
