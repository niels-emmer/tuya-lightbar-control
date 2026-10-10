# ── Stage 1: build the React frontend ──────────────────────────────────────
FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ── Stage 2: Python runtime ─────────────────────────────────────────────────
# Base images are pinned to explicit Debian variants. Pin to a digest
# (image@sha256:...) in CI for full supply-chain reproducibility.
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Bring in the built frontend where main.py expects it
COPY --from=frontend-builder /app/frontend/dist ../frontend/dist

# Run as a non-root user. uid 1000 matches the typical host user so the
# bind-mounted settings.json stays writable.
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
