"""
Tests for delegation ownership enforcement.
Covers:
  - GET  /api/delegations/{id}  — 403 for third-party users
  - PUT  /api/delegations/{id}  — 403 for non-owner (target or third-party)
  - DELETE /api/delegations/{id} — 403 for non-owner
  - Source user can GET/PUT/DELETE their own delegation
  - Target user can GET but not PUT/DELETE
  - Admin can access any delegation
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient
from unittest.mock import patch


# ── Disable rate-limiting ──────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def no_rate_limit():
    with patch("app.core.security_middleware._ip_limiter.is_allowed", return_value=True):
        yield


_PASSWORD = "TestPass123!"

_START = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
_END   = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()


async def _register_and_login(client: AsyncClient, tag: str) -> tuple[str, str]:
    """Register a unique user and return (user_id, access_token)."""
    email = f"deleg_{tag}_{uuid.uuid4().hex[:6]}@test.com"
    username = f"deleg_{tag}_{uuid.uuid4().hex[:6]}"

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


async def _get_admin_token(client: AsyncClient, tag: str) -> tuple[str, str]:
    email = f"dadmin_{tag}_{uuid.uuid4().hex[:6]}@test.com"
    username = f"dadmin_{tag}_{uuid.uuid4().hex[:6]}"

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
    token = login2.json().get("access_token") or login2.json().get("token")
    return user_id, token


async def _create_delegation(client: AsyncClient, source_token: str, target_id: str) -> str:
    """Create a delegation from source user to target user, return delegation ID."""
    resp = await client.post(
        "/api/delegations",
        json={"target_user_id": target_id, "start_time": _START, "end_time": _END},
        headers={"Authorization": f"Bearer {source_token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ═══════════════════════════════════════════════════════════════════════════
# Unauthenticated access
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_delegation_unauthenticated(client: AsyncClient):
    resp = await client.get(f"/api/delegations/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_put_delegation_unauthenticated(client: AsyncClient):
    resp = await client.put(
        f"/api/delegations/{uuid.uuid4()}",
        json={"end_time": _END},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_delegation_unauthenticated(client: AsyncClient):
    resp = await client.delete(f"/api/delegations/{uuid.uuid4()}")
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Third-party user (neither source nor target) — must get 403
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_delegation_third_party_forbidden(client: AsyncClient):
    source_id, source_token = await _register_and_login(client, "get3p_src")
    target_id, _ = await _register_and_login(client, "get3p_tgt")
    _, third_token = await _register_and_login(client, "get3p_3rd")

    delegation_id = await _create_delegation(client, source_token, target_id)

    resp = await client.get(
        f"/api/delegations/{delegation_id}",
        headers={"Authorization": f"Bearer {third_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_put_delegation_third_party_forbidden(client: AsyncClient):
    source_id, source_token = await _register_and_login(client, "put3p_src")
    target_id, _ = await _register_and_login(client, "put3p_tgt")
    _, third_token = await _register_and_login(client, "put3p_3rd")

    delegation_id = await _create_delegation(client, source_token, target_id)

    resp = await client.put(
        f"/api/delegations/{delegation_id}",
        json={"end_time": _END},
        headers={"Authorization": f"Bearer {third_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_delegation_third_party_forbidden(client: AsyncClient):
    source_id, source_token = await _register_and_login(client, "del3p_src")
    target_id, _ = await _register_and_login(client, "del3p_tgt")
    _, third_token = await _register_and_login(client, "del3p_3rd")

    delegation_id = await _create_delegation(client, source_token, target_id)

    resp = await client.delete(
        f"/api/delegations/{delegation_id}",
        headers={"Authorization": f"Bearer {third_token}"},
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Target user — can GET, but NOT PUT/DELETE
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_delegation_target_user_allowed(client: AsyncClient):
    source_id, source_token = await _register_and_login(client, "gettgt_src")
    target_id, target_token = await _register_and_login(client, "gettgt_tgt")

    delegation_id = await _create_delegation(client, source_token, target_id)

    resp = await client.get(
        f"/api/delegations/{delegation_id}",
        headers={"Authorization": f"Bearer {target_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == delegation_id


@pytest.mark.asyncio
async def test_put_delegation_target_user_forbidden(client: AsyncClient):
    source_id, source_token = await _register_and_login(client, "puttgt_src")
    target_id, target_token = await _register_and_login(client, "puttgt_tgt")

    delegation_id = await _create_delegation(client, source_token, target_id)

    resp = await client.put(
        f"/api/delegations/{delegation_id}",
        json={"end_time": _END},
        headers={"Authorization": f"Bearer {target_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_delegation_target_user_forbidden(client: AsyncClient):
    source_id, source_token = await _register_and_login(client, "deltgt_src")
    target_id, target_token = await _register_and_login(client, "deltgt_tgt")

    delegation_id = await _create_delegation(client, source_token, target_id)

    resp = await client.delete(
        f"/api/delegations/{delegation_id}",
        headers={"Authorization": f"Bearer {target_token}"},
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Source user (owner) — can GET/PUT/DELETE
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_source_user_can_get_delegation(client: AsyncClient):
    source_id, source_token = await _register_and_login(client, "src_get")
    target_id, _ = await _register_and_login(client, "src_get_tgt")

    delegation_id = await _create_delegation(client, source_token, target_id)

    resp = await client.get(
        f"/api/delegations/{delegation_id}",
        headers={"Authorization": f"Bearer {source_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == delegation_id


@pytest.mark.asyncio
async def test_source_user_can_update_delegation(client: AsyncClient):
    source_id, source_token = await _register_and_login(client, "src_put")
    target_id, _ = await _register_and_login(client, "src_put_tgt")

    delegation_id = await _create_delegation(client, source_token, target_id)
    new_end = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()

    resp = await client.put(
        f"/api/delegations/{delegation_id}",
        json={"end_time": new_end},
        headers={"Authorization": f"Bearer {source_token}"},
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_source_user_can_delete_delegation(client: AsyncClient):
    source_id, source_token = await _register_and_login(client, "src_del")
    target_id, _ = await _register_and_login(client, "src_del_tgt")

    delegation_id = await _create_delegation(client, source_token, target_id)

    resp = await client.delete(
        f"/api/delegations/{delegation_id}",
        headers={"Authorization": f"Bearer {source_token}"},
    )
    assert resp.status_code == 204


# ═══════════════════════════════════════════════════════════════════════════
# Admin — can access any delegation
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_admin_can_get_any_delegation(client: AsyncClient):
    source_id, source_token = await _register_and_login(client, "adm_get_src")
    target_id, _ = await _register_and_login(client, "adm_get_tgt")
    _, admin_token = await _get_admin_token(client, "adm_get")

    delegation_id = await _create_delegation(client, source_token, target_id)

    resp = await client.get(
        f"/api/delegations/{delegation_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == delegation_id


@pytest.mark.asyncio
async def test_admin_can_delete_any_delegation(client: AsyncClient):
    source_id, source_token = await _register_and_login(client, "adm_del_src")
    target_id, _ = await _register_and_login(client, "adm_del_tgt")
    _, admin_token = await _get_admin_token(client, "adm_del")

    delegation_id = await _create_delegation(client, source_token, target_id)

    resp = await client.delete(
        f"/api/delegations/{delegation_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204
