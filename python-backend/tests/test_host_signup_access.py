"""People who sign up on the platform itself (no tenant) are host-level accounts.
They must not reach the AI agent, host-wide audit data or anyone else's Cloud Setup."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.infrastructure.database as _db_module
from app.core.security import create_access_token, hash_password
from app.domain.models.identity import IdentityRole, IdentityUser, IdentityUserRole
from app.services.auth_service import AuthService


async def _host_headers(role_name: str) -> dict:
    """Bearer headers for a new host-level user holding `role_name`."""
    tag = uuid.uuid4().hex[:8]
    async with _db_module.AsyncSessionLocal() as session:
        role = (await session.execute(
            select(IdentityRole).where(
                IdentityRole.normalized_name == role_name.upper(),
                IdentityRole.tenant_id.is_(None),
            )
        )).scalar_one_or_none()
        if not role:
            role = IdentityRole(id=uuid.uuid4(), name=role_name, normalized_name=role_name.upper(), tenant_id=None)
            session.add(role)
            await session.flush()
        user = IdentityUser(
            id=uuid.uuid4(), tenant_id=None,
            user_name=f"signup_{tag}", normalized_user_name=f"SIGNUP_{tag}",
            email=f"signup-{tag}@example.com", normalized_email=f"SIGNUP-{tag}@EXAMPLE.COM",
            password_hash=hash_password("TestPass123!"), email_confirmed=True, is_active=True,
            security_stamp="test-stamp",
        )
        session.add(user)
        await session.flush()
        session.add(IdentityUserRole(user_id=user.id, role_id=role.id))
        await session.commit()
        token = create_access_token({
            "sub": str(user.id), "email": user.email, "username": user.user_name,
            "roles": [role_name], "sec": user.security_stamp,
        })
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
@pytest.mark.parametrize("role_name", ["User", "Deployer"])
async def test_signups_cannot_use_the_ai_agent(client: AsyncClient, role_name: str):
    headers = await _host_headers(role_name)
    for path in ("/api/aiagent/configurations", "/api/aiagent/source-control-config", "/api/aiagent/queue"):
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 403, f"{role_name} {path}: {resp.status_code}"


@pytest.mark.asyncio
async def test_admin_still_uses_the_ai_agent(client: AsyncClient):
    resp = await client.get("/api/aiagent/configurations", headers=await _host_headers("Admin"))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_only_deployers_get_cloud_setup(client: AsyncClient):
    user = await client.get("/api/cloudsetup/progress", headers=await _host_headers("User"))
    deployer = await client.get("/api/cloudsetup/progress", headers=await _host_headers("Deployer"))
    assert user.status_code == 403
    assert deployer.status_code == 200


@pytest.mark.asyncio
async def test_deployers_each_get_their_own_cloud_setup_session(client: AsyncClient):
    first, second = await _host_headers("Deployer"), await _host_headers("Deployer")
    await client.put("/api/cloudsetup/step/3", json={"data": {"note": "first"}}, headers=first)
    a = (await client.get("/api/cloudsetup/progress", headers=first)).json()
    b = (await client.get("/api/cloudsetup/progress", headers=second)).json()
    assert a["setup_id"] != b["setup_id"]
    assert a["current_step"] == 3
    assert b["current_step"] == 1


@pytest.mark.asyncio
async def test_signups_see_no_host_wide_audit_or_activity(client: AsyncClient):
    headers = await _host_headers("Deployer")
    assert (await client.get("/api/audit-logs", headers=headers)).status_code == 403
    assert (await client.get("/api/dashboard/activity", headers=headers)).json() == []
    assert (await client.get("/api/dashboard/stats", headers=headers)).json() == {}


class _Settings:
    def __init__(self, cloud_setup: bool):
        self.signups_get_cloud_setup = cloud_setup
        self.allow_registration = True
        self.restricted_email_domains_enabled = False
        self.allowed_email_domains = []
        self.password_min_length = None
        self.password_require_digit = None
        self.password_require_lowercase = None
        self.password_require_uppercase = None
        self.password_require_special = None
        self.require_email_confirmation = False
        self.new_users_active_by_default = True


@pytest.mark.asyncio
@pytest.mark.parametrize("cloud_setup,expected", [(True, "Deployer"), (False, "User")])
async def test_signup_role_follows_the_setting(db, cloud_setup: bool, expected: str):
    from app.data_seeder import seed_roles
    await seed_roles(db)
    email = f"role{uuid.uuid4().hex[:8]}@example.com"
    await AuthService(db, host_settings=_Settings(cloud_setup)).register(email=email, password="TestPass123!")
    user = (await db.execute(select(IdentityUser).where(IdentityUser.email == email))).scalar_one()
    roles = (await db.execute(
        select(IdentityRole.name).join(IdentityUserRole, IdentityUserRole.role_id == IdentityRole.id)
        .where(IdentityUserRole.user_id == user.id)
    )).scalars().all()
    assert roles == [expected]
