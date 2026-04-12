# tuya-lightbar-control

A low-latency REST API and interactive demo frontend for precise, segment-level control of the **Battletron Gaming Light Bar** (Tuya v3.5, LAN protocol). Enable scripted patterns, data-driven visualizations (crypto, weather, traffic), and external integrations beyond the proprietary mobile app.

## Overview

`tuya-lightbar-control` is built for developers and enthusiasts who want **fine-grained control** over a Tuya-based RGB lightbar connected via LAN. Unlike cloud-based solutions, this project communicates directly with the device (192.168.x.x:6668), offering:

- **~200 ms round-trip latency** between segments  
- **Whole-bar animations** using DP 24 (instant HSV writes)  
- **Per-segment control** for static visualizations  
- **Hardware scenes** via the device's built-in modes  
- **REST API** for external automation and integrations  
- **Interactive demo frontend** (React + Mantine) for manual testing  

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.9+ • FastAPI • uvicorn • tinytuya |
| **Frontend** | React 18 • TypeScript • Vite • Mantine UI • Tabler Icons |
| **Device Protocol** | Tuya v3.5 LAN • tinytuya library |
| **Deployment** | Docker • Docker Compose |

## Features

✨ **REST API**
- Real-time device status queries  
- Whole-bar color control (instant, via DP 24)  
- Per-segment RGB control (1–20 segments)  
- Batch segment updates with hardware sweep  
- Built-in hardware scene triggering  
- Interactive Swagger docs (`/docs`)  

🎨 **Demo Frontend**
- Live device status display  
- Color picker for whole-bar control  
- Individual segment RGB/brightness editors  
- Scene/pattern browser  
- Settings persistence (local JSON storage)  
- Effect gallery (crypto, rain, countdown, patterns)  

⚡ **Performance**
- Minimal latency for whole-bar writes (~10 ms per DP 24 write)  
- Batch segment updates optimized for device constraints  
- Async effect runner for real-time pattern playback  

## How It Works

### Architecture

```
┌─────────────────────────────────────┐
│  Demo Frontend (React + Mantine)    │
│  http://localhost:5173              │
└──────────────┬──────────────────────┘
               │ /api/* (proxied)
               ↓
┌─────────────────────────────────────┐
│  FastAPI Backend                    │
│  http://localhost:8000              │
│  • main.py (routes)                 │
│  • lightbar.py (tinytuya wrapper)   │
│  • effect_runner.py (async effects) │
└──────────────┬──────────────────────┘
               │ Tuya v3.5 LAN
               ↓
┌─────────────────────────────────────┐
│  Battletron Lightbar                │
│  192.168.101.130:6668               │
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

**Hue encoding:** Raw degrees 0–360 as 4-digit hex (e.g., `00e7` = blue).  
**Sat/Val encoding:** Multiplied by 10 (range 0–1000).

### API Endpoints

| Method | Path | Description | Payload |
|--------|------|-------------|---------|
| `GET` | `/api/status` | Device online, power, mode, whole-bar HSV | — |
| `POST` | `/api/power` | Toggle device power | `{ "on": bool }` |
| `POST` | `/api/color` | Set whole bar color (instant) | `{ "h": 0–360, "s": 0–1, "v": 0–1 }` |
| `POST` | `/api/segment/{n}` | Set segment n (1–20) | `{ "h": 0–360, "s": 0–1, "v": 0–1 }` |
| `POST` | `/api/segment/{n}/off` | Turn off segment n | — |
| `POST` | `/api/segments` | Batch update all 20 segments | `{ "colors": [ { h,s,v } or null, ... ] }` |
| `POST` | `/api/scene` | Trigger hardware scene | `{ "type": string, "speed": int, "colors": [...] }` |
| `GET` | `/api/effects` | List available effects | — |
| `POST` | `/api/effects/{name}/start` | Start an effect | `{ "duration": ms, ...params }` |
| `POST` | `/api/effects/stop` | Stop current effect | — |

**Interactive docs:** Visit `http://localhost:8000/docs` after startup.

## Installation

### Prerequisites

- **Python 3.9+** (system or pyenv)  
- **Node.js 18+** (for frontend)  
- **Device:** Battletron Gaming Light Bar on the same LAN  
- **Device credentials:** Device ID, IP, and local key (see setup below)  

### Option 1: Local Dev Setup

#### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create .env at repo root
cp ../.env.example ../.env

# Edit .env and fill in:
# DEVICE_ID=xxx
# DEVICE_IP=192.168.x.x
# DEVICE_KEY=xxx
# DEVICE_VERSION=3.5

# Start server
uvicorn main:app --reload --port 8000
```

#### Frontend

In a new terminal:

```bash
cd frontend
npm install
npm run dev             # http://localhost:5173 (proxies /api/* to :8000)
```

#### Finding Device Credentials

1. **Device ID & Key:** Extract from Tuya Home app backup or use `tinytuya` scanner:
   ```bash
   python -m tinytuya wizard
   ```

2. **Device IP:** Check your router's DHCP table or use:
   ```bash
   arp-scan --localnet | grep -i "tuya\|battletron"
   ```

### Option 2: Docker Compose

```bash
# Create .env at repo root (see above)
cp .env.example .env
nano .env                      # Fill in device credentials

# Build and run
docker-compose up --build

# Frontend on http://localhost:5173
# Backend on http://localhost:8000
```

## Development

### Project Structure

```
.
├── README.md                    # This file
├── CLAUDE.md                    # Claude.ai coding guidance
├── Dockerfile                   # Multi-stage build (frontend + backend)
├── docker-compose.yml           # Local dev orchestration
├── settings.json                # Persisted UI settings
├── .env                         # Device credentials (local only)
├── backend/
│   ├── main.py                  # FastAPI app & route handlers
│   ├── config.py                # Pydantic settings
│   ├── models.py                # Request/response schemas
│   ├── lightbar.py              # Tuya device driver (tinytuya wrapper)
│   ├── settings_store.py        # Persistent settings
│   ├── effect_runner.py         # Async effect playback
│   ├── requirements.txt          # Python dependencies
│   └── effects/
│       ├── __init__.py
│       ├── base.py              # Effect base class
│       ├── registry.py          # Effect discovery
│       ├── crypto.py            # Crypto price ticker
│       ├── rain.py              # Rain animation
│       ├── countdown.py         # Countdown timer
│       └── patterns.py          # Pattern library
└── frontend/
    ├── package.json             # NPM dependencies
    ├── vite.config.ts           # Vite bundler config
    ├── tsconfig.json            # TypeScript config
    ├── index.html               # HTML entry point
    ├── postcss.config.cjs        # PostCSS plugins (Mantine)
    └── src/
        ├── main.tsx             # React entry (React 18)
        ├── App.tsx              # Main app component
        ├── api.ts               # HTTP client (fetch wrapper)
        ├── theme.ts             # Mantine theme config
        └── components/
            ├── StatusBar.tsx    # Device status & power toggle
            ├── EffectPanel.tsx  # Effect selector & runner
            ├── ImportExport.tsx # Settings backup/restore
            ├── SettingsDrawer.tsx # Config panel
            └── ParamField.tsx   # Dynamic form fields
```

### Running Tests & Linting

```bash
# Backend type checking (Python 3.9+ union syntax)
cd backend
mypy *.py

# Frontend type checking
cd frontend
npx tsc --noEmit

# Frontend linting
npm run lint
```

### Common Development Tasks

**Add a new effect:**
1. Create `backend/effects/my_effect.py`
2. Subclass `Effect` from `base.py`
3. Register in `backend/effects/registry.py`

**Add a new API route:**
1. Define Pydantic request/response models in `backend/models.py`
2. Add route in `backend/main.py`
3. Update frontend `api.ts` client

**Update device constraints:**
- Segment delay: `backend/lightbar.py` → `set_all_segments(segment_delay=...)`
- Whole-bar mode switching: `backend/main.py` → mode handling before DP 24/61 writes

## Performance Notes

⚠️ **Critical Constraints:**

- **Min segment delay:** ~200 ms between individual segment writes (device hardware limit)  
- **Batch sweep time:** ~5 seconds for all 20 segments (segment_delay=0.25 s)  
- **Whole-bar write:** ~10 ms (DP 24 is instant)  
- **Mode switching:** Required before segment or whole-bar color writes (DP 21 → "colour")  

**Frontend implications:**
- Do NOT attempt sub-second pattern updates in segment mode  
- Use whole-bar color for animations (DP 24)  
- Use segment mode for static data visualizations (crypto, weather)  

## Troubleshooting

**Device not reachable:**
- Verify device is on the same LAN (not behind a VPN bridge)
- Use `docker-compose` config `network_mode: host` if on VPS
- Check firewall rules on port 6668

**Tuya connection fails ("Invalid credentials"):**
- Re-scan device with `python -m tinytuya wizard`
- Ensure DEVICE_KEY is the **local key**, not the cloud key

**Frontend can't reach backend API:**
- Verify backend is running on `:8000`
- Check Vite proxy config in `frontend/vite.config.ts`

**Effect runner hangs:**
- Set `--timeout 30` in effect runner startup
- Check `backend/effect_runner.py` for infinite loops

## Deployment

### Production Checklist

- [ ] `.env` file secured (not in git)
- [ ] Backend CORS configured for your frontend domain
- [ ] Device IP is static or set via DHCP reservation
- [ ] Firewall allows outbound port 6668 (LAN device)
- [ ] Docker image tested locally before push

### Pushing to Registry

```bash
docker build -t my-registry/tuya-lightbar-control:latest .
docker push my-registry/tuya-lightbar-control:latest
```

### Kubernetes / Cloud Deploy

Mount `.env` as a ConfigMap or Secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: lightbar-creds
type: Opaque
stringData:
  DEVICE_ID: "xxx"
  DEVICE_IP: "192.168.x.x"
  DEVICE_KEY: "xxx"
```

Then reference in your Pod spec:
```yaml
envFrom:
  - secretRef:
      name: lightbar-creds
```

## Contributing

Contributions welcome! Please:

1. Fork this repo
2. Create a branch (`git checkout -b feature/my-feature`)
3. Make changes and test locally
4. Commit with clear messages
5. Push and open a pull request

## License

MIT – See LICENSE file for details.

## Related Projects

- **[lightbar](https://github.com/your-org/lightbar)** – AI-driven effect generator (sibling project)
- **[tinytuya](https://github.com/jasonacox/tinytuya)** – Open-source Tuya device library
- **[Battletron Docs](https://www.battletron.io)** – Official hardware docs

## Support

- 📧 Open an issue on GitHub
- 💬 Check `/docs` (Swagger UI) for API details
- 🔧 See CLAUDE.md for code navigation hints

---

**Built with ❤️ for hackers and makers.**
