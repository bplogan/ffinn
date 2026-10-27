"""Tests for tenant management endpoints."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from unittest.mock import patch

from tests.test_settings_api import _get_admin_token, _PASSWORD


@pytest.fixture(autouse=True)
def no_rate_limit():
    with patch("app.core.security_middleware._ip_limiter.is_allowed", return_value=True):
        yield


@pytest.mark.asyncio
async def test_create_tenant_returns_201(client: AsyncClient):
    token = await _get_admin_token(client, "tenant")
    suffix = uuid.uuid4().hex[:8]
    resp = await client.post(
        "/api/tenants",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"Test Tenant {suffix}",
            "tenancyName": f"test-{suffix}",
            "adminEmail": f"admin-{suffix}@example.com",
            "adminPassword": _PASSWORD,
            "isActive": True,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "id" in body
    assert isinstance(body["id"], str)
    assert body["name"] == f"Test Tenant {suffix}"
    assert body["tenancyName"] == f"test-{suffix}"
    assert body["adminEmailAddress"] == f"admin-{suffix}@example.com"


@pytest.mark.asyncio
async def test_create_tenant_requires_admin_credentials(client: AsyncClient):
    token = await _get_admin_token(client, "tenant-req")
    suffix = uuid.uuid4().hex[:8]
    resp = await client.post(
        "/api/tenants",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"No Admin Tenant {suffix}",
            "tenancyName": f"no-admin-{suffix}",
        },
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_tenant_creates_admin_user(client: AsyncClient):
    token = await _get_admin_token(client, "tenant-user")
    suffix = uuid.uuid4().hex[:8]
    tenancy_name = f"tenant-user-{suffix}"
    admin_email = f"admin-{suffix}@example.com"
    resp = await client.post(
        "/api/tenants",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"Tenant With Admin {suffix}",
            "tenancyName": tenancy_name,
            "adminEmail": admin_email,
            "adminPassword": _PASSWORD,
            "isActive": True,
        },
    )
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]

    users_resp = await client.get(
        f"/api/tenants/{tenant_id}/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert users_resp.status_code == 200, users_resp.text
    users = users_resp.json()["items"]
    assert len(users) == 1
    assert users[0]["email"] == admin_email
    assert "Admin" in users[0]["roles"]

    login = await client.post("/api/auth/login", json={
        "username_or_email": admin_email,
        "password": _PASSWORD,
        "tenant_name": tenancy_name,
    })
    assert login.status_code == 200, login.text


@pytest.mark.asyncio
async def test_create_tenant_unauthenticated(client: AsyncClient):
    resp = await client.post(
        "/api/tenants",
        json={"name": "No Auth Tenant", "tenancyName": "no-auth"},
    )
    assert resp.status_code == 401
