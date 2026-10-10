# Architecture

`tuya-lightbar-control` is a two-part app: a FastAPI backend that drives a Tuya
v3.5 lightbar over the LAN, and a React frontend that is a thin client over the
backend's REST API. This document describes the components, the data flow, the
device protocol, and the operational constraints.

## Components

```
┌───────────────────────────────┐
│  Frontend (React 19 + Mantine) │
│  Vite build → static SPA       │
│  api.ts: typed fetch client    │
└───────────────┬───────────────┘
                │ /api/*  (JSON)
                ▼
┌───────────────────────────────────────────────┐
│  FastAPI backend (backend/main.py)             │
│  • routes: device / effects / settings         │
│  • auth.py: ApiKeyMiddleware                   │
│  • effect_runner.py: one effect at a time      │
│  • settings_store.py: settings.json            │
└───────┬───────────────────────┬───────────────┘
        │ tinytuya (DP writes)   │ outbound HTTPS / MQTT / local HTTP
        ▼                        ▼
┌───────────────────┐   ┌────────────────────────────────────────┐
│  Battletron       │   │ Data sources (effects):                 │
│  Light Bar        │   │ • Binance WS (crypto)                   │
│  Tuya v3.5 LAN    │   │ • Open-Meteo (rain, air quality)        │
│  port 6668        │   │ • Truth Social (trumps_truths)          │
│  20 segments      │   │ • /proc/net (network_traffic)           │
└───────────────────┘   │ • nanoclaw daemon (claude_usage)        │
                        │ • MQTT broker (home_power)              │
                        └────────────────────────────────────────┘
```

### Backend modules

| Module | Responsibility |
|--------|----------------|
| `main.py` | FastAPI app, all route handlers, lifespan, SPA serving |
| `auth.py` | `ApiKeyMiddleware` — shared-secret auth |
| `lightbar.py` | `LightbarDriver` — thread-safe tinytuya wrapper + DP encoders |
| `effect_runner.py` | Effect lifecycle (start/stop, one active effect) |
| `config.py` | `Settings` (pydantic-settings) loaded from environment / `.env` |
| `models.py` | Request/response schemas; `AppSettings` holds the settings defaults |
| `settings_store.py` | Persistent `settings.json` with atomic writes |
| `effects/` | One file per effect + `base.py`, `registry.py`, `_params.py` |

### Frontend modules

| Module | Responsibility |
|--------|----------------|
| `App.tsx` | Root component, polling loop |
| `api.ts` | Typed fetch client for `/api/*` |
| `components/` | `TopBar`, `StatusCard`, `EffectCard`, `SettingsDrawer`, `ParamField`, `Footer` |
| `theme.ts` | Mantine theme |

## Data flow

### Manual control (frontend → API → driver → device)

1. The user acts in the UI; `api.ts` issues a JSON request to `/api/*`.
2. The matching route in `main.py` validates the body against a pydantic model
   (`models.py`).
3. The route calls a `LightbarDriver` method, which acquires the driver's
   threading lock, opens a short-lived tinytuya connection, writes the DP, and
   closes the socket.
4. The device updates the bar. The response is a small `{ "ok": true }` (or a
   `502` if the device write failed).

`GET /api/status` reads the device's DP state and decodes DP 24 back to HSV.

### Effects loop

- `EffectRunner.activate()` stops any running effect, powers the bar on, and
  spawns an `asyncio.Task` running the effect's `run()` coroutine.
- Each effect loop computes a list of up to 20 `(h, s, v)` entries (or `None` for
  "off") and pushes it with `driver.set_all_segments`, invoked through
  `loop.run_in_executor` so the blocking device I/O never stalls the event loop.
- Only one effect runs at a time. `DELETE /api/effect` cancels the task; the bar
  keeps its last colour.
- Effects that fetch remote data (crypto, rain, air quality, trumps_truths,
  claude_usage) poll on their own cadence and repaint in between. Effects with no
  data yet render a dim "heartbeat" rather than going dark.

### External data sources

| Effect | Source | Transport |
|--------|--------|-----------|
| `crypto` | Binance kline streams | WebSocket (`wss://stream.binance.com:9443`) |
| `rain` | Open-Meteo forecast | HTTPS (`api.open-meteo.com`) |
| `air_quality` | Open-Meteo air quality | HTTPS (`air-quality-api.open-meteo.com`) |
| `trumps_truths` | Truth Social public API | HTTPS (`truthsocial.com`) |
| `claude_usage` | nanoclaw-cyd-monitor daemon | HTTP (`CLAUDE_USAGE_URL`, default `http://127.0.0.1:8787/usage`) |
| `network_traffic` | Host interface counters | local file (`/proc/net/dev`, or `/host_proc_net/dev` in Docker) |
| `home_power` | DSMR P1 meter reader | MQTT (`MQTT_HOST:MQTT_PORT`, topic `MQTT_TOPIC`) |

Weather-backed effects (`rain`, `air_quality`) read the location from
`settings.json` (see below), not from `.env`.

## Device protocol quick reference

The lightbar is a Tuya v3.5 device addressed over the LAN on port 6668. Control
is via data points (DPs):

| DP | Purpose | Payload |
|----|---------|---------|
| 20 | Power | `bool` |
| 21 | Mode | `"colour"` (required before DP 24 / DP 61 writes) |
| 24 | Whole-bar HSV | 12-char hex `HHHHSSSSVVVV` |
| 51 | Hardware scene | base64 payload (`type`, `speed`, RGB colours) |
| 61 | Per-segment colour | 13-byte base64 payload, one segment (1–20) |

**Encoding.** Hue is raw degrees 0–360 as 4-digit hex (blue hue 231 → `00e7`).
Saturation and value are multiplied by 10 (range 0–1000).

**DP 61 payload layout** (13 bytes, then base64):

```
[00][01][00][14][mode][H hi][H lo][S hi][S lo][V hi][V lo][81][seg]
                 ^ 01 = solid colour ON, 02 = segment off
```

`DP 21 = "colour"` must be set in the same session before DP 24 / DP 61 writes —
the driver does this automatically in every write path.

## Timing constraints

The device tolerates only one in-flight command, and segment writes are slow:

| Operation | Latency |
|-----------|---------|
| Whole-bar write (DP 24) | ~10 ms |
| Single segment write (DP 61) | ~200 ms |
| Full 20-segment sweep | ~5 s (0.25 s/segment) |

Consequences for design:

- Use **DP 24** (`POST /api/color`) for animation — it is effectively instant.
- Use **DP 61** (`POST /api/segments`) for static data displays. Do not attempt
  sub-second per-segment refresh.
- `set_all_segments` reuses a single TCP socket for the whole sweep (far more
  reliable than reconnecting per segment) and sleeps `segment_delay` between
  writes (default 0.25 s; the patterns effect uses 0.2 s).
- All driver access is serialised through a lock, so a slow effect sweep blocks
  concurrent manual writes.

## Authentication

`ApiKeyMiddleware` (`auth.py`) guards the API:

- Applies to every path under `/api/` and to `/docs`, `/redoc`, `/openapi.json`.
- Accepts the key via `X-API-Key` or `Authorization: Bearer <key>`, compared in
  constant time.
- If `API_KEY` is empty, the middleware is a no-op and the app logs a warning at
  startup. `GET /healthz` is always open.

See `SECURITY.md` for the full policy.

## Settings persistence

- `settings.json` lives at the repo root and holds `brightness`, `auto_on`,
  `auto_off`, `weather_lat`, and `weather_lon`.
- Defaults live on the `AppSettings` model (`models.py`); `settings_store.load()`
  merges the stored overrides on top of those defaults.
- Writes are atomic: the store writes a `.tmp` file and `replace()`s it, so a
  crash mid-write cannot truncate the file.
- On first run (no `settings.json`), the lifespan hook seeds it from
  `WEATHER_LAT` / `WEATHER_LON`. After that, `settings.json` is authoritative and
  editable from the UI.
- A background task (`_auto_onoff_loop`) checks every 30 s and powers the bar
  on/off at the configured `auto_on` / `auto_off` times.
- The file is runtime state (gitignored, shipped as `settings.json.example`) and
  is bind-mounted into the container.

## Deploy topology

```
office-pc (192.168.101.251)
  /home/niels/tuya-lightbar-control
  docker compose up -d --build
    └─ container: uvicorn on :8000  ──published──▶  host :8042
         ├─ settings.json          (bind-mounted)
         ├─ /proc/net              (bind-mounted read-only → /host_proc_net)
         └─ LAN:
              ├─ lightbar          (Tuya v3.5, port 6668)
              └─ MQTT broker       (192.168.101.252:1883, for home_power)
```

The container runs as a non-root user with all capabilities dropped and
`no-new-privileges`. The healthcheck hits `/healthz`. See `docs/DEPLOYMENT.md`
for the procedure.
