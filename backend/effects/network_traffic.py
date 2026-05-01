from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Optional

from .base import BaseEffect, ParamSchema

# Try host-mounted /proc/net first (Docker with bridge networking),
# fall back to /proc/net/dev when running on the host directly.
_PROC_CANDIDATES = ["/host_proc_net/dev", "/proc/net/dev"]


def _find_proc_path() -> str:
    for p in _PROC_CANDIDATES:
        if Path(p).exists():
            return p
    return "/proc/net/dev"


def _parse_net_dev(path: str) -> dict[str, tuple[int, int]]:
    """Return {iface: (rx_bytes, tx_bytes)} parsed from /proc/net/dev."""
    result: dict[str, tuple[int, int]] = {}
    with open(path) as f:
        lines = f.readlines()
    for line in lines[2:]:  # skip 2 header lines
        colon = line.find(":")
        if colon == -1:
            continue
        iface = line[:colon].strip()
        cols = line[colon + 1:].split()
        if len(cols) >= 9:
            result[iface] = (int(cols[0]), int(cols[8]))
    return result


def _pick_iface(requested: str, stats: dict[str, tuple[int, int]]) -> Optional[str]:
    if requested and requested in stats:
        return requested
    for name in stats:
        if name != "lo":
            return name
    return None


def _build_colors(
    rx_bps: float,
    tx_bps: float,
    max_bps: float,
    brightness: int,
    blink_on: bool,
) -> list[Optional[tuple[int, int, int]]]:
    colors: list[Optional[tuple[int, int, int]]] = [None] * 20

    # RX: segments 1-9 (indices 0-8), fills from index 8 (center) downward
    rx_frac = min(1.0, rx_bps / max_bps) if max_bps > 0 else 0.0
    rx_lit = round(rx_frac * 9)
    for offset in range(9):
        # offset 0 = index 8 (closest to center), offset 8 = index 0 (bottom)
        if offset < rx_lit:
            colors[8 - offset] = (220, 100, brightness)

    # TX: segments 12-20 (indices 11-19), fills from index 11 (center) upward
    tx_frac = min(1.0, tx_bps / max_bps) if max_bps > 0 else 0.0
    tx_lit = round(tx_frac * 9)
    for offset in range(9):
        # offset 0 = index 11 (closest to center), offset 8 = index 19 (top)
        if offset < tx_lit:
            colors[11 + offset] = (120, 100, brightness)

    # Center: segments 10-11 (indices 9-10), white, blinks each cycle
    center_v = brightness if blink_on else max(3, round(brightness * 0.25))
    colors[9] = (0, 0, center_v)
    colors[10] = (0, 0, center_v)

    return colors


class NetworkTrafficEffect(BaseEffect):
    name = "network_traffic"
    label = "Network Traffic"
    description = (
        "Bottom 9 segments = incoming (RX, blue), top 9 = outgoing (TX, green). "
        "Center dot pulses white. Set max_mbps to match your uplink speed."
    )
    params_schema = [
        ParamSchema(
            key="interface",
            label="Interface",
            type="text",
            default="",
            placeholder="auto-detect",
        ),
        ParamSchema(
            key="max_mbps",
            label="Max bandwidth",
            type="number",
            default=100,
            min=1,
            max=10000,
            step=1,
            unit="Mbps",
        ),
    ]

    async def run(self, driver: Any, brightness: int, params: dict) -> None:
        iface_req = str(params.get("interface", "")).strip()
        max_bps = float(params.get("max_mbps", 100)) * 1_000_000 / 8
        loop = asyncio.get_running_loop()
        proc_path = _find_proc_path()

        # Bootstrap: 1-second pre-sample so the first frame shows real data
        s0 = _parse_net_dev(proc_path)
        iface = _pick_iface(iface_req, s0)
        await asyncio.sleep(1.0)
        s1 = _parse_net_dev(proc_path)
        iface = iface or _pick_iface(iface_req, s1)

        rx_bps = tx_bps = 0.0
        if iface and iface in s0 and iface in s1:
            rx_bps = max(0.0, float(s1[iface][0] - s0[iface][0]))
            tx_bps = max(0.0, float(s1[iface][1] - s0[iface][1]))

        blink_on = True
        colors = _build_colors(rx_bps, tx_bps, max_bps, brightness, blink_on)

        while True:
            t0 = time.monotonic()
            snap0 = _parse_net_dev(proc_path)
            await loop.run_in_executor(
                None, lambda c=colors: driver.set_all_segments(c)
            )
            t1 = time.monotonic()
            snap1 = _parse_net_dev(proc_path)

            dt = (t1 - t0) or 1.0
            iface = _pick_iface(iface_req, snap1) or iface
            if iface and iface in snap0 and iface in snap1:
                rx_bps = max(0.0, (snap1[iface][0] - snap0[iface][0]) / dt)
                tx_bps = max(0.0, (snap1[iface][1] - snap0[iface][1]) / dt)

            blink_on = not blink_on
            colors = _build_colors(rx_bps, tx_bps, max_bps, brightness, blink_on)
