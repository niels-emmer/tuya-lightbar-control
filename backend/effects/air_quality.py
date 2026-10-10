from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aiohttp

import settings_store
from ._params import as_choice
from .base import BaseEffect, ParamSchema

logger = logging.getLogger(__name__)

_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Air quality changes slowly; refetch every 10 min. Repaint more often than
# that so the tip can pulse and the display reads as live (the ~5 s segment
# sweep paces this loop).
_POLL_INTERVAL = 600.0
_REFRESH_INTERVAL = 1.0

# Value that fills the whole bar, per metric.
_SCALES = {"aqi": 100.0, "pm2_5": 50.0}
# Open-Meteo JSON field for each metric.
_FIELDS = {"aqi": "european_aqi", "pm2_5": "pm2_5"}


class AirQualityEffect(BaseEffect):
    name = "air_quality"
    label = "Air Quality"
    description = (
        "Local air quality as a severity bar: the fill grows with pollution and "
        "the colour ramps green (good) → yellow → orange → red (very poor). The "
        "tip pulses so you can tell it is live. Reads Open-Meteo's air-quality "
        "API at your saved weather location."
    )
    params_schema = [
        ParamSchema(
            key="metric",
            label="Metric",
            type="select",
            default="aqi",
            options=[
                {"value": "aqi", "label": "European AQI"},
                {"value": "pm2_5", "label": "PM2.5 (µg/m³)"},
            ],
        ),
    ]

    async def run(self, driver, brightness: int, params: dict) -> None:
        metric = as_choice(params, "metric", "aqi", tuple(_SCALES))
        loop = asyncio.get_running_loop()

        value: Optional[float] = None
        last_poll = 0.0
        tick = False

        while True:
            now = loop.time()
            if value is None or now - last_poll >= _POLL_INTERVAL:
                try:
                    value = await self._fetch(metric)
                    logger.info(f"Air quality [{metric}] = {value}")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"Air quality fetch error: {e}")
                last_poll = loop.time()

            tick = not tick
            colors = self._compute(value, metric, brightness, tick)
            await loop.run_in_executor(
                None, lambda c=colors: driver.set_all_segments(c)
            )
            await asyncio.sleep(_REFRESH_INTERVAL)

    async def _fetch(self, metric: str) -> float:
        lat, lon = settings_store.weather()
        url = (
            f"{_AQ_URL}?latitude={lat}&longitude={lon}"
            "&current=european_aqi,pm2_5&timezone=auto"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                r.raise_for_status()
                data = await r.json()

        current = data.get("current") or {}
        raw = current.get(_FIELDS[metric])
        if raw is None:
            raise RuntimeError(f"no {_FIELDS[metric]} in air-quality response")
        return float(raw)

    @staticmethod
    def _band_hue(frac: float) -> int:
        """Colour for a fraction of the full scale: green → yellow → red."""
        if frac <= 0.20:
            return 120  # good
        if frac <= 0.40:
            return 90  # fair
        if frac <= 0.60:
            return 60  # moderate
        if frac <= 0.80:
            return 30  # poor
        return 0  # very poor and above

    def _compute(
        self,
        value: Optional[float],
        metric: str,
        brightness: int,
        tick: bool,
    ) -> list:
        n_seg = 20

        if value is None:
            # No data yet / fetch failing — dim heartbeat rather than silence.
            v = max(2, round(brightness * 0.06))
            return [(0, 0, v)] * n_seg

        scale = _SCALES[metric]
        frac = max(0.0, min(1.0, value / scale))
        n_lit = round(frac * n_seg)

        colors: list = []
        for i in range(n_seg):
            if i >= n_lit:
                colors.append(None)
                continue
            # Per-position colour: the bar's tip shows the band for the current
            # level, so a full red bar reads as "very poor".
            hue = self._band_hue((i + 1) / n_seg)
            v = brightness
            if i == n_lit - 1 and not tick:
                # Pulse the tip so a slow-moving metric still looks alive.
                v = max(3, round(brightness * 0.4))
            colors.append((hue, 100, v))
        return colors
