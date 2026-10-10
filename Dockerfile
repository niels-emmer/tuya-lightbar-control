# ── Stage 1: build the React frontend ──────────────────────────────────────
FROM node:25-bookworm-slim AS frontend-builder

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

# Run as a non-root user. Set APP_UID/APP_GID to the uid/gid that owns the
# bind-mounted settings.json (see docker-compose.yml) so it stays writable.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid ${APP_GID} app 2>/dev/null || true \
    && useradd --create-home --uid ${APP_UID} --gid ${APP_GID} app \
    && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
