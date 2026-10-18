from __future__ import annotations

from typing import Optional

from .air_quality import AirQualityEffect
from .base import BaseEffect
from .claude_usage import ClaudeUsageEffect
from .countdown import CountdownEffect
from .crypto import CryptoEffect
from .home_power import HomePowerEffect
from .network_traffic import NetworkTrafficEffect
from .patterns import RandomEffect
from .polestar import PolestarEffect
from .rain import RainEffect
from .trumps_truths import TrumpsTruthsEffect

_EFFECTS: list[BaseEffect] = [
    CryptoEffect(),
    RainEffect(),
    CountdownEffect(),
    RandomEffect(),
    TrumpsTruthsEffect(),
    NetworkTrafficEffect(),
    ClaudeUsageEffect(),
    AirQualityEffect(),
    HomePowerEffect(),
    PolestarEffect(),
]

_BY_NAME: dict[str, BaseEffect] = {e.name: e for e in _EFFECTS}


def list_effects() -> list[dict]:
    return [e.to_dict() for e in _EFFECTS]


def get_effect(name: str) -> Optional[BaseEffect]:
    return _BY_NAME.get(name)
