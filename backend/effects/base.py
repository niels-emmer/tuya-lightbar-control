from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ParamSchema:
    key: str
    label: str
    type: str  # "text" | "number" | "select" | "slider"
    default: Any = None
    placeholder: str = ""
    options: list[dict] = field(default_factory=list)  # [{value, label}] for select
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    unit: str = ""

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "default": self.default,
            "placeholder": self.placeholder,
        }
        if self.options:
            d["options"] = self.options
        if self.min is not None:
            d["min"] = self.min
        if self.max is not None:
            d["max"] = self.max
        if self.step is not None:
            d["step"] = self.step
        if self.unit:
            d["unit"] = self.unit
        return d


class BaseEffect(ABC):
    name: str
    label: str
    description: str = ""
    params_schema: list[ParamSchema] = []

    @abstractmethod
    async def run(self, driver: Any, brightness: int, params: dict) -> None: ...

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "params": [p.to_dict() for p in self.params_schema],
        }
