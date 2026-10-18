from __future__ import annotations

import base64
import logging
import threading
import time
from contextlib import contextmanager
from typing import Iterator, Optional

import tinytuya

logger = logging.getLogger(__name__)

# DP 61 payload layout (13 bytes, base64-encoded):
#   [0x00][0x01][0x00][0x14=20segs][mode][H hi][H lo][S hi][S lo][V hi][V lo][0x81][seg]
# mode 0x01 = solid colour ON, 0x02 = segment off.
_SEGMENT_COUNT = 20


def hsv_to_tuya(h: float, s: float, v: float) -> str:
    """Convert HSV (h:0-360, s:0-100, v:0-100) to Tuya 12-char hex.

    Tuya encoding: hue is raw 0-360 as 4-digit hex; sat and val are
    scaled 0-1000 (i.e. multiply by 10). Confirmed from device observations:
    blue (hue=231) → 00e7 (=231), not 0281 (=641 which scaling would give).
    """
    hh = int(max(0, min(360, h)))
    ss = int(max(0, min(1000, s * 10)))
    vv = int(max(0, min(1000, v * 10)))
    return f"{hh:04x}{ss:04x}{vv:04x}"


def tuya_to_hsv(hex_str: str) -> tuple[float, float, float]:
    """Parse Tuya 12-char hex back to HSV (h:0-360, s:0-100, v:0-100)."""
    if len(hex_str) != 12:
        return 0.0, 0.0, 0.0
    hh = int(hex_str[0:4], 16)
    ss = int(hex_str[4:8], 16)
    vv = int(hex_str[8:12], 16)
    return float(hh), ss / 10.0, vv / 10.0


def _segment_payload(segment: int, color: Optional[tuple[float, float, float]]) -> str:
    """Build the base64-encoded DP 61 payload for one segment.

    ``color`` is an (h, s, v) tuple, or ``None`` to turn the segment off.
    """
    seg = max(1, min(_SEGMENT_COUNT, int(segment)))
    if color is None:
        data = bytes([
            0x00, 0x01, 0x00, 0x14, 0x02,   # header + mode: OFF
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # h, s, v = 0
            0x81, seg,
        ])
    else:
        h, s, v = color
        hh = int(max(0, min(360, h)))
        ss = int(max(0, min(1000, s * 10)))
        vv = int(max(0, min(1000, v * 10)))
        data = bytes([
            0x00, 0x01, 0x00, 0x14, 0x01,   # header + mode: solid colour ON
            (hh >> 8) & 0xFF, hh & 0xFF,    # hue   big-endian uint16
            (ss >> 8) & 0xFF, ss & 0xFF,    # sat   big-endian uint16
            (vv >> 8) & 0xFF, vv & 0xFF,    # val   big-endian uint16
            0x81, seg,
        ])
    return base64.b64encode(data).decode()


class LightbarDriver:
    """Thread-safe wrapper around tinytuya BulbDevice.

    Each operation opens a short-lived connection and always closes it; the
    device only tolerates one in-flight command at a time, so all access is
    serialised through a lock.
    """

    def __init__(self, device_id: str, ip: str, local_key: str, version: float = 3.5):
        self._device_id = device_id
        self._ip = ip
        self._local_key = local_key
        self._version = version
        self._lock = threading.Lock()
        self._device: tinytuya.BulbDevice | None = None
        self._online = False
        # True once a per-segment (DP 61) or scene (DP 51) write has happened
        # since the last whole-bar (DP 24) write. The device keeps reporting the
        # stale DP 24 register, which no longer describes what is on the bar.
        self._whole_bar_stale = False

    def _connect(self) -> tinytuya.BulbDevice:
        d = tinytuya.BulbDevice(
            dev_id=self._device_id,
            address=self._ip,
            local_key=self._local_key,
            version=self._version,
        )
        d.set_socketTimeout(5)
        d.set_socketRetryLimit(1)
        return d

    @contextmanager
    def _session(self) -> Iterator[tinytuya.BulbDevice]:
        """Open a device connection and always close its socket afterwards."""
        d = self._connect()
        try:
            yield d
        finally:
            try:
                d.close()
            except Exception:
                pass

    def set_color(self, h: float, s: float, v: float) -> bool:
        """Set whole-bar HSV colour (DP 24). Returns True on success."""
        hex_val = hsv_to_tuya(h, s, v)
        with self._lock:
            try:
                with self._session() as d:
                    d.set_value(21, "colour")  # ensure colour mode
                    d.set_value(24, hex_val)
                self._online = True
                self._whole_bar_stale = False
                return True
            except Exception as e:
                logger.warning(f"Lightbar set_color failed: {e}")
                self._online = False
                return False

    def set_power(self, on: bool) -> bool:
        with self._lock:
            try:
                with self._session() as d:
                    d.set_value(20, on)
                self._online = True
                return True
            except Exception as e:
                logger.warning(f"Lightbar set_power failed: {e}")
                self._online = False
                return False

    def set_scene(self, scene_type: int, speed: int, colors: list[tuple[int, int, int]]) -> bool:
        """Send a hardware scene to DP 51.

        scene_type: 0=static, 1=gradient/flow, 2=flash, 3=wave
        speed: 0-100
        colors: list of (r, g, b) tuples, 1-7 entries, each 0-255
        """
        data = bytes([max(0, min(3, scene_type)), max(0, min(100, speed)), 10])
        for r, g, b in colors[:7]:
            data += bytes([max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))])
        payload = base64.b64encode(data).decode()
        with self._lock:
            try:
                with self._session() as d:
                    d.set_value(21, "scene")
                    d.set_value(51, payload)
                self._online = True
                self._whole_bar_stale = True
                return True
            except Exception as e:
                logger.warning(f"Lightbar set_scene failed: {e}")
                self._online = False
                return False

    def set_segment(self, segment: int, h: float, s: float, v: float) -> bool:
        """Set a single LED segment to an HSV colour via DP 61.

        The lightbar has 20 segments indexed 1–20 (left to right). Each call
        targets exactly one segment; other segments are unaffected.
        """
        payload = _segment_payload(segment, (h, s, v))
        with self._lock:
            try:
                with self._session() as d:
                    d.set_value(21, "colour")
                    d.set_value(61, payload)
                self._online = True
                self._whole_bar_stale = True
                return True
            except Exception as e:
                logger.warning(f"Lightbar set_segment failed: {e}")
                self._online = False
                return False

    def set_segment_off(self, segment: int) -> bool:
        """Turn off a single LED segment (DP 61, mode=0x02, colour zeroed)."""
        payload = _segment_payload(segment, None)
        with self._lock:
            try:
                with self._session() as d:
                    d.set_value(21, "colour")
                    d.set_value(61, payload)
                self._online = True
                self._whole_bar_stale = True
                return True
            except Exception as e:
                logger.warning(f"Lightbar set_segment_off failed: {e}")
                self._online = False
                return False

    def set_all_segments(
        self,
        colors: list[tuple[float, float, float] | None],
        segment_delay: float = 0.25,
    ) -> bool:
        """Set all 20 segments in one persistent-connection sweep.

        Much more reliable than calling set_segment() in a loop, because it
        reuses a single TCP socket rather than reconnecting per segment.

        Args:
            colors: list of up to 20 (h, s, v) tuples — or None to turn a
                    segment off. Index 0 = segment 1, index 19 = segment 20.
                    Fewer than 20 entries are fine; missing tail segments are
                    left unchanged.
            segment_delay: seconds between individual segment writes (default
                    0.25 s). Below ~0.2 s the device starts dropping commands.

        Returns True if all writes succeeded.
        """
        with self._lock:
            try:
                with self._session() as d:
                    d.set_value(21, "colour")
                    ok = True
                    for i, entry in enumerate(colors[:_SEGMENT_COUNT]):
                        seg = i + 1
                        result = d.set_value(61, _segment_payload(seg, entry))
                        if isinstance(result, dict) and result.get("Error"):
                            if result.get("Err") == "904":
                                # 904 = tinytuya received a device heartbeat where
                                # it expected an ACK — the command was delivered,
                                # this is a false alarm.
                                logger.debug(
                                    f"set_all_segments seg {seg}: 904 ignored (heartbeat collision)"
                                )
                            else:
                                logger.warning(f"set_all_segments seg {seg} error: {result}")
                                ok = False
                        if i < len(colors) - 1:
                            time.sleep(segment_delay)
                self._online = True
                self._whole_bar_stale = True
                return ok
            except Exception as e:
                logger.warning(f"Lightbar set_all_segments failed: {e}")
                self._online = False
                return False

    def get_status(self) -> dict | None:
        with self._lock:
            try:
                with self._session() as d:
                    status = d.status()
                self._online = True
                # tinytuya returns DP keys as strings; normalise to int.
                return {int(k): v for k, v in status.get("dps", {}).items()}
            except Exception as e:
                logger.warning(f"Lightbar get_status failed: {e}")
                self._online = False
                return None

    @property
    def online(self) -> bool:
        return self._online

    @property
    def whole_bar_stale(self) -> bool:
        """True when DP 24 no longer describes the bar.

        Set once a per-segment (DP 61) or scene (DP 51) write has happened since
        the last whole-bar (DP 24) write — the device keeps reporting the old
        DP 24 value, which is not what is on the bar.
        """
        return self._whole_bar_stale
