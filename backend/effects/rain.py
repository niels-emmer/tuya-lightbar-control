from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aiohttp

from .base import BaseEffect, ParamSchema

logger = logging.getLogger(__name__)

_OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


class RainEffect(BaseEffect):
    name = "rain"
    label = "Rain Probability"
    description = (
        "Blue bar showing the chance of rain in the coming window. "
        "Empty = 0%, full bar = 100%. Fetches from Open-Meteo every 5 minutes."
    )
    params_schema = [
        ParamSchema(
            key="window",
            label="Forecast window",
            type="select",
            default=30,
            options=[
                {"value": 15, "label": "Next 15 min"},
                {"value": 30, "label": "Next 30 min"},
                {"value": 45, "label": "Next 45 min"},
                {"value": 60, "label": "Next 60 min"},
            ],
        ),
    ]

    async def run(self, driver, brightness: int, params: dict) -> None:
        window = int(params.get("window", 30))
        loop = asyncio.get_running_loop()

        while True:
            try:
                prob = await self._fetch_probability(window, driver)
                colors = self._compute(prob, brightness)
                await loop.run_in_executor(
                    None, lambda c=colors: driver.set_all_segments(c)
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Rain effect error: {e}")
            await asyncio.sleep(300)  # 5 minutes

    async def _fetch_probability(self, window_minutes: int, driver) -> float:
        from config import get_settings
        cfg = get_settings()
        lat = cfg.weather_lat
        lon = cfg.weather_lon

        url = (
            f"{_OPEN_METEO}?latitude={lat}&longitude={lon}"
            "&minutely_15=precipitation_probability&forecast_days=1&timezone=auto"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                r.raise_for_status()
                data = await r.json()

        # Each entry = 15 minutes; take the first N entries for our window
        n_slots = max(1, window_minutes // 15)
        probs = data.get("minutely_15", {}).get("precipitation_probability", [])
        if not probs:
            return 0.0
        return sum(probs[:n_slots]) / n_slots

    def _compute(self, probability: float, brightness: int) -> list:
        # Blue → cyan gradient based on probability
        n_lit = min(20, round(probability / 100 * 20))
        colors = []
        for i in range(20):
            if i < n_lit:
                # Shift from cyan (180) to deep blue (240) as bar fills
                frac = i / 19
                hue = round(180 + frac * 60)
                colors.append((hue, 90, brightness))
            else:
                colors.append((210, 60, max(3, round(brightness * 0.07))))
        return colors
