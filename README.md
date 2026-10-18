# tuya-lightbar-control

A low-latency REST API and interactive frontend for precise, segment-level control of the **Battletron Gaming Light Bar** (Tuya v3.5, LAN protocol). Enables scripted patterns, data-driven visualizations (crypto candlesticks, weather, rain probability, network traffic, air quality, home power), and external integrations — beyond what the proprietary mobile app offers.

## Overview

`tuya-lightbar-control` is built for developers and enthusiasts who want fine-grained control over a Tuya-based RGB lightbar on their local network. It communicates directly with the device over LAN (no cloud required), offering:

- **~200 ms round-trip latency** per segment write
- **Whole-bar animations** via DP 24 (instant HSV writes)
- **Per-segment control** for static data visualizations
- **Hardware scenes** via the device's built-in scene engine
- **REST API** for external automation and integrations
- **Interactive frontend** (React + Mantine) for manual control and effect management
- **Optional API-key authentication** for the API and docs

> **Note:** This project was built agentically — developed through prompted iteration with an AI coding assistant rather than written by hand. It is intended for **local (LAN) use only** and should not be exposed to the public internet.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.13 · FastAPI · uvicorn · tinytuya · paho-mqtt |
| **Frontend** | React 19 · TypeScript 7 · Vite 8 · Mantine 9 |
| **Device Protocol** | Tuya v3.5 LAN |
| **Deployment** | Docker · Docker Compose |

## Authentication

The API can be locked with a shared secret. Set `API_KEY` in `.env`; clients must then send it on every `/api/*` request (and to the docs routes) as either:

- `X-API-Key: <key>`, or
- `Authorization: Bearer <key>`

`GET /healthz` is always unauthenticated (used by the container healthcheck). **If `API_KEY` is empty, authentication is disabled** and the app logs a prominent warning at startup — fine for a trusted LAN, not for anything exposed.

The bundled frontend supports the key: it prompts for it when the API returns `401` and stores it in the browser's `localStorage` (never baked into the public JS bundle). See `SECURITY.md`.

## How It Works

### Architecture

```
┌─────────────────────────────────────┐
│  Frontend (React + Mantine)         │
│  dev: http://localhost:5173         │
│  prod: http://<host>:8042           │
└──────────────┬──────────────────────┘
               │ /api/* (proxied in dev)
               ↓
┌─────────────────────────────────────┐
│  FastAPI Backend                    │
│  http://<host>:8042 (container)     │
│  • main.py (routes)                 │
│  • auth.py (API-key middleware)     │
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

In the container image the built frontend is served by FastAPI itself, so **frontend and API share a single port** (host `8042` → container `8000`).

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

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/healthz` | no | Liveness probe (`{"ok": true}`) |
| `GET` | `/api/status` | yes | Device online state, power, mode, whole-bar HSV |
| `POST` | `/api/power` | yes | `{ "on": bool }` |
| `POST` | `/api/color` | yes | `{ "h", "s", "v" }` — whole bar via DP 24 (instant) |
| `POST` | `/api/segment/{n}` | yes | `{ "h", "s", "v" }` — single segment (1–20) via DP 61 |
| `POST` | `/api/segment/{n}/off` | yes | Turn segment n off |
| `POST` | `/api/segments` | yes | `{ "colors": [{h,s,v} or null, ...] }` — batch all 20 |
| `POST` | `/api/scene` | yes | `{ "type", "speed", "colors" }` — hardware scene via DP 51 |
| `GET` | `/api/effects` | yes | List available effects |
| `GET` | `/api/effect` | yes | Currently active effect |
| `POST` | `/api/effect` | yes | `{ "name", "params" }` — activate an effect |
| `DELETE` | `/api/effect` | yes | Stop current effect |
| `GET` | `/api/settings` | yes | Persisted UI settings |
| `PUT` | `/api/settings` | yes | Update persisted UI settings |

Interactive docs at `/docs` after startup (subject to auth when `API_KEY` is set).

## Prerequisites

### Software

- **Python 3.13**
- **Node.js 22** (frontend build / dev only)

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
python3.13 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

cp ../.env.example ../.env   # then fill in credentials
uvicorn main:app --reload --port 8042
```

Key `.env` values:

```
DEVICE_ID=your_device_id
DEVICE_IP=192.168.x.x
DEVICE_KEY=your_local_key
DEVICE_VERSION=3.5
API_KEY=                     # optional; set to require auth
```

#### Frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173 — proxies /api/* to :8042
```

The dev server proxies `/api` to `http://localhost:8042`, so run the backend on port **8042**.

### Option 2: Docker Compose

```bash
cp .env.example .env
cp settings.json.example settings.json   # runtime settings file (bind-mounted)
nano .env                                # fill in device credentials (+ API_KEY)
docker compose up -d --build
```

The app is then served on **`http://<host>:8042`** (frontend and API on one port).

## Built-in Effects

Effects are activated via `POST /api/effect` or from the frontend. Only one runs at a time.

| Effect | Name | Description |
|--------|------|-------------|
| **Crypto Candlestick** | `crypto` | Live 5-minute candlestick from Binance WebSocket. Green segments extend right (price up), red left (price down). Params: `coin` (e.g. `BTCUSDT`), `max_pct`. |
| **Rain Probability** | `rain` | Blue bar showing precipitation probability from Open-Meteo. Empty = 0 %, full = 100 %. Refreshes every 5 min. Params: `window` (15/30/45/60 min). |
| **Countdown Timer** | `countdown` | Amber bar depleting right-to-left. Flashes red three times on expiry. Params: `minutes`. |
| **Patterns** | `random` | Animated patterns: Rainbow, Color Blobs, Running Dots, or Pulse. Params: `style`, `speed`, `colors`, `hue`. |
| **Trump's Truths** | `trumps_truths` | Live count of @realDonaldTrump posts on Truth Social in the past N hours. Green→red gradient. Refreshes every 5 min. Params: `hours`, `max_truths`. |
| **Network Traffic** | `network_traffic` | Host RX/TX bandwidth on a split vertical bar. Bottom 9 segments = incoming (blue), top 9 = outgoing (green), center pulses white. Reads `/proc/net/dev`. Params: `interface`, `max_mbps`. |
| **Claude Token Budget** | `claude_usage` | Remaining Claude Pro budget from the local nanoclaw-cyd-monitor daemon (`CLAUDE_USAGE_URL`). Full bar = budget untouched; empties as you use it. Params: `mode` (`session` / `weekly` / `alternate`). |
| **Air Quality** | `air_quality` | Severity bar for local air quality from Open-Meteo (your saved weather location). Fill grows with pollution; colour ramps green → yellow → orange → red. Tip pulses to show it is live. Refreshes every 10 min. Params: `metric` (`aqi` / `pm2_5`). |
| **Home Power** | `home_power` | Live whole-home power draw (W) from a DSMR P1 smart-meter reader over MQTT (`sensors/power/p1meter/actual_consumption`). Bar fills with load, ramps green → red; near-real-time. Params: `max_w`. Config: `MQTT_HOST` / `MQTT_PORT` / `MQTT_TOPIC`. |
| **Polestar** | `polestar` | Charging state of a Polestar EV, read directly via `pypolestar`. Bar fills with state-of-charge (green ≥ 60 %, amber ≥ 25 %, red below). Actively charging → green bar with a blinking tip; plugged in but idle → static SOC bar; unplugged → dimmed. Config: `POLESTAR_USERNAME` / `POLESTAR_PASSWORD` (optional `POLESTAR_VIN`, `POLESTAR_POLL_INTERVAL`). |

> **Docker note:** The network_traffic effect requires a `/proc/net` volume mount (included in `docker-compose.yml`) to read host-level interface stats rather than the container's virtual eth0.

## Performance Notes

| Operation | Latency |
|-----------|---------|
| Whole-bar write (DP 24) | ~10 ms |
| Single segment write (DP 61) | ~200 ms |
| Full 20-segment sweep | ~5 s |

- Use `POST /api/color` (DP 24) for animations — it's instant.
- Use `POST /api/segments` (DP 61) for static data displays. Do not attempt sub-second refresh in segment mode.

## Configuration

### Environment (`.env`)

| Variable | Purpose |
|----------|---------|
| `DEVICE_ID` / `DEVICE_IP` / `DEVICE_KEY` | Tuya device credentials |
| `DEVICE_VERSION` | Tuya protocol version (default `3.5`) |
| `WEATHER_LAT` / `WEATHER_LON` | First-run seed for `settings.json` (rain + air_quality) |
| `MQTT_HOST` / `MQTT_PORT` / `MQTT_TOPIC` | DSMR P1 meter broker for `home_power` |
| `CLAUDE_USAGE_URL` | nanoclaw-cyd-monitor daemon for `claude_usage` |
| `POLESTAR_USERNAME` / `POLESTAR_PASSWORD` | Polestar account for `polestar` (empty disables it) |
| `POLESTAR_VIN` / `POLESTAR_POLL_INTERVAL` | Optional vehicle VIN and poll interval (seconds) for `polestar` |
| `API_KEY` | Shared secret; empty disables auth |

### Runtime (`settings.json`)

`settings.json` holds UI-editable runtime state (`brightness`, `auto_on`, `auto_off`, `weather_lat`, `weather_lon`). It is **not tracked in git** — it is runtime state, bind-mounted into the container. Copy `settings.json.example` to `settings.json` on first deploy. Defaults live on the `AppSettings` model.

## Deployment

The live instance runs on host `office-pc` (see `docs/DEPLOYMENT.md` for the full procedure):

```bash
cd /home/niels/tuya-lightbar-control
git pull
docker compose up -d --build
curl -fsS http://127.0.0.1:8042/healthz   # -> {"ok": true}
```

## Project Structure

```
.
├── .env                         # Secrets (not in git)
├── .env.example
├── docker-compose.yml
├── settings.json                # Runtime UI settings (not in git)
├── settings.json.example
├── pyproject.toml               # pytest + ruff config
├── .github/workflows/ci.yml     # backend (ruff+pytest) + frontend (build+audit)
├── docs/                        # ARCHITECTURE, DEPLOYMENT, decision-log
├── backend/
│   ├── main.py                  # FastAPI app & route handlers
│   ├── auth.py                  # API-key middleware
│   ├── lightbar.py              # Tuya device driver (tinytuya wrapper)
│   ├── effect_runner.py         # Async effect lifecycle
│   ├── config.py                # Pydantic settings (reads .env)
│   ├── models.py                # Request/response schemas
│   ├── settings_store.py        # Persistent UI settings (atomic writes)
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── tests/                   # pytest suite
│   └── effects/
│       ├── base.py              # BaseEffect ABC + ParamSchema
│       ├── registry.py          # Effect registration
│       ├── _params.py           # Safe param coercion helpers
│       ├── crypto.py            # Live crypto candlestick (Binance WS)
│       ├── rain.py              # Rain probability (Open-Meteo)
│       ├── countdown.py         # Countdown timer
│       ├── patterns.py          # Animated patterns
│       ├── trumps_truths.py     # Truth Social post counter
│       ├── network_traffic.py   # Host RX/TX bandwidth
│       ├── claude_usage.py      # Claude Pro budget
│       ├── air_quality.py       # Air quality (Open-Meteo)
│       ├── home_power.py        # Home power (MQTT / P1 meter)
│       └── polestar.py          # Polestar EV charging state (pypolestar)
└── frontend/
    └── src/
        ├── App.tsx              # Root component, polling loop
        ├── api.ts               # Typed fetch client (+ API-key header)
        ├── auth.ts              # API-key storage (localStorage)
        ├── theme.ts             # Mantine theme
        └── components/
            ├── TopBar.tsx
            ├── StatusCard.tsx
            ├── EffectCard.tsx
            ├── SettingsDrawer.tsx
            ├── ParamField.tsx
            ├── ApiKeyModal.tsx
            └── Footer.tsx
```

## Development

```bash
# Tests + lint (from the repo root)
python -m pytest          # backend suite
ruff check .              # backend lint

# Frontend build / audit
cd frontend && npm run build && npm audit --audit-level=high
```

## Troubleshooting

**Device not reachable**
- Confirm the device and server are on the same LAN subnet
- Check that port 6668 is not firewalled
- If running in Docker, ensure `network_mode: host` or correct bridge networking

**"Invalid credentials" / connection refused**
- The local key may have rotated — re-run `python -m tinytuya wizard` and update `DEVICE_KEY`
- Confirm `DEVICE_VERSION=3.5`

**Frontend shows "Could not load effects"**
- The backend may be down, or (if `API_KEY` is set) the browser has no key — the UI prompts for it on a `401`.

**Status shows standby while device is on**
- DP 20 (power) may be `false` even when the bar is displaying color. Activating any effect via the frontend will send a power-on command first.

## License

MIT — see [LICENSE](LICENSE).
