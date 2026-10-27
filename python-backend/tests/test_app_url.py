"""Tests for frontend URL resolution in transactional emails."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import app.core.app_url as app_url_module
from app.core.app_url import resolve_frontend_url


def _request(origin: str | None = None, referer: str | None = None) -> MagicMock:
    req = MagicMock()
    req.headers = {}
    if origin:
        req.headers["origin"] = origin
    if referer:
        req.headers["referer"] = referer
    return req


def _dev_cfg(app_url: str = "https://ffinn.ca", cors: list[str] | None = None) -> MagicMock:
    cfg = MagicMock()
    cfg.is_development = True
    cfg.app_url = app_url
    cfg.cors_origins = cors or ["http://localhost:3000"]
    return cfg


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)
def test_resolve_frontend_url_uses_origin_on_localhost(monkeypatch, origin):
    monkeypatch.setattr(app_url_module, "cfg", _dev_cfg())

    assert resolve_frontend_url(_request(origin=origin)) == origin.rstrip("/")


def test_resolve_frontend_url_falls_back_to_env_in_development(monkeypatch):
    monkeypatch.setattr(app_url_module, "cfg", _dev_cfg(app_url="http://localhost:3000"))

    assert resolve_frontend_url() == "http://localhost:3000"
