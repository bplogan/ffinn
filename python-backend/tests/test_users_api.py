"""
Tests for user management API endpoints.
Covers:
  - PUT /api/users/me            — self-service profile update (any auth user)
  - POST /api/users/me/avatar   — self-service avatar upload (any auth user)
  - GET/PUT /api/users/{id}     — admin-only guard (non-admins get 403)
"""
from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


# ── Disable rate-limiting ──────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def no_rate_limit():
    with patch("app.core.security_middleware._ip_limiter.is_allowed", return_value=True):
        yield


# ── Credentials ────────────────────────────────────────────────────────────────
_PASSWORD = "TestPass123!"


async def _register_and_login(client: AsyncClient, tag: str) -> tuple[str, str]:
    """Register a unique user and return (user_id, access_token)."""
    email = f"users_api_{tag}_{uuid.uuid4().hex[:6]}@test.com"
    username = f"usersapi_{tag}_{uuid.uuid4().hex[:6]}"

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
    assert token
    return user_id, token


async def _make_admin(user_id_str: str) -> None:
    """Directly grant the 'Admin' role to a user in the shared test DB."""
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
            role = IdentityRole(
                id=uuid.uuid4(),
                name="Admin",
                normalized_name="ADMIN",
                tenant_id=None,
            )
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


async def _get_admin_token(client: AsyncClient, tag: str) -> tuple[str, str]:
    """Register a user, grant Admin role, re-login, return (user_id, token)."""
    email = f"admin_{tag}_{uuid.uuid4().hex[:6]}@test.com"
    username = f"admin_{tag}_{uuid.uuid4().hex[:6]}"

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
    assert login1.status_code == 200, login1.text

    await _make_admin(user_id)

    # Re-login to get a token that includes the Admin role
    login2 = await client.post("/api/auth/login", json={
        "username_or_email": email,
        "password": _PASSWORD,
    })
    assert login2.status_code == 200, login2.text
    token = login2.json().get("access_token") or login2.json().get("token")
    assert token
    return user_id, token


# ═══════════════════════════════════════════════════════════════════════════
# PUT /api/users/me
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_update_my_profile_unauthenticated(client: AsyncClient):
    resp = await client.put("/api/users/me", json={"first_name": "Alice"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_my_profile_success(client: AsyncClient):
    _, token = await _register_and_login(client, "updme")
    resp = await client.put(
        "/api/users/me",
        json={"first_name": "Alice", "last_name": "Smith", "phone_number": "+1234567890"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["first_name"] == "Alice"
    assert data["last_name"] == "Smith"


@pytest.mark.asyncio
async def test_update_my_profile_partial(client: AsyncClient):
    """Only supplied fields should be updated."""
    _, token = await _register_and_login(client, "partial")
    resp = await client.put(
        "/api/users/me",
        json={"first_name": "Bob"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["first_name"] == "Bob"


@pytest.mark.asyncio
async def test_update_my_profile_empty_body(client: AsyncClient):
    """Empty body is valid (no-op update)."""
    _, token = await _register_and_login(client, "emptybody")
    resp = await client.put(
        "/api/users/me",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/users/me/avatar
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_upload_avatar_unauthenticated(client: AsyncClient):
    resp = await client.post(
        "/api/users/me/avatar",
        files={"file": ("avatar.png", b"\x89PNG\r\n", "image/png")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_avatar_invalid_mime_type(client: AsyncClient):
    _, token = await _register_and_login(client, "avbadmime")
    resp = await client.post(
        "/api/users/me/avatar",
        files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_avatar_success(client: AsyncClient):
    _, token = await _register_and_login(client, "avok")
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    with patch("app.infrastructure.storage.StorageService.save_file", new_callable=AsyncMock) as mock_save:
        mock_save.return_value = {"url": "https://storage.test/avatars/test.png"}
        resp = await client.post(
            "/api/users/me/avatar",
            files={"file": ("avatar.png", io.BytesIO(fake_png), "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "profile_picture_url" in data or "id" in data  # returns UserResponse


@pytest.mark.asyncio
async def test_upload_avatar_too_large(client: AsyncClient):
    _, token = await _register_and_login(client, "avlarge")
    # Create a file slightly over the 5 MB limit
    big_content = b"\x89PNG\r\n" + b"\x00" * (5 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/users/me/avatar",
        files={"file": ("big.png", io.BytesIO(big_content), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 413


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/users/{user_id} — requires Admin
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_user_by_id_unauthenticated(client: AsyncClient):
    resp = await client.get(f"/api/users/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_user_by_id_non_admin_forbidden(client: AsyncClient):
    _, token = await _register_and_login(client, "getuid_nonadmin")
    resp = await client.get(
        f"/api/users/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_user_by_id_admin_success(client: AsyncClient):
    target_uid, _ = await _register_and_login(client, "getuid_target")
    admin_uid, admin_token = await _get_admin_token(client, "getuid_admin")

    resp = await client.get(
        f"/api/users/{target_uid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == target_uid


# ═══════════════════════════════════════════════════════════════════════════
# PUT /api/users/{user_id} — requires Admin
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_update_user_by_id_unauthenticated(client: AsyncClient):
    resp = await client.put(f"/api/users/{uuid.uuid4()}", json={"first_name": "X"})
    assert resp.status_code in (401, 422)  # 422 if schema validation fires first


@pytest.mark.asyncio
async def test_update_user_by_id_non_admin_forbidden(client: AsyncClient):
    _, token = await _register_and_login(client, "putuid_nonadmin")
    target_uid, _ = await _register_and_login(client, "putuid_target")
    resp = await client.put(
        f"/api/users/{target_uid}",
        json={"first_name": "Hacker"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_user_by_id_admin_success(client: AsyncClient):
    target_uid, _ = await _register_and_login(client, "putuid_target2")
    _, admin_token = await _get_admin_token(client, "putuid_admin")

    resp = await client.put(
        f"/api/users/{target_uid}",
        json={"first_name": "AdminSet"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["first_name"] == "AdminSet"
