"""Effect parameter coercion helpers."""

from effects._params import as_choice, as_float, as_int, as_str


def test_as_float_default_on_garbage():
    assert as_float({"x": "abc"}, "x", 1.5) == 1.5
    assert as_float({}, "x", 2.0) == 2.0


def test_as_float_clamps():
    assert as_float({"x": 999}, "x", 1.0, 0, 10) == 10
    assert as_float({"x": -5}, "x", 1.0, 0, 10) == 0


def test_as_int():
    assert as_int({"x": "7"}, "x", 0) == 7
    assert as_int({"x": None}, "x", 3, 1, 5) == 3
    assert as_int({"x": 999}, "x", 0, 0, 60) == 60


def test_as_str_strips_and_bounds():
    assert as_str({"s": "  hi  "}, "s") == "hi"
    assert as_str({"s": 123}, "s", "d") == "d"
    assert len(as_str({"s": "x" * 200}, "s")) == 64


def test_as_choice():
    assert as_choice({"m": "b"}, "m", "a", ("a", "b")) == "b"
    assert as_choice({"m": "z"}, "m", "a", ("a", "b")) == "a"
    assert as_choice({}, "m", "a", ("a", "b")) == "a"
