"""Tests for tenant notification configuration API."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.notifications import NotificationConfiguration
from app.domain.models.tenant import Tenant
from app.services.notification_service import NotificationService
from app.schemas.notification_schemas import UpdateNotificationConfigInput


async def _seed_tenant_admin(db: AsyncSession, tag: str) -> tuple[Tenant, str]:
    from app.domain.models.identity import IdentityRole, IdentityUser, IdentityUserRole
    from app.core.security import hash_password, create_access_token

    tenant = Tenant(
        id=uuid.uuid4(),
        name=f"Notify Tenant {tag}",
        normalized_name=f"notify-{tag}".lower(),
        is_active=True,
    )
    db.add(tenant)
    await db.flush()

    role = IdentityRole(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Admin",
        normalized_name="ADMIN",
        is_system=True,
    )
    db.add(role)
    await db.flush()

    user = IdentityUser(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_name=f"notifyadmin-{tag}",
        normalized_user_name=f"NOTIFYADMIN-{tag}".upper(),
        email=f"notify-{tag}@test.com",
        normalized_email=f"NOTIFY-{tag}@TEST.COM",
        password_hash=hash_password("Password123!"),
        email_confirmed=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    db.add(IdentityUserRole(user_id=user.id, role_id=role.id))
    await db.commit()

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "username": user.user_name,
        "tenant_id": str(tenant.id),
        "roles": ["Admin"],
        "permissions": [],
    })
    return tenant, token


@pytest.mark.asyncio
async def test_get_config_creates_empty_defaults(client: AsyncClient, db: AsyncSession):
    _, token = await _seed_tenant_admin(db, "getcfg")
    resp = await client.get(
        "/api/notifications/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["smsEnabled"] is False
    assert data["pushEnabled"] is False
    assert data["hasTwilioAuthToken"] is False


@pytest.mark.asyncio
async def test_update_sms_config_encrypts_token(client: AsyncClient, db: AsyncSession):
    tenant, token = await _seed_tenant_admin(db, "smsupd")
    resp = await client.put(
        "/api/notifications/config",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "smsEnabled": True,
            "twilioAccountSid": "ACtest123",
            "twilioAuthToken": "secret-token",
            "twilioFromNumber": "+15551234567",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["smsEnabled"] is True
    assert body["hasTwilioAuthToken"] is True
    assert body["twilioAccountSid"] == "ACtest123"

    row = (
        await db.execute(
            select(NotificationConfiguration).where(
                NotificationConfiguration.tenant_id == tenant.id
            )
        )
    ).scalar_one()
    assert row.twilio_auth_token_encrypted is not None
    assert "secret-token" not in row.twilio_auth_token_encrypted


@pytest.mark.asyncio
async def test_update_firebase_push_config(client: AsyncClient, db: AsyncSession):
    _, token = await _seed_tenant_admin(db, "fbpush")
    creds = '{"type":"service_account","project_id":"demo"}'
    resp = await client.put(
        "/api/notifications/config",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "pushEnabled": True,
            "pushProvider": "firebase",
            "firebaseProjectId": "demo",
            "firebaseCredentialsJson": creds,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["pushProvider"] == "firebase"
    assert body["hasFirebaseCredentials"] is True


@pytest.mark.asyncio
async def test_sms_enabled_requires_credentials(client: AsyncClient, db: AsyncSession):
    _, token = await _seed_tenant_admin(db, "smsval")
    resp = await client.put(
        "/api/notifications/config",
        headers={"Authorization": f"Bearer {token}"},
        json={"smsEnabled": True},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_non_admin_forbidden(client: AsyncClient, db: AsyncSession):
    from app.domain.models.identity import IdentityUser
    from app.core.security import hash_password, create_access_token

    user = IdentityUser(
        id=uuid.uuid4(),
        tenant_id=None,
        user_name="regularuser",
        normalized_user_name="REGULARUSER",
        email="regular@test.com",
        normalized_email="REGULAR@TEST.COM",
        password_hash=hash_password("Password123!"),
        email_confirmed=True,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "username": user.user_name,
        "roles": ["User"],
        "permissions": [],
    })

    resp = await client.get(
        "/api/notifications/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_send_test_sms_mocked(client: AsyncClient, db: AsyncSession, monkeypatch):
    tenant, token = await _seed_tenant_admin(db, "smstest")
    svc = NotificationService(db)
    await svc.update_config(
        tenant.id,
        UpdateNotificationConfigInput(
            sms_enabled=True,
            twilio_account_sid="ACtest",
            twilio_auth_token="tok",
            twilio_from_number="+15551111111",
        ),
    )

    monkeypatch.setattr(
        "app.services.notification_service.send_twilio_sms",
        lambda **kwargs: "SM123",
    )

    resp = await client.post(
        "/api/notifications/test-sms",
        headers={"Authorization": f"Bearer {token}"},
        json={"to": "+15552222222"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["message_sid"] == "SM123"
