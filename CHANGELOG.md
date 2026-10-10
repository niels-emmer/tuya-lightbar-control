# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

A hardening, cleanup, and tooling refresh of the 1.0.0 codebase.

### Added

- **API-key authentication.** A shared-secret key (`API_KEY`) now guards every
  `/api/*` route and the docs routes, via `X-API-Key` or
  `Authorization: Bearer`. Compared in constant time. Unset `API_KEY` disables
  auth and logs a loud startup warning. `GET /healthz` stays open.
- **Backend test suite** (43 tests) covering the driver encoders, effect
  registry, parameter coercion, settings store, API routes, the auth middleware,
  and the SPA path-traversal guard.
- **CI** (GitHub Actions): backend `ruff check` + `pytest` on Python 3.13, and a
  frontend `npm ci` + build + `npm audit --audit-level=high`.
- **Container healthcheck** hitting `/healthz`, plus a pinned `ruff` config in
  `pyproject.toml`.

### Changed

- **Backend dependencies upgraded** and the runtime retargeted to **Python 3.13**
  (container base `python:3.13-slim-bookworm`).
- **Frontend upgraded** to React 19, Mantine 9, Vite 8, and TypeScript 7.
- **Documentation overhaul** — expanded README, architecture/deployment docs,
  and an agent playbook (`AGENTS.md`).

### Fixed

- **SPA path traversal.** The catch-all route now resolves the requested path and
  confines it to `frontend/dist`, so requests such as `GET /../../.env` fall back
  to `index.html` instead of escaping the static directory.
- **Crypto `coin` parameter validation** — the symbol is now matched against a
  strict `[A-Z0-9]{4,20}` pattern before use.
- **Weather source bug** — weather-backed effects (rain, air quality) read the
  location from `settings.json`, not `.env`, so UI edits take effect.

### Security

- **Container hardening** — runs as non-root (`app`, uid 1000), `cap_drop: [ALL]`,
  and `no-new-privileges:true`.
- API-key auth (see Added) and the SPA traversal fix (see Fixed).

### Removed

- **`settings.json` is no longer tracked** — it is runtime state, gitignored, and
  shipped as `settings.json.example` for the deploy host to copy.

### Internal

- **Driver payload dedupe** — DP 61 segment payloads are built by one helper
  (`_segment_payload`) instead of duplicated across call sites.
- **Atomic settings writes** — `settings.json` is written to a temp file and
  atomically replaced, so a crash mid-write cannot truncate it.
- **Parameter coercion** — effect params are coerced and clamped via
  `effects/_params.py` helpers instead of ad-hoc casts.

## [1.0.0]

Initial release.

### Added

- Low-latency REST API for the Battletron Gaming Light Bar (Tuya v3.5, LAN) with
  whole-bar (DP 24) and per-segment (DP 61) colour control, power, and hardware
  scenes (DP 51).
- React + Mantine frontend (PWA) for manual control and effect management.
- Effect engine (`effect_runner.py`) running one async effect at a time, with
  nine built-in effects: `crypto`, `rain`, `countdown`, `random`, `trumps_truths`,
  `network_traffic`, `claude_usage`, `air_quality`, and `home_power`.
- Persistent UI settings (`brightness`, `auto_on`, `auto_off`, weather location)
  with a background auto on/off scheduler.
- Dockerfile (multi-stage: Node build → Python runtime) and Docker Compose
  deployment.
