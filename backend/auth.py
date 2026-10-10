"""Shared-secret API-key authentication.

Every ``/api/*`` route and the interactive docs routes require the configured
API key when one is set. The key is read from the ``X-API-Key`` header or an
``Authorization: Bearer <key>`` header and compared in constant time.

If no key is configured the middleware is a no-op (auth disabled) — the caller
logs a prominent warning at startup so this is never left open by accident.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Path prefixes that require the key.
_PROTECTED_PREFIXES = ("/api/",)
# Exact paths that require the key (interactive docs).
_PROTECTED_EXACT = frozenset({"/docs", "/redoc", "/openapi.json"})


def _extract_key(request: Request) -> str | None:
    """Return the caller-supplied key from X-API-Key or a Bearer token."""
    key = request.headers.get("x-api-key")
    if key:
        return key
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _is_protected(path: str) -> bool:
    return path in _PROTECTED_EXACT or any(
        path.startswith(prefix) for prefix in _PROTECTED_PREFIXES
    )


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated requests to protected routes with 401."""

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):
        if not self._api_key:
            return await call_next(request)

        if _is_protected(request.url.path):
            provided = _extract_key(request)
            if not provided or not hmac.compare_digest(provided, self._api_key):
                logger.warning(
                    "Rejected unauthenticated request: %s %s",
                    request.method,
                    request.url.path,
                )
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)
