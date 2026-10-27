"""
Tests for admin-only settings endpoints.
Covers:
  - GET  /api/settings        — 401 unauthenticated, 403 non-admin, 200 admin
  - POST /api/settings        — 401 unauthenticated, 403 non-admin, 200 admin
  - PUT  /api/settings        — 403 non-admin
  - GET  /api/settings/public — no auth required (public)
  - GET  /api/settings/{key}  — 403 non-admin, 200 admin
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from unittest.mock import patch


# ── Disable rate-limiting ──────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def no_rate_limit():
    with patch("app.core.security_middleware._ip_limiter.is_allowed", return_value=True):
        yield


_PASSWORD = "TestPass123!"


async def _register_and_login(client: AsyncClient, tag: str) -> tuple[str, str]:
    email = f"settings_{tag}_{uuid.uuid4().hex[:6]}@test.com"
    username = f"settings_{tag}_{uuid.uuid4().hex[:6]}"

    reg = await client.post("/api/auth/register", json={
        "user_name": username,
        "email": email,
        "password": _PASSWORD,
    })
    assert reg.status_code == 201, reg.text
    user_id = reg.json().get("user_id")
    assert user_id

    login = await client.post("/api/auth/login", json={
        "username_or_email": email,
        "password": _PASSWORD,
    })
    if login.status_code == 400:
        pytest.skip("Email confirmation required in this environment")
    assert login.status_code == 200, login.text
    token = login.json().get("access_token") or login.json().get("token")
    return user_id, token


async def _make_admin(user_id_str: str) -> None:
    import app.infrastructure.database as _db_module
    from app.domain.models.identity import IdentityRole, IdentityUserRole
    from sqlalchemy import select

    uid = uuid.UUID(user_id_str)
    async with _db_module.AsyncSessionLocal() as session:
        role = (await session.execute(
            select(IdentityRole).where(
                IdentityRole.normalized_name == "ADMIN",
                IdentityRole.tenant_id.is_(None),
            )
        )).scalar_one_or_none()
        if not role:
            role = IdentityRole(id=uuid.uuid4(), name="Admin", normalized_name="ADMIN", tenant_id=None)
            session.add(role)
            await session.flush()

        existing = (await session.execute(
            select(IdentityUserRole).where(
                IdentityUserRole.user_id == uid,
                IdentityUserRole.role_id == role.id,
            )
        )).scalar_one_or_none()
        if not existing:
            session.add(IdentityUserRole(user_id=uid, role_id=role.id))
        await session.commit()


async def _get_admin_token(client: AsyncClient, tag: str) -> str:
    email = f"sadmin_{tag}_{uuid.uuid4().hex[:6]}@test.com"
    username = f"sadmin_{tag}_{uuid.uuid4().hex[:6]}"

    reg = await client.post("/api/auth/register", json={
        "user_name": username,
        "email": email,
        "password": _PASSWORD,
    })
    assert reg.status_code == 201, reg.text
    user_id = reg.json().get("user_id")
    assert user_id

    login1 = await client.post("/api/auth/login", json={
        "username_or_email": email,
        "password": _PASSWORD,
    })
    if login1.status_code == 400:
        pytest.skip("Email confirmation required in this environment")
    await _make_admin(user_id)

    login2 = await client.post("/api/auth/login", json={
        "username_or_email": email,
        "password": _PASSWORD,
    })
    assert login2.status_code == 200
    return login2.json().get("access_token") or login2.json().get("token")


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/settings/public — no auth required
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_public_settings_no_auth(client: AsyncClient):
    resp = await client.get("/api/settings/public")
    assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/settings — requires Admin
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_settings_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/settings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_settings_non_admin_forbidden(client: AsyncClient):
    _, token = await _register_and_login(client, "gsnonadm")
    resp = await client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_settings_admin_success(client: AsyncClient):
    token = await _get_admin_token(client, "gsadm")
    resp = await client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    # Should return a list or dict of settings
    assert isinstance(resp.json(), (list, dict))


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/settings/{key} — requires Admin
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_setting_key_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/settings/somekey")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_setting_key_non_admin_forbidden(client: AsyncClient):
    _, token = await _register_and_login(client, "gsknonadm")
    resp = await client.get("/api/settings/somekey", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_setting_key_admin_success(client: AsyncClient):
    admin_token = await _get_admin_token(client, "gskadm")
    resp = await client.get("/api/settings/anykey", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
    assert "key" in resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/settings — requires Admin
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_post_setting_unauthenticated(client: AsyncClient):
    resp = await client.post("/api/settings", json={"key": "test.key", "value": "hello"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_setting_non_admin_forbidden(client: AsyncClient):
    _, token = await _register_and_login(client, "psnonadm")
    resp = await client.post(
        "/api/settings",
        json={"key": "test.key", "value": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_post_setting_admin_success(client: AsyncClient):
    admin_token = await _get_admin_token(client, "psadm")
    resp = await client.post(
        "/api/settings",
        json={"key": "test.setting.key", "value": "test_value"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert "message" in resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# PUT /api/settings (bulk) — requires Admin
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_put_settings_unauthenticated(client: AsyncClient):
    resp = await client.put("/api/settings", json={"settings": []})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_put_settings_non_admin_forbidden(client: AsyncClient):
    _, token = await _register_and_login(client, "putnonadm")
    resp = await client.put(
        "/api/settings",
        json={"settings": [{"key": "x", "value": "y"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_put_settings_admin_success(client: AsyncClient):
    admin_token = await _get_admin_token(client, "putadm")
    resp = await client.put(
        "/api/settings",
        json={"settings": [{"key": "bulk.test.key", "value": "bulk_value"}]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert "message" in resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/settings/groups — requires Admin
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_setting_groups_non_admin_forbidden(client: AsyncClient):
    _, token = await _register_and_login(client, "grpnonadm")
    resp = await client.get("/api/settings/groups", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_setting_groups_admin_success(client: AsyncClient):
    admin_token = await _get_admin_token(client, "grpadm")
    resp = await client.get("/api/settings/groups", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
