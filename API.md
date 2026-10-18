# Lightbar Monitor API

> Machine-readable description for agent integration. Keep this file current — agents read it instead of probing the service.
>
> A live OpenAPI spec is also served by the app itself (all three require the API key):
> `GET /openapi.json` · `GET /docs` (Swagger UI) · `GET /redoc`.

Base URL: `http://<host>:8042` (the app's published port)
Auth: API key in `X-API-Key`, or `Authorization: Bearer <key>`. If `API_KEY` is empty, auth is disabled.
Version: 1.0.0

There are two ways in, depending on where the caller runs:

| Caller | URL | Key |
|--------|-----|-----|
| LAN / external app / Home Assistant | `http://<host>:8042` | supply `X-API-Key` yourself |
| A container on the same Docker host | `http://host.docker.internal:8043` | the `lightbar-proxy` sidecar injects the key — send **no** key |

`GET /healthz` is unauthenticated (container healthcheck).

## Endpoints

### GET /api/status

Device status: reachability, power, mode, whole-bar colour, and the running effect.

Example:

```bash
curl -s http://<host>:8042/api/status -H "X-API-Key: $KEY"
```

```json
{ "online": true, "power": true, "mode": "colour",
  "color": { "h": 231, "s": 100, "v": 80 }, "effect": null }
```

- `mode` is `"effect"` while an effect is active, otherwise the device's DP 21 (`"colour"` / `"scene"`).
- `color` is the whole-bar DP 24 register, and is `null` whenever it does **not** describe what is on the bar — while an effect is active, or after any per-segment (`/api/segments`, `/api/segment/{n}`) or scene write. The device keeps reporting the last whole-bar colour it was given, so echoing it would hand a snapshot/restore caller a stale colour.
- `effect` is `{ "name", "params" }` when one is running, else `null`.
- `color` is also `null` when unknown; `online: false` means the device did not answer.

> **Snapshot/restore: key off `effect`, not `color`.** Read `GET /api/status`; if `effect` is non-null, restore by re-activating that `{name, params}`; if it is null and `color` is set, restore with `POST /api/color`; if both are null there is no known whole-bar colour to restore.

### POST /api/power

Turn the bar on or off.

Body:

```json
{ "on": true }
```

### POST /api/color

Set the whole bar to one HSV colour instantly (DP 24, ~10 ms). Stops any running effect.

Body:

```json
{ "h": 231, "s": 100, "v": 80 }
```

`h` 0–360, `s` 0–100, `v` 0–100.

### POST /api/segment/{n}

Set one segment (`n` 1–20, left to right) via DP 61. Minimum ~200 ms between calls.

Body: `{ "h": 231, "s": 100, "v": 80 }`

### POST /api/segment/{n}/off

Turn off a single segment. No body.

### POST /api/segments

Set up to 20 segments in one persistent-connection sweep — the route for data-driven patterns.

Body: an array of up to 20 entries, index 0 = segment 1; `null` turns a segment off.

```json
{ "colors": [ { "h": 120, "s": 100, "v": 80 }, null, { "h": 0, "s": 100, "v": 80 } ] }
```

### POST /api/scene

Trigger a native Tuya hardware animation (DP 51).

Body:

```json
{ "type": 1, "speed": 50, "colors": [[255, 0, 0], [0, 255, 0]] }
```

`type`: 0=static, 1=flow, 2=flash, 3=wave. `speed` 0–100. `colors`: 1–7 `[r,g,b]` (0–255).

### GET /api/effects

List every registered effect with its label, description, and **parameter schema**. This is dynamic — it always reflects what the build registers, so call it instead of hardcoding effect names.

Example response (one entry):

```json
[
  {
    "name": "polestar",
    "label": "Polestar",
    "description": "Charging state of a Polestar EV, …",
    "params": []
  },
  {
    "name": "rain",
    "label": "Rain Probability",
    "description": "…",
    "params": [
      { "key": "window", "label": "Window", "type": "select", "default": "60",
        "placeholder": "", "options": [ { "value": "15", "label": "15 min" } ] }
    ]
  }
]
```

Each param has `key`, `label`, `type` (`text` | `number` | `select` | `slider`) and `default`; `select` adds `options`, numeric types add `min`/`max`/`step`/`unit`.

### GET /api/effect

The currently active effect and its params, or `null`.

```json
{ "name": "polestar", "params": {} }
```

### POST /api/effect

Activate an effect by name (stops any running one first). Brightness comes from saved settings.

Body:

```json
{ "name": "rain", "params": { "window": "60" } }
```

```bash
curl -s -X POST http://<host>:8042/api/effect \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"name":"polestar","params":{}}'
```

Returns `{"ok": true, "name": "polestar"}`. An unknown name is `404`.

### DELETE /api/effect

Stop the running effect. The bar keeps its last colour. No body.

### GET /api/settings

App settings (`settings.json`).

```json
{ "brightness": 80, "auto_on": "07:00", "auto_off": "23:00",
  "weather_lat": 52.37, "weather_lon": 4.89 }
```

### PUT /api/settings

Persist settings. Send the full object.

- `brightness` 0–100, applied to effects on next activation.
- `auto_on` / `auto_off` are `HH:MM` (24h) or `null` to disable.
- `weather_lat` / `weather_lon` are used by the weather-backed effects.

### GET /healthz

Unauthenticated liveness probe. `{"ok": true}`.

## Conventions

- **Errors**: JSON `{"detail": "<message>"}` with 4xx/5xx. `401` = missing/wrong key, `404` = unknown path or effect, `422` = validation, `502` = device write failed, `503` = device not configured.
- **Unknown paths 404** — there is no SPA catch-all, so a probe for a spec file that does not exist returns an honest 404 rather than an HTML page.
- **Latency**: whole-bar write (DP 24) ~10 ms; single segment (DP 61) ~200 ms; a full 20-segment sweep ~5 s. Do not design for sub-second per-segment refresh.
- **One effect at a time.** Effect routes run a continuous async loop; activating another stops the current one.
- **Idempotency**: `GET` is safe to retry; `POST /api/color`, `/api/power`, `/api/scene`, `/api/segments` are safe to repeat (last write wins). `POST /api/effect` restarts the named effect.
- **Device mode**: segment and whole-bar writes only take effect once mode DP 21 = `"colour"`; the driver sets this itself, so no caller action is needed.
