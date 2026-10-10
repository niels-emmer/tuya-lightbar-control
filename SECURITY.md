# Security Policy

## Scope and threat model

`tuya-lightbar-control` is designed for **local (LAN) use only**. It talks to a
Tuya v3.5 lightbar over the LAN and exposes a REST API for automation. It is
**not** hardened for direct exposure to the public internet.

The realistic threat model is therefore a **trusted local network**: other
devices on your LAN, and anyone who can reach the host's port. The security
measures below are aimed at that model, not at defending a service published to
the open internet.

## Authentication

A shared-secret API key guards the API. It is configured with the `API_KEY`
environment variable (set it in `.env`).

When `API_KEY` is set, every `/api/*` route and the interactive docs routes
(`/docs`, `/redoc`, `/openapi.json`) require the key. Callers supply it in
either header:

| Header | Example |
|--------|---------|
| `X-API-Key` | `X-API-Key: <key>` |
| `Authorization` (Bearer) | `Authorization: Bearer <key>` |

The key is compared in constant time (`hmac.compare_digest`). Requests without a
valid key receive `401 Unauthorized`.

`GET /healthz` is **always unauthenticated** — it is a liveness probe used by the
container healthcheck and returns no device data.

### Running with `API_KEY` unset

If `API_KEY` is empty (the default), **authentication is disabled and the API is
completely open** to anyone who can reach it. The app logs a loud warning at
startup when this is the case:

```
API_KEY is not set — the API is UNAUTHENTICATED. Set API_KEY in .env
before exposing this service beyond a trusted host.
```

This default is convenient for local development and a trusted LAN. **Set
`API_KEY` before running anywhere it matters.**

## What is protected, and what is not

Protected by the API key (when set):

- All `/api/*` routes — device control, effects, and settings.
- The interactive docs (`/docs`, `/redoc`, `/openapi.json`).

Not protected:

- `GET /healthz` — intentionally open liveness probe, no device data.
- **The bundled web UI does not itself send the key.** The frontend's fetch
  client issues plain `/api/*` requests. If you enable `API_KEY`, the UI's own
  API calls will receive `401` unless you add key handling in the frontend or put
  it behind a reverse proxy that injects the header. Enabling the key is aimed at
  API clients (Home Assistant, scripts); plan for the UI separately.
- The device's own LAN protocol (Tuya port 6668) is untouched by this app's auth.
- Traffic between this app and third-party data sources (Binance, Open-Meteo,
  Truth Social) is outbound HTTPS and outside this project's control.

## Container hardening

The shipped `docker-compose.yml` runs the app with:

- A **non-root** user (`app`, uid 1000).
- `cap_drop: [ALL]` — all Linux capabilities dropped.
- `security_opt: [no-new-privileges:true]` — no privilege escalation.
- A `healthcheck` hitting `/healthz`.

A read-only root filesystem is intentionally **not** set, because `settings.json`
is a single-file bind-mount the app writes in place.

## Secrets

- Never commit `.env` or `settings.json` (runtime state). They are gitignored.
- Device credentials (device ID, local key, IP) and `API_KEY` belong in `.env`
  only, never in code, docs, or prompts.
- The Tuya local key rotates if the device is reset or re-paired.

## Reporting a vulnerability

Please report suspected vulnerabilities **privately**, not in a public issue.

- Preferred: open a private advisory via GitHub Security Advisories at
  `https://github.com/niels-emmer/tuya-lightbar-control/security/advisories/new`.
- Alternative: email the maintainer at **`security@example.com`**
  <!-- TODO(maintainer): replace this placeholder with a real, monitored address. -->

Please include a description, reproduction steps, and the impact you believe is
possible. As a hobby-scale, LAN-only project there is no formal SLA, but reports
will be acknowledged and triaged as time allows.

## Supported versions

This project is under active development; security fixes target the latest
`main`. There are no maintained release branches.
