"""
Tests for tenant logo endpoints — admin guard enforcement.
Covers:
  - POST   /api/tenantlogo  — 401 unauthenticated, 403 non-admin
  - DELETE /api/tenantlogo  — 401 unauthenticated, 403 non-admin
  - GET    /api/tenantlogo  — 401 unauthenticated (requires auth)
  - Admin with no tenant context gets 400 (guard passes, but no tenant set up)
"""
from __future__ import annotations

import io
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
    email = f"tenantlogo_{tag}_{uuid.uuid4().hex[:6]}@test.com"
    username = f"tlogo_{tag}_{uuid.uuid4().hex[:6]}"

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
    email = f"tladmin_{tag}_{uuid.uuid4().hex[:6]}@test.com"
    username = f"tladmin_{tag}_{uuid.uuid4().hex[:6]}"

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


_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/tenantlogo — requires Admin
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_upload_logo_unauthenticated(client: AsyncClient):
    resp = await client.post(
        "/api/tenantlogo",
        files={"file": ("logo.png", io.BytesIO(_FAKE_PNG), "image/png")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_logo_non_admin_forbidden(client: AsyncClient):
    _, token = await _register_and_login(client, "ul_nonadm")
    resp = await client.post(
        "/api/tenantlogo",
        files={"file": ("logo.png", io.BytesIO(_FAKE_PNG), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_upload_logo_admin_no_tenant_returns_400(client: AsyncClient):
    """Admin user without a tenant context should get 400, not 403.
    This confirms the role guard passes but the tenant check fires next.
    """
    admin_token = await _get_admin_token(client, "ul_adm_notenant")
    resp = await client.post(
        "/api/tenantlogo",
        files={"file": ("logo.png", io.BytesIO(_FAKE_PNG), "image/png")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Guard passed (not 403); endpoint rejects because tenant_id is None
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# DELETE /api/tenantlogo — requires Admin
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delete_logo_unauthenticated(client: AsyncClient):
    resp = await client.delete("/api/tenantlogo")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_logo_non_admin_forbidden(client: AsyncClient):
    _, token = await _register_and_login(client, "dl_nonadm")
    resp = await client.delete(
        "/api/tenantlogo",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_logo_admin_no_tenant_returns_400(client: AsyncClient):
    """Same as upload: admin without tenant → 400, confirming guard passes."""
    admin_token = await _get_admin_token(client, "dl_adm_notenant")
    resp = await client.delete(
        "/api/tenantlogo",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/tenantlogo — requires any authenticated user
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_logo_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/tenantlogo")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_logo_authenticated_no_tenant_returns_400(client: AsyncClient):
    """Authenticated user without tenant context → 400 (no tenant to look up logo for)."""
    _, token = await _register_and_login(client, "gl_auth")
    resp = await client.get(
        "/api/tenantlogo",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/tenantlogo/{identifier} — public, no auth required
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_logo_by_identifier_not_found(client: AsyncClient):
    resp = await client.get(f"/api/tenantlogo/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_logo_by_identifier_invalid_uuid_still_responds(client: AsyncClient):
    resp = await client.get("/api/tenantlogo/nonexistent-tenant-name")
    assert resp.status_code in (404, 200)  # 404 for unknown names
