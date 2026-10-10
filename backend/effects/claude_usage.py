from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import aiohttp

from .base import BaseEffect, ParamSchema

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 30.0  # daemon itself only refreshes every 60s
_ALTERNATE_INTERVAL = 10.0


class ClaudeUsageEffect(BaseEffect):
    name = "claude_usage"
    label = "Claude Token Budget"
    description = (
        "Gradient bar (green = full budget, red = near limit) showing remaining "
        "Claude Pro usage. Full bar = budget untouched; bar empties as you use "
        "it up, all off once the window is exhausted. Reads the nanoclaw-cyd-"
        "monitor daemon's /usage endpoint (~/nanoclaw-monitor) — no credentials "
        "needed."
    )
    params_schema = [
        ParamSchema(
            key="mode",
            label="Window",
            type="select",
            default="session",
            options=[
                {"value": "session", "label": "Session (5h)"},
                {"value": "weekly", "label": "Weekly"},
                {"value": "alternate", "label": "Alternate (session ↔ weekly)"},
            ],
        ),
    ]

    async def run(self, driver, brightness: int, params: dict) -> None:
        mode = str(params.get("mode", "session"))
        loop = asyncio.get_running_loop()

        session_pct: Optional[float] = None
        weekly_pct: Optional[float] = None
        last_poll = 0.0
        alt_since = time.monotonic()
        showing_weekly = False
        last_key = None

        while True:
            now = time.monotonic()

            if now - last_poll >= _POLL_INTERVAL or last_poll == 0.0:
                try:
                    session_pct, weekly_pct = await self._fetch_usage()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"Claude usage fetch error: {e}")
                last_poll = now

            if mode == "alternate":
                if now - alt_since >= _ALTERNATE_INTERVAL:
                    alt_since = now
                    showing_weekly = not showing_weekly
                active_pct = weekly_pct if showing_weekly else session_pct
                source = "weekly" if showing_weekly else "session"
            elif mode == "weekly":
                active_pct = weekly_pct
                source = "weekly"
            else:
                active_pct = session_pct
                source = "session"

            n_lit = self._n_lit(active_pct)
            key = (source, n_lit)
            if key != last_key:
                colors = self._compute(active_pct, brightness)
                await loop.run_in_executor(
                    None, lambda c=colors: driver.set_all_segments(c)
                )
                last_key = key

            await asyncio.sleep(1.0)

    async def _fetch_usage(self) -> tuple[float, float]:
        from config import get_settings

        cfg = get_settings()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                cfg.claude_usage_url, timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                r.raise_for_status()
                data = await r.json()

        if not data.get("ok", False):
            raise RuntimeError(f"daemon reported not ok: {data}")

        return float(data.get("s", 0)), float(data.get("w", 0))

    @staticmethod
    def _n_lit(utilization_pct: Optional[float]) -> int:
        if utilization_pct is None:
            return -1  # sentinel: no data yet
        remaining_frac = max(0.0, min(1.0, 1.0 - utilization_pct / 100))
        return round(remaining_frac * 20)

    def _compute(self, utilization_pct: Optional[float], brightness: int) -> list:
        if utilization_pct is None:
            # No data yet / fetch failing — dim white heartbeat, not silence
            return [(0, 0, max(3, round(brightness * 0.08)))] * 20

        n_lit = self._n_lit(utilization_pct)
        colors = []
        for i in range(20):
            # Fixed per-position gradient: red (idx 0) -> green (idx 19).
            # Depletes from the green end first, red end stays lit longest.
            frac = i / 19
            hue = round(120 * frac)
            if i < n_lit:
                colors.append((hue, 100, brightness))
            else:
                colors.append(None)
        return colors
