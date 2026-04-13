from __future__ import annotations

import asyncio
import logging
import time

from .base import BaseEffect, ParamSchema

logger = logging.getLogger(__name__)


class CountdownEffect(BaseEffect):
    name = "countdown"
    label = "Countdown Timer"
    description = (
        "Amber bar that depletes from right to left over the set duration. "
        "Flashes red when time is up."
    )
    params_schema = [
        ParamSchema(
            key="minutes",
            label="Duration",
            type="number",
            default=10,
            min=1,
            max=120,
            step=1,
            unit="min",
        ),
    ]

    async def run(self, driver, brightness: int, params: dict) -> None:
        minutes = float(params.get("minutes", 10))
        total_seconds = minutes * 60
        start = time.monotonic()
        loop = asyncio.get_running_loop()
        last_n_lit = -1

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= total_seconds:
                break

            remaining_frac = max(0.0, 1.0 - elapsed / total_seconds)
            n_lit = max(0, round(remaining_frac * 20))

            if n_lit != last_n_lit:
                colors = self._compute(n_lit, brightness)
                await loop.run_in_executor(
                    None, lambda c=colors: driver.set_all_segments(c)
                )
                last_n_lit = n_lit

            # Sleep one segment's worth of time, minimum 1s
            interval = max(1.0, total_seconds / 20)
            await asyncio.sleep(interval)

        # Flash red × 3 then leave dim red
        for _ in range(3):
            await loop.run_in_executor(None, lambda: driver.set_color(0, 100, brightness))
            await asyncio.sleep(0.4)
            await loop.run_in_executor(None, lambda: driver.set_color(0, 100, 0))
            await asyncio.sleep(0.4)
        await loop.run_in_executor(None, lambda: driver.set_color(0, 100, max(5, brightness // 6)))

    def _compute(self, n_lit: int, brightness: int) -> list:
        # Amber (hue 35) for lit segments, very dim for empty
        colors = []
        for i in range(20):
            if i < n_lit:
                # Shift from warm yellow (55) at left to orange-red (20) at right
                frac = i / 19
                hue = round(55 - frac * 35)
                colors.append((hue, 100, brightness))
            else:
                colors.append(None)
        return colors
