from __future__ import annotations

from typing import Optional

from .base import BaseEffect
from .crypto import CryptoEffect
from .rain import RainEffect
from .countdown import CountdownEffect
from .patterns import RandomEffect
from .trumps_truths import TrumpsTruthsEffect

_EFFECTS: list[BaseEffect] = [
    CryptoEffect(),
    RainEffect(),
    CountdownEffect(),
    RandomEffect(),
    TrumpsTruthsEffect(),
]

_BY_NAME: dict[str, BaseEffect] = {e.name: e for e in _EFFECTS}


def list_effects() -> list[dict]:
    return [e.to_dict() for e in _EFFECTS]


def get_effect(name: str) -> Optional[BaseEffect]:
    return _BY_NAME.get(name)
