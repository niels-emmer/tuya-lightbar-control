# AGENTS.md

A practical playbook for AI coding agents working in this repo.

## What this is

`tuya-lightbar-control` is a low-latency REST API + React frontend for
segment-level control of a **Battletron Gaming Light Bar** (Tuya v3.5, LAN
protocol, 20 addressable segments). Local/LAN use only. It was built agentically
(prompted AI-assisted development).

The backend controls the device directly over the LAN via `tinytuya`. The
frontend is a thin client over the API. Nine effects push live data (crypto,
weather, network traffic, power, etc.) to the bar.

## Layout

| Path | What lives there |
|------|------------------|
| `backend/main.py` | FastAPI app, all route handlers, SPA serving |
| `backend/auth.py` | `ApiKeyMiddleware` — shared-secret auth on `/api/*` + docs |
| `backend/lightbar.py` | `LightbarDriver` — thread-safe tinytuya wrapper + DP encoders |
| `backend/effect_runner.py` | Effect lifecycle (one effect at a time) |
| `backend/config.py` | `Settings` (pydantic-settings), reads `.env` |
| `backend/models.py` | Request/response schemas + `AppSettings` defaults |
| `backend/settings_store.py` | Persistent `settings.json` (atomic writes) |
| `backend/effects/*.py` | One file per effect, plus `base.py`, `registry.py`, `_params.py` |
| `backend/tests/` | pytest suite |
| `frontend/src/` | React app (`api.ts` client, `components/`) |
| `Dockerfile` | Multi-stage: Node build → Python runtime, non-root |
| `docker-compose.yml` | Runtime config, port `8042:8000`, `/proc/net` mount |
| `pyproject.toml` | pytest + ruff config |

## Commands

All backend commands run **from `backend/`** unless noted. Tests run from the
**repo root** per `pyproject.toml`.

```bash
# Backend dev
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp ../.env.example ../.env        # fill in device credentials
uvicorn main:app --reload --port 8000

# Frontend dev (proxies /api -> http://localhost:8042)
cd frontend && npm install && npm run dev

# Tests + lint (from repo root)
python -m pytest                  # 43 tests
ruff check .

# Frontend build / audit
cd frontend && npm run build && npm audit --audit-level=high

# Docker
docker compose up -d --build      # API on host port 8042
```

## Conventions

- **Python 3.13** everywhere (local venv, container, CI). No need for the old
  `Optional[X]` workaround, but `from __future__ import annotations` is kept in
  every module — match it.
- **Flat backend imports** — `import main`, `from config import get_settings`.
  The `backend/` directory is on `sys.path` (see `pyproject.toml` `pythonpath`).
  Do not convert these to relative/package imports.
- **One effect per file.** Subclass `BaseEffect`, set `name`/`label`/
  `description`/`params_schema`, implement `async def run(driver, brightness,
  params)`, then register the instance in `effects/registry.py`.
- **Coerce effect params** with the helpers in `effects/_params.py`
  (`as_float`, `as_int`, `as_str`, `as_choice`) — never trust raw JSON params.
- **Long device writes block** — call `driver.set_all_segments` /
  `set_power` via `loop.run_in_executor` / `asyncio.to_thread`, never directly on
  the event loop.
- **Never commit secrets** — `.env` and `settings.json` are gitignored. Do not
  print or inline device keys or `API_KEY`.
- **Ruff**: line length 100, rules `E, F, I, W`, target `py313`.

## Known traps

- **~200 ms per segment.** A single DP 61 segment write takes ~200 ms; a full
  20-segment sweep is ~5 s (`segment_delay=0.25`, patterns use 0.2). Never design
  an effect that expects sub-second per-segment refresh. Whole-bar DP 24 writes
  are ~10 ms and are the right tool for fast animation.
- **`DP 21 = "colour"` first.** The device ignores DP 24 / DP 61 writes unless
  mode DP 21 has been set to `"colour"` in the same session. The driver already
  does this; keep it if you touch the driver.
- **`settings.json` is runtime state**, not source. It is gitignored and shipped
  as `settings.json.example`; the container bind-mounts it. Don't track it, and
  don't treat it as a config default — defaults live on the `AppSettings` model.
- **`API_KEY` unset ⇒ open API.** Auth is disabled when `API_KEY` is empty (with
  a startup warning). Remember this when reasoning about "is this route
  protected".
- **The frontend does not send the API key.** `frontend/src/api.ts` issues plain
  `/api/*` requests. Enabling `API_KEY` breaks the bundled UI's calls unless you
  add key handling.
- **Frontend lockfile is committed** (`frontend/package-lock.json`); CI uses
  `npm ci`. Keep it in sync when changing `package.json`.
