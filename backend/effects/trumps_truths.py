from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp

from .base import BaseEffect, ParamSchema

logger = logging.getLogger(__name__)

_LOOKUP_URL = "https://truthsocial.com/api/v1/accounts/lookup"
_STATUSES_URL = "https://truthsocial.com/api/v1/accounts/{}/statuses"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; lightbar-monitor/1.0)"}


class TrumpsTruthsEffect(BaseEffect):
    name = "trumps_truths"
    label = "Trump's Truths"
    description = (
        "Live counter of @realDonaldTrump posts on Truth Social in the past N hours. "
        "0 segments = no posts, 20 segments = full bar. Refreshes every 5 minutes."
    )
    params_schema = [
        ParamSchema(
            key="hours",
            label="Count truths in past",
            type="number",
            default=24,
            min=1,
            max=168,
            step=1,
            unit="hours",
        ),
        ParamSchema(
            key="max_truths",
            label="Truths for full bar",
            type="number",
            default=20,
            min=1,
            max=100,
            step=1,
            unit="truths",
        ),
    ]

    def __init__(self) -> None:
        self._account_id: Optional[str] = None

    async def run(self, driver, brightness: int, params: dict) -> None:
        hours = int(params.get("hours", 24))
        max_truths = int(params.get("max_truths", 20))
        loop = asyncio.get_running_loop()

        while True:
            try:
                if self._account_id is None:
                    self._account_id = await self._get_account_id()
                count = await self._count_truths(self._account_id, hours)
                logger.info(f"Trump's Truths: {count} posts in last {hours}h")
                colors = self._build_colors(count, max_truths, brightness)
                await loop.run_in_executor(
                    None, lambda c=colors: driver.set_all_segments(c)
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Trumps Truths effect error: {e}")
                self._account_id = None  # Reset so we retry lookup next time
            await asyncio.sleep(300)  # Refresh every 5 minutes

    async def _get_account_id(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                _LOOKUP_URL,
                params={"acct": "realDonaldTrump"},
                headers=_HEADERS,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                account_id = data["id"]
                logger.info(f"Trump's Truths: resolved account id={account_id}")
                return account_id

    async def _count_truths(self, account_id: str, hours: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        count = 0
        max_id: Optional[str] = None

        async with aiohttp.ClientSession() as session:
            url = _STATUSES_URL.format(account_id)
            while True:
                req_params: dict = {"limit": 40, "exclude_replies": "false"}
                if max_id:
                    req_params["max_id"] = max_id

                async with session.get(
                    url,
                    params=req_params,
                    headers=_HEADERS,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    resp.raise_for_status()
                    statuses = await resp.json()

                if not statuses:
                    break

                done = False
                for status in statuses:
                    created_raw = status.get("created_at", "")
                    created_at = datetime.fromisoformat(
                        created_raw.replace("Z", "+00:00")
                    )
                    if created_at < cutoff:
                        done = True
                        break
                    count += 1

                if done:
                    break

                max_id = statuses[-1]["id"]

        return count

    def _build_colors(self, count: int, max_truths: int, brightness: int) -> list:
        filled = min(20, round(count / max_truths * 20))
        colors = []
        for i in range(20):
            # Gradient: green (hue=120) at bottom → yellow (60) → red (0) at top
            hue = round(120 - (120 / 19) * i)
            if i < filled:
                colors.append((hue, 100, brightness))
            else:
                colors.append(None)
        return colors
