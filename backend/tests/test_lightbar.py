"""Driver encoding tests: HSV<->Tuya hex and the DP 61 segment payload."""

import base64

from lightbar import LightbarDriver, _segment_payload, hsv_to_tuya, tuya_to_hsv


def _decode(payload: str) -> bytes:
    return base64.b64decode(payload)


class _FakeDevice:
    """Minimal stand-in for tinytuya.BulbDevice (records DP writes)."""

    def __init__(self) -> None:
        self.values: dict[int, object] = {}

    def set_value(self, dp: int, value: object) -> dict:
        self.values[dp] = value
        return {"Error": None}

    def close(self) -> None:
        pass


def _driver(monkeypatch) -> LightbarDriver:
    d = LightbarDriver("dev", "1.2.3.4", "key")
    monkeypatch.setattr(d, "_connect", _FakeDevice)
    return d


class TestHsvEncoding:
    def test_blue_hue_is_raw_degrees(self):
        # hue 231 -> 00e7 (raw degrees); sat/val are scaled x10 (0-1000).
        assert hsv_to_tuya(231, 100, 100) == "00e703e803e8"

    def test_clamps_out_of_range(self):
        assert hsv_to_tuya(-5, 200, 200) == hsv_to_tuya(0, 100, 100)

    def test_round_trip(self):
        assert tuya_to_hsv(hsv_to_tuya(120, 50, 25)) == (120.0, 50.0, 25.0)

    def test_bad_length_returns_zero(self):
        assert tuya_to_hsv("nope") == (0.0, 0.0, 0.0)


class TestSegmentPayload:
    def test_on_payload_layout(self):
        data = _decode(_segment_payload(3, (231, 100, 50)))
        assert len(data) == 13
        assert data[0:5] == bytes([0x00, 0x01, 0x00, 0x14, 0x01])  # header + mode ON
        assert data[5:7] == bytes([0x00, 0xE7])   # hue 231
        assert data[7:9] == bytes([0x03, 0xE8])   # sat 1000
        assert data[9:11] == bytes([0x01, 0xF4])  # val 500
        assert data[11] == 0x81
        assert data[12] == 3

    def test_off_payload(self):
        data = _decode(_segment_payload(5, None))
        assert data[4] == 0x02          # mode OFF
        assert data[5:11] == bytes(6)   # h, s, v all zero
        assert data[12] == 5

    def test_segment_index_is_clamped(self):
        assert _decode(_segment_payload(0, None))[12] == 1


class TestWholeBarStaleness:
    """DP 24 stops describing the bar once segments/scene are written."""

    def test_fresh_driver_is_not_stale(self, monkeypatch):
        assert _driver(monkeypatch).whole_bar_stale is False

    def test_segment_write_marks_stale(self, monkeypatch):
        d = _driver(monkeypatch)
        d.set_segment(1, 0, 100, 100)
        assert d.whole_bar_stale is True

    def test_segment_off_marks_stale(self, monkeypatch):
        d = _driver(monkeypatch)
        d.set_segment_off(1)
        assert d.whole_bar_stale is True

    def test_sweep_marks_stale(self, monkeypatch):
        d = _driver(monkeypatch)
        d.set_all_segments([(0, 100, 100)] * 2, segment_delay=0)
        assert d.whole_bar_stale is True

    def test_scene_marks_stale(self, monkeypatch):
        d = _driver(monkeypatch)
        d.set_scene(1, 50, [(255, 0, 0)])
        assert d.whole_bar_stale is True

    def test_set_color_clears_staleness(self, monkeypatch):
        d = _driver(monkeypatch)
        d.set_all_segments([(0, 100, 100)] * 2, segment_delay=0)
        assert d.whole_bar_stale is True
        d.set_color(0, 100, 100)
        assert d.whole_bar_stale is False
        assert _decode(_segment_payload(99, None))[12] == 20
