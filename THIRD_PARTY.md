# Third-Party Dependencies

A ledger of the direct runtime dependencies and the licences they ship under.
Versions are the pinned backend versions (`backend/requirements.txt`) and the
declared frontend ranges (`frontend/package.json`). Verify a licence before
relying on it in a redistribution context — this file is a convenience, not legal
advice.

## Backend (Python 3.13)

| Package | Version | Licence | Purpose |
|---------|---------|---------|---------|
| fastapi | 0.143.0 | MIT | Web framework and request validation for the REST API |
| uvicorn | 0.54.0 | BSD-3-Clause | ASGI server that runs the FastAPI app |
| tinytuya | 1.20.0 | MIT | Tuya LAN protocol driver — talks to the lightbar over DP registers |
| pydantic-settings | 2.15.0 | MIT | Typed configuration loaded from environment / `.env` |
| python-dotenv | 1.2.4 | BSD-3-Clause | Loads `.env` into the process environment |
| aiohttp | 3.14.4 | Apache-2.0 | Async HTTP/WebSocket client for effect data sources |
| paho-mqtt | 2.1.0 | EPL-2.0 | MQTT client for the `home_power` effect (DSMR P1 meter) |

## Frontend (React 19 / Mantine 9 / Vite 8 / TypeScript 7)

| Package | Version | Licence | Purpose |
|---------|---------|---------|---------|
| react | ^19.3.0 | MIT | UI library |
| react-dom | ^19.3.0 | MIT | React DOM renderer |
| @mantine/core | ^9.7.1 | MIT | Component library for the dashboard UI |
| @mantine/hooks | ^9.7.1 | MIT | Mantine React hooks |
| @tabler/icons-react | ^3.49.0 | MIT | Icon set used in the UI |
| vite | ^8.3.4 | MIT | Frontend build tool and dev server |
| typescript | ^7.0.2 | Apache-2.0 | Type-checking (`tsc`) for the build |
| vite-plugin-pwa | ^2.0.0 | MIT | PWA manifest + service worker generation |

## Build / dev tooling (not shipped in the runtime image)

| Package | Version | Licence | Purpose |
|---------|---------|---------|---------|
| pytest | 9.1.1 | MIT | Backend test runner |
| httpx | 0.28.1 | BSD-3-Clause | HTTP client used by the FastAPI test client |
| ruff | 0.14.0 | MIT | Python linter/formatter |
| @vitejs/plugin-react | ^6.1.2 | MIT | React fast-refresh + JSX transform for Vite |
| postcss | ^8.5.29 | MIT | CSS processing for Mantine |
| postcss-preset-mantine | ^1.18.0 | MIT | Mantine PostCSS preset |
| postcss-simple-vars | ^7.0.1 | MIT | PostCSS variable support |

> `paho-mqtt` is dual-licensed EPL-2.0 / EDL-1.0; this project uses it under
> EPL-2.0. Verify the current upstream licence text if you redistribute.
