"""Tests for auth refresh rotation and dashboard activity."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.domain.models.audit import AuditLog
from tests.test_settings_api import _get_admin_token, _PASSWORD


@pytest.fixture(autouse=True)
def no_rate_limit():
    with patch("app.core.security_middleware._ip_limiter.is_allowed", return_value=True):
        yield


@pytest.mark.asyncio
async def test_refresh_twice_with_cookie(client: AsyncClient):
    email = f"refresh_{uuid.uuid4().hex[:6]}@test.com"
    username = f"refresh_{uuid.uuid4().hex[:6]}"
    reg = await client.post(
        "/api/auth/register",
        json={"user_name": username, "email": email, "password": _PASSWORD},
    )
    if reg.status_code == 400 and "disabled" in reg.text.lower():
        pytest.skip("Registration disabled")
    assert reg.status_code == 201, reg.text

    login = await client.post(
        "/api/auth/login",
        json={"username_or_email": email, "password": _PASSWORD},
    )
    if login.status_code == 400:
        pytest.skip("Email confirmation required")
    assert login.status_code == 200, login.text

    first = await client.post("/api/auth/refresh", json={})
    assert first.status_code == 200, first.text

    second = await client.post("/api/auth/refresh", json={})
    assert second.status_code == 200, second.text


@pytest.mark.asyncio
async def test_dashboard_activity_returns_200(client: AsyncClient):
    token = await _get_admin_token(client, "dashact")
    import app.infrastructure.database as db_module

    async with db_module.AsyncSessionLocal() as session:
        session.add(
            AuditLog(
                id=uuid.uuid4(),
                tenant_id=None,
                user_id=None,
                action="TestAction",
                entity_type="Test",
                entity_id="1",
                created_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    resp = await client.get(
        "/api/dashboard/activity",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)
