# Contributing

Thanks for taking a look. This is a small, LAN-only hobby project, so the bar for
contributions is pragmatic: keep changes focused, tested, and consistent with the
existing code.

## Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp ../.env.example ../.env         # fill in device credentials
uvicorn main:app --reload --port 8000
```

Python **3.13** is the target (local, container, and CI all agree).

### Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173, proxies /api -> :8042
```

Node **22** is what CI and the Docker build use.

## Tests and lint

Run the backend checks **from the repo root** (see `pyproject.toml`):

```bash
python -m pytest                   # 43 tests
ruff check .                       # E, F, I, W; line length 100
```

Frontend:

```bash
cd frontend
npm run build                      # tsc + vite build
npm audit --audit-level=high
```

All of the above run in CI (`.github/workflows/ci.yml`) on every PR. Make sure
they pass locally first.

## Making changes

- **Keep the diff focused.** One logical change per PR; no drive-by refactors.
- **Add a test** for bug fixes and new behaviour. The suite is small and fast —
  extend it rather than replacing it.
- **Don't commit secrets.** `.env` and `settings.json` are gitignored and must
  stay that way. Never inline device keys or `API_KEY`.
- **Match existing style** — `from __future__ import annotations`, flat backend
  imports, one effect per file, param coercion via `effects/_params.py`.

### Adding an effect

1. Create `backend/effects/<name>.py` with a `BaseEffect` subclass (`name`,
   `label`, `description`, `params_schema`, `async def run(...)`).
2. Register the instance in `backend/effects/registry.py`.
3. Coerce params with the `_params.py` helpers.
4. Remember the **~200 ms/segment** hardware constraint — use whole-bar DP 24 for
   fast animation.
5. Add a rendering/registry test.

## Branch naming

Use a short, prefixed branch name:

```
feat/<short-description>
fix/<short-description>
chore/<short-description>
docs/<short-description>
```

## Commit style

[Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <summary>
```

Common types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `security`.
Example: `fix(effects): clamp crypto coin symbol before use`.

## Pull requests

- Give the PR a clear description: **what** changed and **why**.
- Note how you verified it (commands run, manual checks).
- Keep CI green. Link any related issue.
- Changes touching auth, device writes, or the container image get a closer
  review — call those out explicitly.
