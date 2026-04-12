from __future__ import annotations

import asyncio
import math
import logging

from .base import BaseEffect, ParamSchema

logger = logging.getLogger(__name__)

_SPEED_MAP = {"slow": 8, "medium": 22, "fast": 55}
_PULSE_SPEED_MAP = {"slow": 0.04, "medium": 0.10, "fast": 0.24}


class RandomEffect(BaseEffect):
    name = "random"
    label = "Patterns"
    description = (
        "Animated light patterns: rainbow sweeps, color blobs, moving dots, or a breathing pulse."
    )
    params_schema = [
        ParamSchema(
            key="style",
            label="Style",
            type="select",
            default="rainbow",
            options=[
                {"value": "rainbow", "label": "Rainbow"},
                {"value": "blobs", "label": "Color Blobs"},
                {"value": "dots", "label": "Running Dots"},
                {"value": "pulse", "label": "Pulse"},
            ],
        ),
        ParamSchema(
            key="speed",
            label="Speed",
            type="select",
            default="medium",
            options=[
                {"value": "slow", "label": "Slow"},
                {"value": "medium", "label": "Medium"},
                {"value": "fast", "label": "Fast"},
            ],
        ),
        ParamSchema(
            key="colors",
            label="Color mode",
            type="select",
            default="multi",
            options=[
                {"value": "multi", "label": "Multi-color"},
                {"value": "single", "label": "Single color"},
            ],
        ),
        ParamSchema(
            key="hue",
            label="Hue (single-color mode)",
            type="slider",
            default=200,
            min=0,
            max=359,
            step=1,
        ),
    ]

    async def run(self, driver, brightness: int, params: dict) -> None:
        style = params.get("style", "rainbow")
        speed = params.get("speed", "medium")
        color_mode = params.get("colors", "multi")
        hue_param = int(params.get("hue", 200))
        loop = asyncio.get_running_loop()

        if style == "pulse":
            await self._run_pulse(driver, brightness, speed, color_mode, hue_param, loop)
        else:
            await self._run_segment(
                driver, brightness, style, speed, color_mode, hue_param, loop
            )

    # ------------------------------------------------------------------
    # Pulse — whole-bar breathing, fast update rate
    # ------------------------------------------------------------------

    async def _run_pulse(self, driver, brightness, speed, color_mode, hue_param, loop):
        t = 0.0
        dt = _PULSE_SPEED_MAP.get(speed, 0.10)
        while True:
            v = round(brightness * (0.25 + 0.75 * (0.5 + 0.5 * math.sin(t * math.pi))))
            h = (hue_param + round(t * 30)) % 360 if color_mode == "multi" else hue_param
            await loop.run_in_executor(None, lambda hh=h, vv=v: driver.set_color(hh, 100, max(1, vv)))
            await asyncio.sleep(0.25)
            t += dt

    # ------------------------------------------------------------------
    # Segment patterns — rainbow, blobs, dots
    # ------------------------------------------------------------------

    async def _run_segment(
        self, driver, brightness, style, speed, color_mode, hue_param, loop
    ):
        step = _SPEED_MAP.get(speed, 22)
        hue_base = 0
        while True:
            colors = self._compute_segments(style, hue_base, color_mode, hue_param, brightness)
            await loop.run_in_executor(
                None, lambda c=colors: driver.set_all_segments(c, segment_delay=0.2)
            )
            hue_base = (hue_base + step) % 360

    def _compute_segments(self, style, hue_base, color_mode, hue_param, brightness):
        if style == "rainbow":
            return self._rainbow(hue_base, color_mode, hue_param, brightness)
        if style == "blobs":
            return self._blobs(hue_base, color_mode, hue_param, brightness)
        return self._dots(hue_base, color_mode, hue_param, brightness)

    def _rainbow(self, hue_base, color_mode, hue_param, brightness):
        colors = []
        for i in range(20):
            if color_mode == "multi":
                h = (hue_base + i * 18) % 360
            else:
                v_frac = 0.5 + 0.5 * math.sin(math.pi * i / 19 + hue_base / 60)
                colors.append((hue_param, 100, round(brightness * v_frac)))
                continue
            colors.append((h, 100, brightness))
        return colors

    def _blobs(self, hue_base, color_mode, hue_param, brightness):
        # Three gaussian blobs drifting across the bar
        pos = hue_base / 18  # float position 0–20
        blob_offsets = [0, 7, 14]
        colors = []
        for i in range(20):
            intensity = 0.0
            for offset in blob_offsets:
                bp = (pos + offset) % 20
                dist = min(abs(i - bp), 20 - abs(i - bp))
                intensity = max(intensity, math.exp(-(dist ** 2) / 3.5))
            v = round(brightness * intensity)
            if v < 4:
                colors.append(None)
            else:
                h = (hue_base + i * 18) % 360 if color_mode == "multi" else hue_param
                colors.append((h, 95, v))
        return colors

    def _dots(self, hue_base, color_mode, hue_param, brightness):
        pos = hue_base / 18  # float position 0–20
        dot_positions = [pos % 20, (pos + 10) % 20]
        colors = []
        for i in range(20):
            d = min(
                abs(i - dp) if abs(i - dp) <= 10 else 20 - abs(i - dp)
                for dp in dot_positions
            )
            v = round(brightness * math.exp(-(d ** 2) / 1.2))
            if v < 4:
                colors.append(None)
            else:
                h = (hue_base + i * 30) % 360 if color_mode == "multi" else hue_param
                colors.append((h, 100, v))
        return colors
