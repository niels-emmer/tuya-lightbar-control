# CLAUDE.md

Guidance for Claude Code / OpenCode agents working in this repository. See also `AGENTS.md` (the repo playbook) and `docs/ARCHITECTURE.md`.

## Project

`tuya-lightbar-control` is a frontend-driven controller and REST API for the Battletron Gaming Light Bar (Tuya v3.5, LAN). Unlike the sibling `../lightbar` project (which uses an AI engine to generate programs), this project exposes a low-latency, segment-level API and demo frontend — enabling scripted control, data-driven modes (crypto candles, traffic, weather, air quality, home power), and external integrations.

The device, credentials, and Tuya protocol knowledge are shared with `../lightbar`.

## Dev setup

```bash
# Backend (Python 3.13)
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

cp ../.env.example ../.env   # fill in DEVICE_ID, DEVICE_IP, DEVICE_KEY
uvicorn main:app --reload --port 8042
```

```bash
# Frontend
cd frontend
npm install
npm run dev   # http://localhost:5173 — proxies /api/* to :8042
```

The dev proxy targets port **8042**, so run the backend on 8042.

## API

Device routes:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | Device online state, power, mode, whole-bar HSV |
| `POST` | `/api/power` | `{ on: bool }` |
| `POST` | `/api/color` | `{ h, s, v }` — set whole bar at once (DP 24) |
| `POST` | `/api/segment/{n}` | `{ h, s, v }` — set segment n (1–20) via DP 61 |
| `POST` | `/api/segment/{n}/off` | Turn segment n off |
| `POST` | `/api/segments` | `{ colors: [{h,s,v}\|null, ...] }` — batch all 20 |
| `POST` | `/api/scene` | `{ type, speed, colors }` — hardware scene via DP 51 |

Effects and settings routes:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/effects` | List registered effects + their parameter schemas |
| `GET` | `/api/effect` | Currently active effect (or null) |
| `POST` | `/api/effect` | `{ name, params }` — activate an effect |
| `DELETE` | `/api/effect` | Stop the active effect |
| `GET` | `/api/settings` | Persisted UI settings |
| `PUT` | `/api/settings` | Update persisted UI settings |

Plus `GET /healthz` (unauthenticated liveness). Interactive docs at `http://<host>:8042/docs`.

When `API_KEY` is set, every `/api/*` route and the docs routes require `X-API-Key: <key>` or `Authorization: Bearer <key>`.

## Architecture

```
Frontend (React 19 + Mantine 9)
  → /api/*
  ↓
FastAPI backend  (backend/main.py, auth.py)
  ↓
LightbarDriver   (backend/lightbar.py) — thread-safe tinytuya wrapper
  ↓
Battletron @ 192.168.101.130:6668  (Tuya v3.5 LAN)
```

**Key constraint:** minimum ~200 ms between individual segment writes. `set_all_segments` uses `segment_delay=0.25` s, so a full 20-segment sweep takes ~5 s. The frontend must not attempt sub-second pattern refresh on segment mode.

**Whole-bar vs segment mode:**
- `POST /api/color` uses DP 24 — instant, good for animations
- `POST /api/segments` uses DP 61 — slow sweep, good for static data visualisations

## Key files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app, all route handlers |
| `backend/auth.py` | API-key middleware |
| `backend/lightbar.py` | Tuya device driver (tinytuya wrapper) |
| `backend/config.py` | Pydantic Settings — loads `.env` |
| `backend/models.py` | Pydantic request/response models |
| `backend/settings_store.py` | Persistent `settings.json` |
| `backend/effects/` | One file per effect + `registry.py`, `base.py`, `_params.py` |
| `frontend/src/` | React app |

## Python version note

The runtime is **Python 3.13** (local venv, container, CI). `from __future__ import annotations` is kept in every module; `Optional[X]` / `List[X]` style is used for consistency with the existing code, though `X | None` is now available.

## Device protocol quick reference

- DP 20: power (bool)
- DP 21: mode — `"colour"` required before DP 24 or DP 61 writes
- DP 24: whole-bar HSV — 12-char hex `HHHHSSSSVVVV` (hue raw 0–360, sat/val ×10)
- DP 51: hardware scene (base64 payload)
- DP 61: per-segment colour (13-byte base64 payload, segment index 1–20)

Hue encoding: raw degrees 0–360 as 4-digit hex (e.g. blue hue=231 → `00e7`), **not** scaled. Saturation and value are multiplied by 10 (range 0–1000).
