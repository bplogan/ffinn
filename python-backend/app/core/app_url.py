"""Resolve the public frontend base URL for links in transactional emails."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.core.config import settings as cfg

if TYPE_CHECKING:
    from fastapi import Request

    from app.services.host_settings import HostSettings


def _normalize_url(url: str) -> str:
    return url.rstrip("/")


def _is_localhost(hostname: str | None) -> bool:
    return hostname in ("localhost", "127.0.0.1", "::1")


def _is_allowed_frontend_origin(url: str) -> bool:
    normalized = _normalize_url(url)
    allowed = {_normalize_url(o) for o in cfg.cors_origins}
    allowed.add(_normalize_url(cfg.app_url))

    if normalized in allowed:
        return True

    if cfg.is_development:
        parsed = urlparse(normalized)
        if parsed.scheme in ("http", "https") and _is_localhost(parsed.hostname):
            return True

    return False


def _origin_from_referer(referer: str) -> str | None:
    parsed = urlparse(referer)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return None


def _default_app_url(host_settings: HostSettings | None) -> str:
    """Env APP_URL wins in development so shared DB prod URLs don't leak into local emails."""
    if cfg.is_development:
        return _normalize_url(cfg.app_url)
    if host_settings is not None:
        return _normalize_url(host_settings.app_url)
    return _normalize_url(cfg.app_url)


def resolve_frontend_url(
    request: Request | None = None,
    host_settings: HostSettings | None = None,
) -> str:
    """Pick the frontend origin for email links (reset password, confirm email, etc.)."""
    default = _default_app_url(host_settings)

    if request is None:
        return default

    for header in (request.headers.get("origin"), _origin_from_referer(request.headers.get("referer") or "")):
        if header and _is_allowed_frontend_origin(header):
            return _normalize_url(header)

    return default
