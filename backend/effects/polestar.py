from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .base import BaseEffect

logger = logging.getLogger(__name__)

# A full 20-segment DP 61 sweep takes ~5 s, so this only bounds the sleep
# between frames — the real frame rate is the sweep itself.
_REFRESH_INTERVAL = 1.0
# Never hammer the Polestar login endpoint: each fetch is a full OIDC login.
_MIN_POLL_INTERVAL = 30
_N_SEGMENTS = 20
# pypolestar GraphQL enum members (see pypolestar.models). An allow-list rather
# than a substring match: CHARGING_STATUS_DISCHARGING / _ERROR also contain
# "CHARGING" but are not an active charge.
_CHARGING_STATUSES = frozenset({"CHARGING_STATUS_CHARGING", "CHARGING_STATUS_SMART_CHARGING"})
_CONNECTED_STATUSES = frozenset({"CHARGER_CONNECTION_STATUS_CONNECTED"})


class PolestarEffect(BaseEffect):
    name = "polestar"
    label = "Polestar"
    description = (
        "Charging state of a Polestar EV, read directly via pypolestar. The bar "
        "fills with state-of-charge; the hue is green (≥ 60 %), amber (≥ 25 %) "
        "or red below. While the car is actively charging the whole bar is green "
        "and its tip pulses; plugged in but idle shows a static SOC bar; "
        "unplugged dims it. With no data it shows a dim heartbeat. Requires "
        "POLESTAR_USERNAME / POLESTAR_PASSWORD (and optionally POLESTAR_VIN)."
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
        tick = False

        while True:
            now = loop.time()
            if configured and (last_poll is None or now - last_poll >= poll_interval):
                try:
                    snapshot = await self._fetch(cfg)
                    logger.info(
                        "polestar: soc=%s charging=%s connection=%s",
                        snapshot.get("soc"),
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

            tick = not tick
            colors = self._compute(snapshot, brightness, tick)
            await loop.run_in_executor(None, lambda c=colors: driver.set_all_segments(c))
            await asyncio.sleep(_REFRESH_INTERVAL)

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
            # The GraphQL telematics query carries no charger-connection or
            # power data; pypolestar's optional gRPC path does. Not every
            # vehicle supports it, so treat it as best-effort.
            try:
                grpc_battery = api.get_grpc_battery(vin)
            except Exception:
                grpc_battery = None
            return self._parse(telematics, grpc_battery)
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
    def _first_vin(api: Any) -> str:
        vins = api.get_available_vins()
        if not vins:
            raise RuntimeError("no vehicles found on this Polestar account")
        return vins[0]

    @staticmethod
    def _parse(telematics: Any, grpc_battery: Any = None) -> dict:
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

        def _enum_name(value: Any) -> Optional[str]:
            return getattr(value, "name", None)

        odometer_m = getattr(odometer, "odometer_meters", None) if odometer is not None else None
        return {
            "soc": _pick(
                _battery("battery_charge_level_percentage"),
                _grpc("battery_charge_level_percentage"),
            ),
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

    def _compute(self, snapshot: Optional[dict], brightness: int, tick: bool) -> list:
        if snapshot is None or snapshot.get("soc") is None:
            # No data yet / fetch failing / no credentials — dim heartbeat.
            return [(0, 0, max(2, round(brightness * 0.06)))] * _N_SEGMENTS

        soc = max(0.0, min(100.0, float(snapshot["soc"])))
        n_lit = round(soc / 100 * _N_SEGMENTS)
        charging = self._is_charging(snapshot.get("charging_status"))
        connected = self._is_connected(snapshot.get("connection_status"))

        # While charging the bar reads green (activity); otherwise the hue
        # encodes SOC health. Unplugged dims the whole bar.
        if charging:
            hue = 120
            value = brightness
        else:
            hue = self._soc_hue(soc)
            value = brightness if connected else max(2, round(brightness * 0.4))

        colors: list = []
        for i in range(_N_SEGMENTS):
            if i >= n_lit:
                colors.append(None)
                continue
            v = value
            if charging and i == n_lit - 1 and not tick:
                # Pulse the tip so an active charge is visibly alive.
                v = max(3, round(brightness * 0.35))
            colors.append((hue, 100, v))
        return colors
