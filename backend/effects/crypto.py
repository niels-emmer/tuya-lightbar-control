from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import aiohttp

from .base import BaseEffect, ParamSchema

logger = logging.getLogger(__name__)

_BINANCE_KLINES = "https://api.binance.com/api/v3/klines"

# Segments are 0-indexed (0 = leftmost, 19 = rightmost).
# CENTER_DEFAULT sits in the middle; green extends right, red extends left.
_NSEG = 20
_CENTER_DEFAULT = 9  # 0-indexed → segment 10 in 1-indexed


class CryptoEffect(BaseEffect):
    name = "crypto"
    label = "Crypto Candlestick"
    description = (
        "Live 1-minute candlestick centred on the rolling 5-minute reference price. "
        "Green segments extend right (price up), red extend left (price down). "
        "Every 5 minutes the reference price advances to the latest 5m close and the "
        "centre resets. The centre also shifts automatically if the move would overflow "
        "the bar."
    )
    params_schema = [
        ParamSchema(
            key="coin",
            label="Coin pair",
            type="text",
            default="BTCUSDT",
            placeholder="e.g. BTCUSDT, ETHUSDT, SOLUSDT",
        ),
        ParamSchema(
            key="max_pct",
            label="% move = half bar",
            type="number",
            default=0.3,
            min=0.05,
            max=20,
            step=0.05,
            unit="%",
        ),
    ]

    async def run(self, driver, brightness: int, params: dict) -> None:
        coin = str(params.get("coin", "BTCUSDT")).upper().strip()
        max_pct = float(params.get("max_pct", 0.3))
        loop = asyncio.get_running_loop()

        # State
        ref_price: Optional[float] = None
        center_idx: int = _CENTER_DEFAULT
        last_5m_ts: float = 0.0  # unix time of last 5m reference update

        while True:
            now = time.monotonic()

            try:
                # ── Fetch latest 1m close and 5m open ──────────────────────
                one_min_close, five_min_open = await asyncio.gather(
                    _fetch_latest_close(coin, "1m"),
                    _fetch_candle_open(coin, "5m"),
                )

                # ── Update 5m reference every 5 minutes ────────────────────
                # Use the OPEN of the current 5m candle as the reference so
                # we always compare against where this 5m period started.
                if ref_price is None or (now - last_5m_ts) >= 300:
                    ref_price = five_min_open
                    center_idx = _CENTER_DEFAULT
                    last_5m_ts = now
                    logger.info(f"Crypto [{coin}] 5m open (ref) updated: {ref_price:.4f}")

                # ── Compute move from reference ─────────────────────────────
                pct = (one_min_close - ref_price) / ref_price * 100
                n_seg = round(abs(pct) / max_pct * 10)
                n_seg = min(n_seg, 10)  # cap at half-bar

                # ── Fit check: shift center if bar would overflow ───────────
                if pct >= 0:
                    # green extends right: need center_idx + n_seg <= 19
                    if center_idx + n_seg > _NSEG - 1:
                        center_idx = _NSEG - 1 - n_seg
                else:
                    # red extends left: need center_idx - n_seg >= 0
                    if center_idx - n_seg < 0:
                        center_idx = n_seg

                center_idx = max(0, min(_NSEG - 1, center_idx))

                # ── Build segment colors ────────────────────────────────────
                colors = _build_colors(pct, n_seg, center_idx, brightness)

                await loop.run_in_executor(
                    None, lambda c=colors: driver.set_all_segments(c)
                )

                logger.info(
                    f"Crypto [{coin}] 1m={one_min_close:.4f} ref={ref_price:.4f} "
                    f"pct={pct:+.3f}% n_seg={n_seg} center={center_idx}"
                )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Crypto effect error ({coin}): {e}")

            await asyncio.sleep(60)


async def _fetch_latest_close(coin: str, interval: str) -> float:
    url = f"{_BINANCE_KLINES}?symbol={coin}&interval={interval}&limit=1"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            r.raise_for_status()
            data = await r.json()
            return float(data[0][4])  # index 4 = close price


async def _fetch_candle_open(coin: str, interval: str) -> float:
    url = f"{_BINANCE_KLINES}?symbol={coin}&interval={interval}&limit=1"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            r.raise_for_status()
            data = await r.json()
            return float(data[0][1])  # index 1 = open price


def _build_colors(
    pct: float,
    n_seg: int,
    center_idx: int,
    brightness: int,
) -> list:
    """Build the 20-entry color list for the current candle state.

    Layout (0-indexed):
      - center_idx:                  dim white marker (reference price)
      - center_idx+1 … center_idx+n: bright green  (price up)
      - center_idx-1 … center_idx-n: bright red    (price down)
      - everything else:             off (None)
    """
    colors: list = [None] * _NSEG

    # Centre marker — dim white so it's visible but not distracting
    center_v = max(5, round(brightness * 0.15))
    colors[center_idx] = (0, 0, center_v)

    if n_seg == 0:
        return colors

    if pct >= 0:
        # Green extends right from center
        for i in range(1, n_seg + 1):
            idx = center_idx + i
            if 0 <= idx < _NSEG:
                colors[idx] = (120, 100, brightness)
    else:
        # Red extends left from center
        for i in range(1, n_seg + 1):
            idx = center_idx - i
            if 0 <= idx < _NSEG:
                colors[idx] = (0, 100, brightness)

    return colors
