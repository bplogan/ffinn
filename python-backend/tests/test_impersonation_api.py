"""Tests for user impersonation endpoints."""
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


async def _create_tenant_with_user(client: AsyncClient, tag: str) -> tuple[str, str, str, str]:
    """Create tenant and return (tenant_id, tenant_user_id, tenant_user_token, tenancy_name)."""
    admin_token = await _get_admin_token(client, f"imp_{tag}")
    suffix = uuid.uuid4().hex[:8]
    tenancy_name = f"imp-{suffix}"
    resp = await client.post(
        "/api/tenants",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": f"Imp Tenant {suffix}",
            "tenancyName": tenancy_name,
            "adminEmail": f"tenant-admin-{suffix}@example.com",
            "adminPassword": _PASSWORD,
            "isActive": True,
        },
    )
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]

    login = await client.post("/api/auth/login", json={
        "username_or_email": f"tenant-admin-{suffix}@example.com",
        "password": _PASSWORD,
        "tenant_name": tenancy_name,
    })
    assert login.status_code == 200, login.text
    tenant_token = login.json()["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tenant_token}"})
    assert me.status_code == 200, me.text
    tenant_user_id = me.json()["id"]
    return tenant_id, tenant_user_id, tenant_token, tenancy_name


@pytest.mark.asyncio
async def test_host_admin_can_impersonate_tenant_user(client: AsyncClient):
    admin_token = await _get_admin_token(client, "host_imp")
    tenant_id, tenant_user_id, _, _ = await _create_tenant_with_user(client, "host")

    resp = await client.post(
        "/api/auth/impersonate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"user_id": tenant_user_id, "tenant_id": tenant_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("is_impersonation") is True
    imp_token = body["access_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {imp_token}"})
    assert me.status_code == 200, me.text
    me_body = me.json()
    assert me_body["id"] == tenant_user_id
    assert me_body.get("isImpersonating") is True
    assert me_body.get("impersonatorUserId")


@pytest.mark.asyncio
async def test_tenant_admin_can_impersonate_same_tenant_user(client: AsyncClient):
    tenant_id, tenant_admin_id, tenant_admin_token, _ = await _create_tenant_with_user(client, "tadmin")

    suffix = uuid.uuid4().hex[:6]
    reg = await client.post("/api/auth/register", json={
        "user_name": f"member_{suffix}",
        "email": f"member_{suffix}@example.com",
        "password": _PASSWORD,
        "tenant_name": None,
    })
    assert reg.status_code == 201, reg.text
    member_id = reg.json()["user_id"]

    # Assign member to tenant via direct DB update
    import app.infrastructure.database as _db_module
    from app.domain.models.identity import IdentityUser
    from sqlalchemy import select

    async with _db_module.AsyncSessionLocal() as session:
        user = (await session.execute(select(IdentityUser).where(IdentityUser.id == uuid.UUID(member_id)))).scalar_one()
        user.tenant_id = uuid.UUID(tenant_id)
        await session.commit()

    resp = await client.post(
        "/api/auth/impersonate",
        headers={"Authorization": f"Bearer {tenant_admin_token}"},
        json={"user_id": member_id},
    )
    assert resp.status_code == 200, resp.text
    imp_token = resp.json()["access_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {imp_token}"})
    assert me.status_code == 200
    assert me.json()["id"] == member_id


@pytest.mark.asyncio
async def test_non_admin_cannot_impersonate(client: AsyncClient):
    tenant_id, tenant_admin_id, _, tenancy_name = await _create_tenant_with_user(client, "nonadmin")

    suffix = uuid.uuid4().hex[:6]
    reg = await client.post("/api/auth/register", json={
        "user_name": f"plain_{suffix}",
        "email": f"plain_{suffix}@example.com",
        "password": _PASSWORD,
    })
    assert reg.status_code == 201, reg.text
    member_id = reg.json()["user_id"]

    import app.infrastructure.database as _db_module
    from app.domain.models.identity import IdentityUser
    from sqlalchemy import select

    async with _db_module.AsyncSessionLocal() as session:
        user = (await session.execute(select(IdentityUser).where(IdentityUser.id == uuid.UUID(member_id)))).scalar_one()
        user.tenant_id = uuid.UUID(tenant_id)
        user.email_confirmed = True
        await session.commit()

    login = await client.post("/api/auth/login", json={
        "username_or_email": f"plain_{suffix}@example.com",
        "password": _PASSWORD,
        "tenant_name": tenancy_name,
    })
    assert login.status_code == 200, login.text
    member_token = login.json()["access_token"]

    resp = await client.post(
        "/api/auth/impersonate",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"user_id": tenant_admin_id},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_tenant_users_returns_serialized_list(client: AsyncClient):
    admin_token = await _get_admin_token(client, "tusers")
    tenant_id, _, _, _ = await _create_tenant_with_user(client, "tusers")

    resp = await client.get(
        f"/api/tenants/{tenant_id}/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_count"] >= 1
    assert isinstance(body["items"], list)
    assert "email" in body["items"][0]
