"""Safe coercion helpers for effect parameters.

Effect params arrive as untyped JSON from ``POST /api/effect``. These helpers
coerce them to the expected type and clamp to a valid range, so a malformed
value degrades gracefully instead of crashing the effect loop.
"""

from __future__ import annotations

from typing import Iterable


def as_float(
    params: dict,
    key: str,
    default: float,
    lo: float | None = None,
    hi: float | None = None,
) -> float:
    try:
        value = float(params.get(key, default))
    except (TypeError, ValueError):
        return default
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def as_int(
    params: dict,
    key: str,
    default: int,
    lo: int | None = None,
    hi: int | None = None,
) -> int:
    return int(as_float(params, key, default, lo, hi))


def as_str(params: dict, key: str, default: str = "", max_len: int = 64) -> str:
    value = params.get(key, default)
    if not isinstance(value, str):
        return default
    return value.strip()[:max_len]


def as_choice(params: dict, key: str, default: str, allowed: Iterable[str]) -> str:
    value = as_str(params, key, default)
    return value if value in set(allowed) else default
