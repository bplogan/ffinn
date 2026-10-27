"""Tests for staging demo tenant seeder and monitoring endpoints."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Roles
from app.data_seeder import seed_roles, seed_subscription_plans
from app.domain.models.identity import IdentityUser
from app.domain.models.projects import Project
from app.domain.models.tenant import Tenant
from app.staging_demo_seeder import (
    demo_email_for_role,
    ensure_staging_tenant,
    list_staging_demo_accounts,
    repair_staging_demo_users_if_missing,
    seed_staging_demo,
    should_seed_staging_demo,
)


@pytest.fixture
def enable_staging_demo(monkeypatch):
    monkeypatch.setattr("app.staging_demo_seeder.settings.seed_staging_demo", True)
    monkeypatch.setattr("app.staging_demo_seeder.settings.environment", "test")
    yield


def test_should_seed_staging_demo_respects_flag(enable_staging_demo):
    assert should_seed_staging_demo() is True


def test_should_seed_staging_demo_staging_environment(monkeypatch):
    monkeypatch.setattr("app.staging_demo_seeder.settings.seed_staging_demo", False)
    monkeypatch.setattr("app.staging_demo_seeder.settings.environment", "staging")
    assert should_seed_staging_demo() is True


def test_should_seed_staging_demo_off_by_default(monkeypatch):
    monkeypatch.setattr("app.staging_demo_seeder.settings.seed_staging_demo", False)
    monkeypatch.setattr("app.staging_demo_seeder.settings.environment", "production")
    assert should_seed_staging_demo() is False


@pytest.mark.asyncio
async def test_repair_staging_demo_users_if_missing(db: AsyncSession, enable_staging_demo):
    await seed_roles(db)
    await seed_subscription_plans(db)

    tenant = await ensure_staging_tenant(db)
    await db.commit()

    accounts = await repair_staging_demo_users_if_missing(db)
    assert len(accounts) == len(Roles.DEFAULT_ROLE_PERMISSIONS)

    second = await repair_staging_demo_users_if_missing(db)
    assert second == []


@pytest.mark.asyncio
async def test_seed_staging_demo_creates_tenant_and_role_users(db: AsyncSession, enable_staging_demo):
    await seed_roles(db)
    await seed_subscription_plans(db)

    accounts = await seed_staging_demo(db)

    expected_roles = set(Roles.DEFAULT_ROLE_PERMISSIONS.keys())
    assert len(accounts) == len(expected_roles)
    assert {a["role"] for a in accounts} == expected_roles

    tenant = (
        await db.execute(select(Tenant).where(Tenant.normalized_name == "staging"))
    ).scalar_one()
    assert tenant.is_active is True

    for role_name in expected_roles:
        email = demo_email_for_role(role_name)
        user = (
            await db.execute(
                select(IdentityUser).where(
                    IdentityUser.tenant_id == tenant.id,
                    IdentityUser.normalized_email == email.upper(),
                )
            )
        ).scalar_one()
        assert user.email_confirmed is True
        assert user.is_active is True


@pytest.mark.asyncio
async def test_seed_staging_demo_is_idempotent(db: AsyncSession, enable_staging_demo):
    await seed_roles(db)
    await seed_subscription_plans(db)

    first = await seed_staging_demo(db)
    second = await seed_staging_demo(db)

    assert len(first) == len(second)
    projects = (
        await db.execute(select(Project).where(Project.tenant_id.is_not(None)))
    ).scalars().all()
    assert len(projects) == 5


@pytest.mark.asyncio
async def test_list_staging_demo_accounts(db: AsyncSession, enable_staging_demo):
    await seed_roles(db)
    await seed_subscription_plans(db)
    await seed_staging_demo(db)

    info = await list_staging_demo_accounts(db)
    assert info["tenant_name"] == "staging"
    assert len(info["accounts"]) == len(Roles.DEFAULT_ROLE_PERMISSIONS)
    assert all("@" in a["email"] for a in info["accounts"])


@pytest.mark.asyncio
async def test_staging_demo_accounts_endpoint_requires_admin(
    client: AsyncClient, enable_staging_demo, monkeypatch
):
    monkeypatch.setattr(
        "app.staging_demo_seeder.should_seed_staging_demo", lambda: True
    )
    resp = await client.get("/api/monitoring/staging-demo-accounts")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_seed_staging_demo_endpoint_requires_callback_token(
    client: AsyncClient, enable_staging_demo, monkeypatch
):
    monkeypatch.setattr(
        "app.staging_demo_seeder.should_seed_staging_demo", lambda: True
    )
    with patch("app.core.dependencies.settings") as mock_settings:
        mock_settings.callback_token = "expected-token"
        resp = await client.post("/api/monitoring/seed-staging-demo")
    assert resp.status_code == 403
