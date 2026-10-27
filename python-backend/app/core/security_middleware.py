"""
Security middleware and rate-limiter setup for PEN-test readiness.

Provides:
- SecurityHeadersMiddleware  — OWASP-recommended HTTP security headers
- RequestSizeLimitMiddleware — 413 on oversized requests
- RequestLoggingMiddleware   — structured logging (no secrets)
- rate_limiter               — slowapi Limiter (in-memory; swap to Redis in prod)
- build_rate_limit_dep()     — FastAPI Depends factory for per-endpoint limits
"""
from __future__ import annotations

import time
import threading
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import ORJSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings

# ── Rate limiter (shared singleton — used by main.py for global limits) ───────
rate_limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_default_per_minute}/minute"],
    storage_uri=settings.rate_limit_storage_uri or "memory://",
)


# ── Per-endpoint rate limiter (Depends-based, FastAPI-compatible) ─────────────

class _InMemoryIPLimiter:
    """
    Simple sliding-window counter keyed by IP.
    Thread-safe; does not require Redis.
    """
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # {ip: deque of request timestamps (float)}
        self._windows: dict[str, deque] = defaultdict(deque)

    def is_allowed(self, ip: str, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            dq = self._windows[ip]
            # drop old entries
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= max_requests:
                return False
            dq.append(now)
            return True


_ip_limiter = _InMemoryIPLimiter()


def build_rate_limit_dep(max_requests: int, window_seconds: int = 60):
    """
    Return a FastAPI Depends() callable that enforces a per-IP rate limit.

    Usage::

        @router.post("/login", dependencies=[Depends(build_rate_limit_dep(10))])
        async def login(body: LoginRequest, db: DBSession):
            ...
    """
    async def _check(request: Request) -> None:
        # Only honour X-Forwarded-For when the deployment explicitly opts in via
        # settings.trust_forwarded_headers (i.e. behind a known reverse proxy).
        # Otherwise any client could spoof the header to bypass per-IP throttles.
        ip: str = "unknown"
        if settings.trust_forwarded_headers:
            xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            if xff:
                ip = xff
        if ip == "unknown" and request.client:
            ip = request.client.host
        if not _ip_limiter.is_allowed(ip, max_requests, window_seconds):
            raise _rate_limit_response()

    return _check


def _rate_limit_response():
    from fastapi import HTTPException
    return HTTPException(
        status_code=429,
        detail={"error": "RATE_LIMIT_EXCEEDED", "message": "Too many requests. Please slow down."},
        headers={"Retry-After": "60"},
    )


def check_rate_limit_by_key(key: str, max_requests: int, window_seconds: int = 60) -> None:
    """
    Enforce a sliding-window rate limit keyed by an arbitrary string (e.g. user_id).
    Raises HTTP 429 if the key has exceeded *max_requests* within *window_seconds*.

    Usage in a route handler::

        check_rate_limit_by_key(str(body.user_id), max_requests=5, window_seconds=60)
    """
    if not _ip_limiter.is_allowed(f"__keyed__{key}", max_requests, window_seconds):
        raise _rate_limit_response()


# ── Security headers ──────────────────────────────────────────────────────────
_SECURITY_HEADERS: dict[str, str] = {
    # Prevent the browser from guessing content type
    "X-Content-Type-Options": "nosniff",
    # Clickjacking protection
    "X-Frame-Options": "DENY",
    # Legacy XSS filter (belt-and-suspenders)
    "X-XSS-Protection": "1; mode=block",
    # Referrer policy — don't leak full URL to third parties
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Restrict browser features
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    # Suppress server info
    "Server": "ffinn",
    # Content Security Policy — tight default; relax per-route if needed
    "Content-Security-Policy": (
        "default-src 'none'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
}

_HSTS_HEADER = "max-age=63072000; includeSubDomains; preload"  # 2 years


# Relaxed CSP for the Swagger/ReDoc documentation pages (dev only).
# Allows CDN assets that FastAPI's built-in docs pages load from jsdelivr.net.
_DOCS_CSP = (
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: blob: https://fastapi.tiangolo.com https://cdn.jsdelivr.net; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self' https://cdn.jsdelivr.net; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)

_DOCS_PATHS = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach OWASP-recommended security headers to every response."""

    def __init__(self, app: ASGIApp, force_https: bool = False):
        super().__init__(app)
        self._force_https = force_https

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        # Docs pages need CDN access — override the strict default CSP.
        if request.url.path in _DOCS_PATHS:
            response.headers["Content-Security-Policy"] = _DOCS_CSP
        if self._force_https:
            response.headers["Strict-Transport-Security"] = _HSTS_HEADER
        # Remove server-identifying headers added by uvicorn/starlette
        try:
            del response.headers["x-powered-by"]
        except KeyError:
            pass
        return response


# ── Request body size limit ───────────────────────────────────────────────────

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds max_bytes."""

    def __init__(self, app: ASGIApp, max_bytes: int = 10 * 1024 * 1024):
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._max_bytes:
            return ORJSONResponse(
                status_code=413,
                content={
                    "error": "REQUEST_TOO_LARGE",
                    "message": f"Request body must not exceed {self._max_bytes // 1_048_576} MB.",
                },
            )
        return await call_next(request)


# ── Timing-safe request logging ───────────────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log method, path, status, and duration.
    Intentionally does NOT log Authorization headers, cookies, or request bodies.
    Also catches any unhandled exceptions from inner layers and converts them to a
    proper JSON 500 response so that outer CORS/GZip middleware can still process
    the response (otherwise ServerErrorMiddleware runs above CORSMiddleware and the
    500 response would be returned without CORS headers).
    """
    import structlog as _structlog
    _log = _structlog.get_logger("request")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        t0 = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            self._log.exception(
                "http unhandled",
                method=request.method,
                path=request.url.path,
                ms=ms,
            )
            return ORJSONResponse(
                status_code=500,
                content={"error": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred"},
            )
        ms = round((time.perf_counter() - t0) * 1000, 1)
        self._log.info(
            "http",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=ms,
        )
        return response
