"""Effect registry and pure-rendering tests."""

from effects.registry import get_effect, list_effects

EXPECTED = {
    "crypto",
    "rain",
    "countdown",
    "random",
    "trumps_truths",
    "network_traffic",
    "claude_usage",
    "air_quality",
    "home_power",
    "polestar",
}


def test_all_effects_registered():
    assert {e["name"] for e in list_effects()} == EXPECTED


def test_effect_dict_shape():
    for e in list_effects():
        assert {"name", "label", "description", "params"} <= set(e)
        for p in e["params"]:
            assert {"key", "label", "type"} <= set(p)


def test_get_effect_unknown_is_none():
    assert get_effect("does-not-exist") is None


def test_home_power_rendering():
    from effects.home_power import HomePowerEffect

    e = HomePowerEffect()
    # No data yet -> dim heartbeat (80 * 0.06 -> 5).
    assert e._compute(None, 3000, 80, True) == [(0, 0, 5)] * 20
    # Zero load -> nothing lit.
    assert e._compute(0, 3000, 100, True) == [None] * 20
    # Full load -> all lit, green at the bottom, red at the top.
    full = e._compute(3000, 3000, 100, True)
    assert all(c is not None for c in full)
    assert full[0][0] == 120 and full[-1][0] == 0


def test_air_quality_band_hue():
    from effects.air_quality import AirQualityEffect

    assert AirQualityEffect._band_hue(0.10) == 120  # good
    assert AirQualityEffect._band_hue(0.50) == 60   # moderate
    assert AirQualityEffect._band_hue(0.95) == 0    # very poor


def test_claude_usage_n_lit():
    from effects.claude_usage import ClaudeUsageEffect

    assert ClaudeUsageEffect._n_lit(None) == -1     # sentinel: no data
    assert ClaudeUsageEffect._n_lit(0) == 20        # budget untouched
    assert ClaudeUsageEffect._n_lit(100) == 0       # exhausted
