# tuya-lightbar-control

A low-latency REST API and interactive frontend for precise, segment-level control of the **Battletron Gaming Light Bar** (Tuya v3.5, LAN protocol). Enables scripted patterns, data-driven visualizations (crypto candlesticks, weather, rain probability), and external integrations — beyond what the proprietary mobile app offers.

## Overview

`tuya-lightbar-control` is built for developers and enthusiasts who want fine-grained control over a Tuya-based RGB lightbar on their local network. It communicates directly with the device over LAN (no cloud required), offering:

- **~200 ms round-trip latency** per segment write
- **Whole-bar animations** via DP 24 (instant HSV writes)
- **Per-segment control** for static data visualizations
- **Hardware scenes** via the device's built-in scene engine
- **REST API** for external automation and integrations
- **Interactive frontend** (React + Mantine) for manual control and effect management

> **Note:** This project was built agentically — developed through prompted iteration with an AI coding assistant rather than written by hand. It is intended for **local (LAN) use only** and should not be exposed to the public internet. There is no authentication layer.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.9+ · FastAPI · uvicorn · tinytuya |
| **Frontend** | React 18 · TypeScript · Vite · Mantine UI |
| **Device Protocol** | Tuya v3.5 LAN |
| **Deployment** | Docker · Docker Compose |

## How It Works

### Architecture

```
┌─────────────────────────────────────┐
│  Frontend (React + Mantine)         │
│  http://<host>:5173                 │
└──────────────┬──────────────────────┘
               │ /api/* (proxied)
               ↓
┌─────────────────────────────────────┐
│  FastAPI Backend                    │
│  http://<host>:8000                 │
│  • main.py (routes)                 │
│  • lightbar.py (tinytuya wrapper)   │
│  • effect_runner.py (async effects) │
└──────────────┬──────────────────────┘
               │ Tuya v3.5 LAN · port 6668
               ↓
┌─────────────────────────────────────┐
│  Battletron Lightbar                │
│  192.168.x.x:6668                   │
│  20 addressable segments            │
└─────────────────────────────────────┘
```

### Device Protocol (Quick Ref)

| DP | Purpose | Payload |
|----|---------|---------|
| 20 | Power | `bool` |
| 21 | Mode | `"colour"` (required before color writes) |
| 24 | Whole-bar HSV | `HHHHSSSSVVVV` (12-char hex) |
| 51 | Hardware scene | Base64-encoded payload |
| 61 | Per-segment color | 13-byte base64 (segment 1–20) |

**Hue encoding:** Raw degrees 0–360 as 4-digit hex (e.g. `00e7` = blue/231°).  
**Sat/Val encoding:** Multiplied by 10 (range 0–1000).

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | Device online state, power, mode, whole-bar HSV |
| `POST` | `/api/power` | `{ "on": bool }` |
| `POST` | `/api/color` | `{ "h", "s", "v" }` — whole bar via DP 24 (instant) |
| `POST` | `/api/segment/{n}` | `{ "h", "s", "v" }` — single segment (1–20) via DP 61 |
| `POST` | `/api/segment/{n}/off` | Turn segment n off |
| `POST` | `/api/segments` | `{ "colors": [{h,s,v} or null, ...] }` — batch all 20 |
| `POST` | `/api/scene` | `{ "type", "speed", "colors" }` — hardware scene via DP 51 |
| `GET` | `/api/effects` | List available effects |
| `GET` | `/api/effect` | Currently active effect |
| `POST` | `/api/effect` | `{ "name", "params" }` — activate an effect |
| `DELETE` | `/api/effect` | Stop current effect |

Interactive docs at `/docs` after startup.

## Prerequisites

### Software

- **Python 3.9+**
- **Node.js 18+**

### Hardware

A Battletron Gaming Light Bar (or compatible Tuya v3.5 RGB device) connected to the same LAN as the machine running this software.

### Device Credentials

You need three values from your device: **Device ID**, **local key**, and **IP address**. These are not available from the Tuya app directly — you need to extract them.

#### Step 1 — Get Device ID and local key via tinytuya wizard

Install tinytuya in a temporary environment:

```bash
pip install tinytuya
python -m tinytuya wizard
```

The wizard will ask for your Tuya IoT Platform credentials. If you don't have an account:

1. Register at [iot.tuya.com](https://iot.tuya.com)
2. Create a Cloud project (free tier is sufficient)
3. Link your Tuya/Smart Life app account to the project
4. In the wizard, enter your **Access ID** and **Access Secret** from the project's API keys page

The wizard will scan your account and output a `devices.json` file. Find your lightbar and note:
- `id` → `DEVICE_ID`
- `key` → `DEVICE_KEY`

> The local key rotates if you reset the device or re-pair it in the app. Re-run the wizard if the connection stops working.

#### Step 2 — Find the device IP

Check your router's DHCP client list (usually under LAN settings), or scan your network:

```bash
pip install tinytuya
python -m tinytuya scan
```

This broadcasts a discovery packet and lists responding Tuya devices with their IP addresses. Note the IP for your lightbar.

> Assign a static DHCP reservation for the device in your router so the IP doesn't change between reboots.

#### Step 3 — Confirm connectivity

```bash
python -m tinytuya device <DEVICE_ID> <DEVICE_IP> <DEVICE_KEY> 3.5
```

You should see a status response with `dps` keys including `20` (power) and `21` (mode).

## Installation

### Option 1: Local Dev

#### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example ../.env   # then fill in credentials
uvicorn main:app --reload --port 8000
```

`.env` values:

```
DEVICE_ID=your_device_id
DEVICE_IP=192.168.x.x
DEVICE_KEY=your_local_key
DEVICE_VERSION=3.5
```

#### Frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173 — proxies /api/* to :8000
```

### Option 2: Docker Compose

```bash
cp .env.example .env
nano .env                    # fill in device credentials
docker-compose up --build
```

Frontend at `:5173`, backend at `:8000`.

## Performance Notes

| Operation | Latency |
|-----------|---------|
| Whole-bar write (DP 24) | ~10 ms |
| Single segment write (DP 61) | ~200 ms |
| Full 20-segment sweep | ~5 s |

- Use `POST /api/color` (DP 24) for animations — it's instant.
- Use `POST /api/segments` (DP 61) for static data displays. Do not attempt sub-second refresh in segment mode.

## Project Structure

```
.
├── .env                         # Device credentials (not in git)
├── .env.example
├── docker-compose.yml
├── settings.json                # Persisted UI settings
├── backend/
│   ├── main.py                  # FastAPI app & route handlers
│   ├── lightbar.py              # Tuya device driver (tinytuya wrapper)
│   ├── effect_runner.py         # Async effect lifecycle
│   ├── config.py                # Pydantic settings (reads .env)
│   ├── models.py                # Request/response schemas
│   ├── settings_store.py        # Persistent UI settings
│   ├── requirements.txt
│   └── effects/
│       ├── base.py              # BaseEffect ABC + ParamSchema
│       ├── registry.py          # Effect registration
│       ├── crypto.py            # Live crypto candlestick (Binance WS)
│       ├── rain.py              # Rain probability (Open-Meteo)
│       ├── countdown.py         # Countdown timer
│       └── patterns.py          # Random/static patterns
└── frontend/
    └── src/
        ├── App.tsx              # Root component, polling loop
        ├── api.ts               # Typed fetch client
        ├── theme.ts             # Mantine theme
        └── components/
            ├── TopBar.tsx
            ├── StatusCard.tsx
            ├── EffectCard.tsx
            ├── SettingsDrawer.tsx
            └── ParamField.tsx
```

## Troubleshooting

**Device not reachable**
- Confirm the device and server are on the same LAN subnet
- Check that port 6668 is not firewalled
- If running in Docker, ensure `network_mode: host` or correct bridge networking

**"Invalid credentials" / connection refused**
- The local key may have rotated — re-run `python -m tinytuya wizard` and update `DEVICE_KEY`
- Confirm `DEVICE_VERSION=3.5`

**Status shows standby while device is on**
- DP 20 (power) may be `false` even when the bar is displaying color. Activating any effect via the frontend will send a power-on command first.

## License

MIT
