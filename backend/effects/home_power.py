from __future__ import annotations

import asyncio
import logging
from typing import Optional

import paho.mqtt.client as mqtt

from .base import BaseEffect, ParamSchema

logger = logging.getLogger(__name__)


def _new_client() -> "mqtt.Client":
    # paho-mqtt 2.x requires an explicit callback API version; 1.x does not
    # accept the argument at all. Support both.
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    except AttributeError:
        return mqtt.Client()


class HomePowerEffect(BaseEffect):
    name = "home_power"
    label = "Home Power"
    description = (
        "Live whole-home power draw (W) from a DSMR P1 smart-meter reader that "
        "publishes to MQTT. The bar fills with load and ramps green (bottom) -> "
        "red (top); it tracks the meter in near-real-time (~1 s). With no data "
        "yet it shows a dim heartbeat."
    )
    params_schema = [
        ParamSchema(
            key="max_w",
            label="Full bar at",
            type="number",
            default=3000,
            min=100,
            max=20000,
            step=100,
            unit="W",
        ),
    ]

    async def run(self, driver, brightness: int, params: dict) -> None:
        from config import get_settings

        cfg = get_settings()
        max_w = float(params.get("max_w", 3000))
        topic = cfg.mqtt_topic
        loop = asyncio.get_running_loop()

        state: dict = {"value": None}

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                client.subscribe(topic)
                logger.info(
                    f"home_power: MQTT connected to {cfg.mqtt_host}:{cfg.mqtt_port}, "
                    f"subscribed {topic}"
                )
            else:
                logger.warning(f"home_power: MQTT connect failed rc={rc}")

        def on_message(client, userdata, msg):
            try:
                state["value"] = float(msg.payload.decode().strip())
            except (ValueError, UnicodeDecodeError):
                logger.debug(f"home_power: ignoring non-numeric payload {msg.payload!r}")

        def on_disconnect(client, userdata, rc):
            logger.warning(f"home_power: MQTT disconnected rc={rc}")

        client = _new_client()
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        client.connect_async(cfg.mqtt_host, cfg.mqtt_port, keepalive=60)
        client.loop_start()

        tick = False
        try:
            while True:
                tick = not tick
                colors = self._compute(state["value"], max_w, brightness, tick)
                await loop.run_in_executor(
                    None, lambda c=colors: driver.set_all_segments(c)
                )
                await asyncio.sleep(1.0)
        finally:
            client.loop_stop()
            try:
                client.disconnect()
            except Exception:
                pass

    @staticmethod
    def _compute(
        value: Optional[float], max_w: float, brightness: int, tick: bool
    ) -> list:
        n = 20

        if value is None:
            # No data yet — dim heartbeat rather than silence.
            v = max(2, round(brightness * 0.06))
            return [(0, 0, v)] * n

        frac = max(0.0, min(1.0, value / max_w)) if max_w > 0 else 0.0
        n_lit = round(frac * n)

        colors: list = []
        for i in range(n):
            if i < n_lit:
                hue = round(120 - (120 / 19) * i)  # green (bottom) -> red (top)
                v = brightness
                if i == n_lit - 1 and not tick:
                    # Pulse the tip so a steady load still reads as alive.
                    v = max(3, round(brightness * 0.5))
                colors.append((hue, 100, v))
            else:
                colors.append(None)
        return colors
