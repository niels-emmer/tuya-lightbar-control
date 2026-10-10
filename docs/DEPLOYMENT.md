# Deployment

The live deployment runs on the host **`office-pc`** (`192.168.101.251`) at
`/home/niels/tuya-lightbar-control`, as a single Docker Compose container built
from this repo.

```
office-pc
  /home/niels/tuya-lightbar-control
    docker compose up -d --build
      └─ container (uvicorn :8000) ──published──▶ host :8042
```

## Prerequisites

- Docker + Docker Compose on the host.
- The repo cloned to `/home/niels/tuya-lightbar-control`.
- Network reachability to:
  - the lightbar (Tuya v3.5, LAN port 6668),
  - an MQTT broker at `192.168.101.252:1883` — **only needed by the `home_power`
    effect**. The broker is anonymous; other effects work without it.
- Device credentials: device ID, local key, IP (see the README for how to obtain
  them via the tinytuya wizard).

## First-time setup

1. **Create `.env` from the example and fill in credentials:**

   ```bash
   cd /home/niels/tuya-lightbar-control
   cp .env.example .env
   $EDITOR .env
   ```

   At minimum set `DEVICE_ID`, `DEVICE_IP`, and `DEVICE_KEY`. Also **set
   `API_KEY`** to a strong shared secret — with it unset, the API is
   unauthenticated. Adjust `MQTT_*` if your broker differs.

2. **Create `settings.json` from the example.** It is runtime state, gitignored,
   and bind-mounted into the container, so it must exist on the host before
   startup:

   ```bash
   cp settings.json.example settings.json
   ```

   The container mounts `./settings.json:/app/settings.json`; if the file is
   missing Docker will create a directory in its place and the app will fail to
   write settings. Copy the example first.

3. **Build and start:**

   ```bash
   docker compose up -d --build
   ```

   The build is multi-stage (Node builds the frontend, then a Python 3.13 runtime
   serves it). The service publishes host port **8042** → container **8000**.

## Verifying the deployment

The healthcheck hits `/healthz` (unauthenticated liveness). Check it and the
container state:

```bash
curl -fsS http://127.0.0.1:8042/healthz        # {"ok": true}
docker compose ps                              # health: healthy
docker compose logs -f --tail=50               # watch startup logs
```

Then check the device route. If `API_KEY` is set, include it:

```bash
curl -fsS -H "X-API-Key: $API_KEY" http://127.0.0.1:8042/api/status
# {"online": true, "power": ..., "mode": "colour", "color": {...}}
```

If `online` is `false`, the container cannot reach the device — see the
troubleshooting notes below.

## MQTT dependency (`home_power`)

The `home_power` effect subscribes to a DSMR P1 smart-meter reader that publishes
watts over MQTT. It expects a broker on `MQTT_HOST:MQTT_PORT`
(`192.168.101.252:1883` by default) and reads topic `MQTT_TOPIC`
(`sensors/power/p1meter/actual_consumption`). The broker is anonymous. If it is
unreachable, the effect logs a warning and shows a dim heartbeat — the rest of
the app is unaffected.

## Updating

```bash
cd /home/niels/tuya-lightbar-control
git pull
docker compose up -d --build
```

The `--build` rebuilds the image from the current source; `-d` leaves it running
detached. Settings persist across rebuilds because `settings.json` is
bind-mounted, not baked into the image.

## Rollback

Because deploys are just "checkout a ref, rebuild", rollback is a git operation:

```bash
cd /home/niels/tuya-lightbar-control
git log --oneline -10                # find the last good commit
git checkout <good-commit>
docker compose up -d --build
```

To return to tracking `main` afterwards:

```bash
git checkout main
git pull
docker compose up -d --build
```

If a bad deploy left the container unhealthy, `docker compose logs` and the
`health: unhealthy` status in `docker compose ps` are the first things to check.

## Notes and gotchas

- **Port mapping.** Host **8042** → container **8000**. The frontend dev proxy and
  any local `curl` checks should target `8042`.
- **`/proc/net` mount.** `docker-compose.yml` mounts the host's `/proc/net`
  read-only at `/host_proc_net` so the `network_traffic` effect reads real host
  interface counters rather than the container's virtual interface. The effect
  falls back to `/proc/net/dev` when that mount is absent.
- **Host networking.** If the device is unreachable over bridge networking (for
  example on a VPS), uncomment `network_mode: host` in `docker-compose.yml` and
  remove the `ports:` mapping.
- **Non-root runtime.** The container runs as user `app` (uid 1000) with all
  capabilities dropped and `no-new-privileges`. uid 1000 matches the typical host
  user so the bind-mounted `settings.json` stays writable — make sure the host
  file is owned by a uid the container can write.
- **Secrets.** `.env` and `settings.json` must never be committed. Device keys and
  `API_KEY` live only on the host.
