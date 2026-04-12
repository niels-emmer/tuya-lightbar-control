# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`tuya-lightbar-control` is a frontend-driven controller and REST API for the Battletron Gaming Light Bar (Tuya v3.5, LAN). Unlike the sibling `../lightbar` project which uses an AI engine to generate programs, this project exposes a low-latency, segment-level API and demo frontend — enabling scripted control, data-driven modes (crypto candles, traffic jams, weather), and external integrations.

The device, credentials, and Tuya protocol knowledge are shared with `../lightbar`. See `../lightbar/docs/device-protocol.md` for DP register details.

## Dev setup

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp ../.env.example ../.env   # fill in DEVICE_ID, DEVICE_IP, DEVICE_KEY
uvicorn main:app --reload --port 8000
```

```bash
# Frontend (once it exists)
cd frontend
npm install
npm run dev   # http://localhost:5173 — proxies /api/* to :8000
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | Device online state, power, mode, whole-bar HSV |
| `POST` | `/api/power` | `{ on: bool }` |
| `POST` | `/api/color` | `{ h, s, v }` — set whole bar at once (DP 24) |
| `POST` | `/api/segment/{n}` | `{ h, s, v }` — set segment n (1–20) via DP 61 |
| `POST` | `/api/segment/{n}/off` | Turn segment n off |
| `POST` | `/api/segments` | `{ colors: [{h,s,v}\|null, ...] }` — batch all 20 via `set_all_segments` |
| `POST` | `/api/scene` | `{ type, speed, colors }` — hardware scene via DP 51 |

Interactive docs at `http://localhost:8000/docs`.

## Architecture

```
Frontend (React + Mantine)
  → /api/*
  ↓
FastAPI backend  (backend/main.py)
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
| `backend/lightbar.py` | Tuya device driver (copied from `../lightbar`) |
| `backend/config.py` | Pydantic Settings — loads `.env` |
| `backend/models.py` | Pydantic request/response models |
| `frontend/src/` | (future) React app |

## Python version note

The system Python is 3.9. Use `Optional[X]` from `typing` instead of `X | None` union syntax in type annotations — Pydantic evaluates annotations at runtime and the `|` union operator for types requires Python 3.10+. All files already include `from __future__ import annotations`.

## Device protocol quick reference

- DP 20: power (bool)
- DP 21: mode — `"colour"` required before DP 24 or DP 61 writes
- DP 24: whole-bar HSV — 12-char hex `HHHHSSSSVVVV` (hue raw 0–360, sat/val ×10)
- DP 51: hardware scene (base64 payload)
- DP 61: per-segment colour (13-byte base64 payload, segment index 1–20)

Hue encoding: raw degrees 0–360 as 4-digit hex (e.g. blue hue=231 → `00e7`), **not** scaled. Saturation and value are multiplied by 10 (range 0–1000).
