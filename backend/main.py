from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import settings_store
from config import get_settings
from effect_runner import EffectRunner
from effects.registry import list_effects
from lightbar import LightbarDriver, tuya_to_hsv
from models import (
    AppSettings,
    ColorRequest,
    DeviceStatus,
    EffectActivateRequest,
    EffectState,
    HSV,
    PowerRequest,
    SceneRequest,
    SegmentsRequest,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_driver: Optional[LightbarDriver] = None
_runner = EffectRunner()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _driver
    cfg = get_settings()

    # Seed settings.json from .env on first run
    stored = settings_store.load()
    if stored.get("weather_lat") == 52.92 and cfg.weather_lat != 52.92:
        settings_store.save({"weather_lat": cfg.weather_lat, "weather_lon": cfg.weather_lon})

    if cfg.device_id and cfg.device_ip and cfg.device_key:
        _driver = LightbarDriver(
            device_id=cfg.device_id,
            ip=cfg.device_ip,
            local_key=cfg.device_key,
            version=cfg.device_version,
        )
        logger.info(f"LightbarDriver initialized for {cfg.device_ip}")
    else:
        logger.warning("Device credentials missing — running without device")

    # Auto on/off background task
    task = asyncio.create_task(_auto_onoff_loop())
    yield
    task.cancel()
    await _runner.stop()


async def _auto_onoff_loop():
    while True:
        try:
            s = settings_store.load()
            now = datetime.now().strftime("%H:%M")
            if _driver:
                if s.get("auto_on") == now:
                    _driver.set_power(True)
                if s.get("auto_off") == now:
                    await _runner.stop()
                    _driver.set_power(False)
        except Exception as e:
            logger.warning(f"auto_onoff_loop error: {e}")
        await asyncio.sleep(30)


app = FastAPI(
    title="Lightbar Monitor",
    description=(
        "REST API for controlling the Battletron RGB lightbar (Tuya v3.5 LAN). "
        "Low-level device routes are stable and safe to call from Home Assistant or any external app. "
        "Effect routes run an async loop that continuously pushes patterns to the device; "
        "only one effect can be active at a time."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


def _require_driver() -> LightbarDriver:
    if _driver is None:
        raise HTTPException(status_code=503, detail="Device not configured")
    return _driver


# ---------------------------------------------------------------------------
# Device — low-level routes (also usable by external apps / Home Assistant)
# ---------------------------------------------------------------------------

@app.get(
    "/api/status",
    response_model=DeviceStatus,
    tags=["Device"],
    summary="Get device status",
    description="Returns whether the lightbar is reachable, its power state, current mode, and whole-bar HSV color.",
)
def get_status():
    if _driver is None:
        return DeviceStatus(online=False)
    dps = _driver.get_status()
    if dps is None:
        return DeviceStatus(online=False)
    color: Optional[HSV] = None
    raw = dps.get(24)
    if isinstance(raw, str) and len(raw) == 12:
        h, s, v = tuya_to_hsv(raw)
        color = HSV(h=h, s=s, v=v)
    return DeviceStatus(
        online=True,
        power=dps.get(20),
        mode=dps.get(21),
        color=color,
    )


@app.post(
    "/api/power",
    tags=["Device"],
    summary="Turn the lightbar on or off",
)
def set_power(req: PowerRequest):
    d = _require_driver()
    if not d.set_power(req.on):
        raise HTTPException(status_code=502, detail="Device write failed")
    return {"ok": True}


@app.post(
    "/api/color",
    tags=["Device"],
    summary="Set whole-bar color",
    description="Sets all 20 segments to the same HSV color instantly via DP 24. Stops any running effect.",
)
def set_color(req: ColorRequest):
    d = _require_driver()
    if not d.set_color(req.h, req.s, req.v):
        raise HTTPException(status_code=502, detail="Device write failed")
    return {"ok": True}


@app.post(
    "/api/segment/{n}",
    tags=["Device"],
    summary="Set a single segment",
    description=(
        "Sets one LED segment (1–20, left to right) to an HSV color via DP 61. "
        "Minimum ~200 ms between calls; device drops commands sent faster."
    ),
)
def set_segment(n: int, req: ColorRequest):
    if not 1 <= n <= 20:
        raise HTTPException(status_code=422, detail="Segment must be 1–20")
    d = _require_driver()
    if not d.set_segment(n, req.h, req.s, req.v):
        raise HTTPException(status_code=502, detail="Device write failed")
    return {"ok": True}


@app.post(
    "/api/segment/{n}/off",
    tags=["Device"],
    summary="Turn off a single segment",
)
def set_segment_off(n: int):
    if not 1 <= n <= 20:
        raise HTTPException(status_code=422, detail="Segment must be 1–20")
    d = _require_driver()
    if not d.set_segment_off(n):
        raise HTTPException(status_code=502, detail="Device write failed")
    return {"ok": True}


@app.post(
    "/api/segments",
    tags=["Device"],
    summary="Set all segments in one sweep",
    description=(
        "Writes up to 20 HSV values (index 0 = segment 1) in a single persistent connection. "
        "Pass `null` for a segment to turn it off. A full 20-segment sweep takes ~5 s at 0.25 s/segment. "
        "This is the primary route for data-driven patterns."
    ),
)
def set_segments(req: SegmentsRequest):
    d = _require_driver()
    colors = [(c.h, c.s, c.v) if c is not None else None for c in req.colors]
    if not d.set_all_segments(colors):
        raise HTTPException(status_code=502, detail="One or more segment writes failed")
    return {"ok": True}


@app.post(
    "/api/scene",
    tags=["Device"],
    summary="Trigger a hardware scene",
    description=(
        "Sends a native Tuya hardware animation via DP 51. "
        "type: 0=static, 1=flow, 2=flash, 3=wave. "
        "Colors are RGB (0–255). Up to 7 colors."
    ),
)
def set_scene(req: SceneRequest):
    d = _require_driver()
    if not d.set_scene(req.type, req.speed, [tuple(c) for c in req.colors]):
        raise HTTPException(status_code=502, detail="Device write failed")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Effects
# ---------------------------------------------------------------------------

@app.get(
    "/api/effects",
    tags=["Effects"],
    summary="List available effects",
    description=(
        "Returns all registered effects with their name, label, description, and parameter schemas. "
        "Use the `name` field with `POST /api/effect` to activate an effect."
    ),
)
def get_effects():
    return list_effects()


@app.get(
    "/api/effect",
    response_model=Optional[EffectState],
    tags=["Effects"],
    summary="Get active effect",
    description="Returns the currently running effect and its parameters, or null if none is active.",
)
def get_current_effect():
    c = _runner.current
    if c is None:
        return None
    return EffectState(name=c["name"], params=c["params"])


@app.post(
    "/api/effect",
    tags=["Effects"],
    summary="Activate an effect",
    description=(
        "Starts a named effect with the given parameters. "
        "Any previously running effect is stopped first. "
        "Brightness is taken from saved settings. "
        "Available effect names: `crypto`, `rain`, `countdown`, `random`. "
        "Example: `{\"name\": \"crypto\", \"params\": {\"coin\": \"BTCUSDT\"}}`"
    ),
)
async def activate_effect(req: EffectActivateRequest):
    d = _require_driver()
    s = settings_store.load()
    try:
        await _runner.activate(d, req.name, req.params, s.get("brightness", 80))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "name": req.name}


@app.delete(
    "/api/effect",
    tags=["Effects"],
    summary="Stop active effect",
    description="Cancels the running effect loop. The lightbar keeps its last color.",
)
async def stop_effect():
    await _runner.stop()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.get(
    "/api/settings",
    response_model=AppSettings,
    tags=["Settings"],
    summary="Get app settings",
)
def get_settings_route():
    return AppSettings(**settings_store.load())


@app.put(
    "/api/settings",
    response_model=AppSettings,
    tags=["Settings"],
    summary="Update app settings",
    description=(
        "Persists settings to settings.json. "
        "`brightness` (0–100) is applied to all effects on next activation. "
        "`auto_on` / `auto_off` are `HH:MM` strings (24h) or null to disable. "
        "`weather_lat` / `weather_lon` are used by the rain effect."
    ),
)
def update_settings(req: AppSettings):
    saved = settings_store.save(req.model_dump(exclude_none=False))
    return AppSettings(**saved)


# ---------------------------------------------------------------------------
# Serve frontend (production build)
# ---------------------------------------------------------------------------

_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        file = _DIST / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def index():
        return {"message": "Build the frontend first: cd frontend && npm run build"}
