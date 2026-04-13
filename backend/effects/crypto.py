from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import aiohttp

from .base import BaseEffect, ParamSchema

logger = logging.getLogger(__name__)

_WS_BASE = "wss://stream.binance.com:9443/stream"
_NSEG = 20
_CENTER_DEFAULT = 9  # 0-indexed; segment 10 in 1-indexed


class CryptoEffect(BaseEffect):
    name = "crypto"
    label = "Crypto Candlestick"
    description = (
        "Live candlestick via Binance WebSocket. "
        "The centre marker (dim white) represents the 5-minute open price. "
        "Green segments extend right (price up), red extend left (price down). "
        "The display updates as fast as the hardware allows (~5 s/sweep). "
        "When a new 5-minute candle opens the centre resets to the middle."
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

        coin_lower = coin.lower()
        streams = f"{coin_lower}@kline_1m/{coin_lower}@kline_5m"
        url = f"{_WS_BASE}?streams={streams}"

        # Mutable state shared between the WS reader and the writer task
        state = {
            "ref_price": None,       # 5m open — the centre reference
            "prev_5m_open": None,    # detect when a new 5m candle starts
            "center_idx": _CENTER_DEFAULT,
            "busy": False,           # True while set_all_segments is running
            "tick": False,           # alternates on each data push (sign of life)
        }

        async def _push(colors: list) -> None:
            """Run set_all_segments in a thread; clear busy flag when done."""
            try:
                await loop.run_in_executor(
                    None, lambda c=colors: driver.set_all_segments(c)
                )
            finally:
                state["busy"] = False

        while True:  # outer loop: reconnect on disconnect / error
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(
                        url,
                        heartbeat=20,
                        receive_timeout=60,
                    ) as ws:
                        logger.info(f"Crypto [{coin}] WebSocket connected")

                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                _handle_message(
                                    msg.data, coin, max_pct, brightness,
                                    state, loop, _push,
                                )
                            elif msg.type in (
                                aiohttp.WSMsgType.ERROR,
                                aiohttp.WSMsgType.CLOSED,
                            ):
                                logger.warning(f"Crypto [{coin}] WS closed/error")
                                break

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Crypto [{coin}] WS error: {e} — reconnecting in 5 s")

            await asyncio.sleep(5)


def _handle_message(
    raw: str,
    coin: str,
    max_pct: float,
    brightness: int,
    state: dict,
    loop: asyncio.AbstractEventLoop,
    push_fn,
) -> None:
    try:
        envelope = json.loads(raw)
    except Exception:
        return

    stream: str = envelope.get("stream", "")
    k: dict = envelope.get("data", {}).get("k", {})
    if not k:
        return

    # ── 5m kline: track the open as our reference price ──────────────────────
    if "@kline_5m" in stream:
        new_open = float(k["o"])
        if new_open != state["prev_5m_open"]:
            state["ref_price"] = new_open
            state["prev_5m_open"] = new_open
            state["center_idx"] = _CENTER_DEFAULT
            logger.info(f"Crypto [{coin}] new 5m candle — ref={new_open:.4f}")
        return

    # ── 1m kline: update display ──────────────────────────────────────────────
    if "@kline_1m" not in stream:
        return

    ref_price: Optional[float] = state["ref_price"]
    if ref_price is None:
        return  # wait for first 5m event

    current_price = float(k["c"])
    pct = (current_price - ref_price) / ref_price * 100
    n_seg = min(10, round(abs(pct) / max_pct * 10))

    # Fit check: shift centre so the candle stays on the bar
    center_idx: int = state["center_idx"]
    if pct >= 0:
        if center_idx + n_seg > _NSEG - 1:
            center_idx = _NSEG - 1 - n_seg
    else:
        if center_idx - n_seg < 0:
            center_idx = n_seg
    center_idx = max(0, min(_NSEG - 1, center_idx))
    state["center_idx"] = center_idx

    logger.debug(
        f"Crypto [{coin}] price={current_price:.4f} ref={ref_price:.4f} "
        f"pct={pct:+.3f}% n_seg={n_seg} center={center_idx}"
    )

    # Only push if the previous sweep has finished
    if state["busy"]:
        return

    state["tick"] = not state["tick"]
    colors = _build_colors(pct, n_seg, center_idx, brightness, state["tick"])
    state["busy"] = True
    asyncio.create_task(push_fn(colors))


def _build_colors(
    pct: float,
    n_seg: int,
    center_idx: int,
    brightness: int,
    tick: bool = False,
) -> list:
    colors: list = [None] * _NSEG

    # Centre marker — alternates between dim and mid white as sign of life
    centre_v = round(brightness * 0.4) if tick else max(5, round(brightness * 0.15))
    colors[center_idx] = (0, 0, centre_v)

    if n_seg == 0:
        return colors

    if pct >= 0:
        for i in range(1, n_seg + 1):
            idx = center_idx + i
            if 0 <= idx < _NSEG:
                colors[idx] = (120, 100, brightness)
    else:
        for i in range(1, n_seg + 1):
            idx = center_idx - i
            if 0 <= idx < _NSEG:
                colors[idx] = (0, 100, brightness)

    return colors
