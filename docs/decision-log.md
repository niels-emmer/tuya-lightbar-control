# Decision Log

Architecture and design decisions, newest first. Format: `## YYYY-MM-DD — <decision>`
with **Context / Decision / Consequences**.

## 2026-10-10 — Add paho-mqtt for the `home_power` effect

**Context.** The `home_power` effect visualises whole-home power draw from a DSMR
P1 smart-meter reader. That reader publishes readings to an MQTT broker; there was
no MQTT client in the stack.

**Decision.** Add `paho-mqtt` (2.1.0) as a backend runtime dependency and
subscribe to the meter topic inside the effect. Support both paho 2.x (explicit
callback API version) and 1.x, since the constructor differs between them.

**Consequences.** The app gains a dependency and an optional runtime dependency on
an MQTT broker. When the broker is unreachable the effect degrades to a dim
heartbeat rather than failing; the rest of the app is unaffected. MQTT is only
needed for this one effect.

## 2026-10-10 — Weather location sourced from `settings.json`, not `.env`

**Context.** `WEATHER_LAT` / `WEATHER_LON` existed as `.env` values, but the
location is something users want to change from the UI. Effects were reading the
wrong source, so UI edits had no effect.

**Decision.** Treat `.env` weather values as a **first-run seed only**: on first
startup they seed `settings.json`, which is then authoritative. Weather-backed
effects (`rain`, `air_quality`) read the location via `settings_store.weather()`.

**Consequences.** The UI fully controls the location after first run. Changing
`.env` weather values later has no effect — a possible source of confusion, hence
the documented "seed only" wording.

## 2026-10-10 — `settings.json` is runtime state, untracked

**Context.** `settings.json` (brightness, auto on/off, weather location) was
tracked in git, so runtime edits dirtied the working tree and risked leaking
per-install state into the repo.

**Decision.** Stop tracking `settings.json`. Gitignore it, ship a
`settings.json.example` template, and have the deploy host copy it into place.
The container bind-mounts `./settings.json:/app/settings.json`.

**Consequences.** Deploys must create `settings.json` from the example before
startup (otherwise Docker creates a directory at the mount path). Settings
survive rebuilds and are never committed. Model-level defaults remain the single
source of truth for default values.

## 2026-10-10 — Target Python 3.13

**Context.** The original code targeted an older interpreter (system Python 3.9)
and worked around it with `Optional[X]` unions and `from __future__ import
annotations` everywhere.

**Decision.** Standardise on **Python 3.13** across the local venv, the container
(`python:3.13-slim-bookworm`), CI, and the ruff `target-version`. Dependencies
were bumped to match.

**Consequences.** One interpreter version everywhere removes drift between dev
and prod. The `from __future__ import annotations` imports are kept for
consistency. `uvicorn[standard]` and the pinned dependency set are validated
against 3.13.

## 2026-10-10 — Fix SPA path traversal via a containment check

**Context.** The catch-all route that serves the built SPA joined the request
path onto `frontend/dist` without checking the result. A request such as
`GET /../../.env` could resolve outside the static directory and leak files.

**Decision.** Resolve the candidate path and confine it to `_DIST` with
`Path.is_relative_to()`. If the resolved path is not a real file inside `dist`,
fall back to `index.html`. Covered by regression tests in `test_security.py`.

**Consequences.** Traversal attempts (including absolute paths, which replace the
base in pathlib) serve `index.html` instead of leaking files. Any legitimate file
must live under `frontend/dist`.

## 2026-10-10 — API-key auth chosen over loopback binding

**Context.** The service was completely open: any host that could reach the port
could drive the lightbar. The app is LAN-only by design, but a shared LAN still
includes untrusted or guest devices.

**Decision.** Add a shared-secret API key (`API_KEY`) enforced by middleware on
`/api/*` and the docs routes, accepted via `X-API-Key` or `Authorization:
Bearer`, compared in constant time. Chose this over binding to loopback (which
would break access from other LAN devices and the frontend) and over per-user
auth (overkill for a single-owner LAN device). `GET /healthz` stays open for the
container healthcheck. With `API_KEY` empty, auth is disabled and the app logs a
loud warning.

**Consequences.** LAN clients must send the key once it is set. The bundled
frontend does not yet attach the key, so enabling it affects the UI's own calls —
API clients are the primary target. The open-by-default behaviour keeps local dev
and trusted-LAN use frictionless, at the cost of needing a deliberate opt-in to
secure a deployment.
