"""Login without an organization name: tenant lookup, organization choice and 2FA responses."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.domain.models.identity import IdentityUser, TwoFactorAuth
from app.domain.models.tenant import Tenant

_PASSWORD = "TenantPass123!"


@pytest.fixture(autouse=True)
def no_rate_limit():
    with patch("app.core.security_middleware._ip_limiter.is_allowed", return_value=True):
        yield


async def _tenant(db, label: str) -> Tenant:
    name = f"{label} {uuid.uuid4().hex[:6]}"
    tenant = Tenant(id=uuid.uuid4(), name=name, normalized_name=name.lower(), is_active=True, is_available=True)
    db.add(tenant)
    await db.flush()
    return tenant


async def _user(db, email: str, tenant_id, password: str = _PASSWORD) -> IdentityUser:
    username = f"u_{uuid.uuid4().hex[:8]}"
    user = IdentityUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_name=username,
        normalized_user_name=username.upper(),
        email=email,
        normalized_email=email.upper(),
        email_confirmed=True,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


def _email() -> str:
    return f"member_{uuid.uuid4().hex[:8]}@example.com"


async def _login(client: AsyncClient, email: str, password: str = _PASSWORD, tenant_name: str | None = None):
    body = {"username_or_email": email, "password": password}
    if tenant_name:
        body["tenant_name"] = tenant_name
    return await client.post("/api/auth/login", json=body)


@pytest.mark.asyncio
async def test_tenant_user_signs_in_without_organization(client: AsyncClient, db):
    email = _email()
    tenant = await _tenant(db, "Acme")
    await _user(db, email, tenant.id)
    await db.commit()

    resp = await _login(client, email)
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_same_sign_in_in_two_organizations_asks_which(client: AsyncClient, db):
    email = _email()
    first, second = await _tenant(db, "Northwind"), await _tenant(db, "Bluebird")
    await _user(db, email, first.id)
    await _user(db, email, second.id)
    await db.commit()

    resp = await _login(client, email)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" not in body
    assert sorted(t["name"] for t in body["tenants"]) == sorted([first.name, second.name])

    chosen = await _login(client, email, tenant_name=second.name)
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["access_token"]


@pytest.mark.asyncio
async def test_only_the_organization_whose_password_matches_is_used(client: AsyncClient, db):
    email = _email()
    first, second = await _tenant(db, "Contoso"), await _tenant(db, "Fabrikam")
    await _user(db, email, first.id, password="SomethingElse456!")
    await _user(db, email, second.id)
    await db.commit()

    resp = await _login(client, email)
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_wrong_password_across_organizations_is_rejected(client: AsyncClient, db):
    email = _email()
    first, second = await _tenant(db, "Initech"), await _tenant(db, "Globex")
    a = await _user(db, email, first.id)
    b = await _user(db, email, second.id)
    await db.commit()

    resp = await _login(client, email, password="WrongPass999!")
    assert resp.status_code == 401
    await db.refresh(a)
    await db.refresh(b)
    assert a.access_failed_count == 1 and b.access_failed_count == 1


@pytest.mark.asyncio
async def test_inactive_organization_is_not_offered(client: AsyncClient, db):
    email = _email()
    active, inactive = await _tenant(db, "Umbrella"), await _tenant(db, "Closed")
    inactive.is_active = False
    await _user(db, email, active.id)
    await _user(db, email, inactive.id)
    await db.commit()

    resp = await _login(client, email)
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_two_factor_user_gets_challenge_not_server_error(client: AsyncClient, db):
    email = _email()
    tenant = await _tenant(db, "Stark")
    user = await _user(db, email, tenant.id)
    db.add(TwoFactorAuth(id=uuid.uuid4(), user_id=user.id, secret_key="x", is_enabled=True))
    await db.commit()

    resp = await _login(client, email, tenant_name=tenant.name)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requires_two_factor"] is True
    assert body["user_id"] == str(user.id)
    assert "access_token" not in body


@pytest.mark.asyncio
async def test_me_includes_the_organization_name(client: AsyncClient, db):
    email = _email()
    tenant = await _tenant(db, "Wayne")
    await _user(db, email, tenant.id)
    await db.commit()

    token = (await _login(client, email)).json()["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["tenantName"] == tenant.name
