from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HSV(BaseModel):
    h: float = Field(..., ge=0, le=360, description="Hue 0–360")
    s: float = Field(..., ge=0, le=100, description="Saturation 0–100")
    v: float = Field(..., ge=0, le=100, description="Value/brightness 0–100")


class PowerRequest(BaseModel):
    on: bool


class ColorRequest(HSV):
    pass


class SegmentsRequest(BaseModel):
    colors: List[Optional[HSV]] = Field(
        ...,
        max_length=20,
        description="Up to 20 HSV entries (index 0 = segment 1). None turns a segment off.",
    )


class SceneRequest(BaseModel):
    type: int = Field(..., ge=0, le=3, description="0=static, 1=flow, 2=flash, 3=wave")
    speed: int = Field(..., ge=0, le=100)
    colors: List[List[int]] = Field(
        ...,
        min_length=1,
        max_length=7,
        description="List of [r, g, b] entries (0–255 each)",
    )


class DeviceStatus(BaseModel):
    online: bool
    power: Optional[bool] = None
    mode: Optional[str] = None
    color: Optional[HSV] = None


# ── Settings ────────────────────────────────────────────────────────────────

class AppSettings(BaseModel):
    brightness: int = Field(80, ge=0, le=100)
    auto_on: Optional[str] = Field(None, description="HH:MM or null")
    auto_off: Optional[str] = Field(None, description="HH:MM or null")
    weather_lat: float = 52.92
    weather_lon: float = 6.43


# ── Effects ─────────────────────────────────────────────────────────────────

class EffectActivateRequest(BaseModel):
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)


class EffectState(BaseModel):
    name: str
    params: Dict[str, Any]
