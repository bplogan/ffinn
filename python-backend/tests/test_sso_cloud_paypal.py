"""Tests for SSO, cloud setup wizard, and PayPal helpers."""
from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, encrypt_value, hash_password
from app.domain.models.identity import IdentityRole, IdentityUser, IdentityUserRole, SsoConfiguration
from app.domain.models.subscription import PaypalProcessedEvent
from app.domain.models.tenant import Tenant
from app.services.cloud_setup_service import CloudSetupService
from app.services.paypal_service import PayPalService


async def _seed_host_admin(db: AsyncSession, tag: str) -> tuple[IdentityUser, str]:
    from sqlalchemy import select

    role = (
        await db.execute(
            select(IdentityRole).where(
                IdentityRole.normalized_name == "ADMIN",
                IdentityRole.tenant_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not role:
        role = IdentityRole(
            id=uuid.uuid4(),
            name="Admin",
            normalized_name="ADMIN",
            tenant_id=None,
            is_system=True,
        )
        db.add(role)
        await db.flush()

    user = IdentityUser(
        id=uuid.uuid4(),
        tenant_id=None,
        user_name=f"hostadmin-{tag}",
        normalized_user_name=f"HOSTADMIN-{tag}".upper(),
        email=f"host-{tag}@test.com",
        normalized_email=f"HOST-{tag}@TEST.COM",
        password_hash=hash_password("Password123!"),
        email_confirmed=True,
        is_active=True,
        security_stamp="test-stamp",
    )
    db.add(user)
    await db.flush()
    db.add(IdentityUserRole(user_id=user.id, role_id=role.id))
    await db.commit()

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "username": user.user_name,
        "roles": ["Admin"],
        "permissions": ["System.Admin"],
        "sec": user.security_stamp,
    })
    return user, token


async def _seed_tenant_admin(db: AsyncSession, tag: str) -> tuple[Tenant, IdentityUser, str]:
    tenant = Tenant(
        id=uuid.uuid4(),
        name=f"SSO Tenant {tag}",
        normalized_name=f"sso-{tag}".lower(),
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
        user_name=f"ssoadmin-{tag}",
        normalized_user_name=f"SSOADMIN-{tag}".upper(),
        email=f"sso-{tag}@test.com",
        normalized_email=f"SSO-{tag}@TEST.COM",
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
        "permissions": ["Settings.Security"],
    })
    return tenant, user, token


@pytest.mark.asyncio
async def test_sso_tenant_providers_public(client: AsyncClient, db: AsyncSession):
    tenant, _, _ = await _seed_tenant_admin(db, "public")
    config = SsoConfiguration(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        provider="OIDC",
        provider_name="google",
        client_id="cid",
        client_secret=encrypt_value("secret"),
        metadata_url="https://accounts.google.com",
        is_enabled=True,
    )
    db.add(config)
    await db.commit()

    resp = await client.get(f"/api/sso/tenant/{tenant.name}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_name"] == tenant.name
    assert len(data["providers"]) == 1
    assert data["providers"][0]["provider_name"] == "google"


@pytest.mark.asyncio
async def test_sso_crud_requires_auth(client: AsyncClient, db: AsyncSession):
    tenant, _, token = await _seed_tenant_admin(db, "crud")

    create = await client.post(
        "/api/sso",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "OIDC",
            "provider_name": "microsoft",
            "client_id": "ms-client",
            "client_secret": "ms-secret",
            "metadata_url": "https://login.microsoftonline.com/common/v2.0",
            "is_enabled": True,
        },
    )
    assert create.status_code == 201
    config_id = create.json()["id"]

    listing = await client.get("/api/sso", headers={"Authorization": f"Bearer {token}"})
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    test_url = await client.get(f"/api/sso/{config_id}/test", headers={"Authorization": f"Bearer {token}"})
    assert test_url.status_code == 200
    assert f"/api/sso/login/{config_id}" in test_url.json()["test_url"]

    delete = await client.delete(f"/api/sso/{config_id}", headers={"Authorization": f"Bearer {token}"})
    assert delete.status_code == 204


@pytest.mark.asyncio
async def test_external_providers_lists_sso(client: AsyncClient, db: AsyncSession):
    tenant, _, _ = await _seed_tenant_admin(db, "ext")
    config = SsoConfiguration(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        provider="OIDC",
        provider_name="google",
        client_id="cid",
        client_secret=encrypt_value("secret"),
        metadata_url="https://accounts.google.com",
        is_enabled=True,
    )
    db.add(config)
    await db.commit()

    resp = await client.get("/api/auth/external-providers", params={"tenant_name": tenant.name})
    assert resp.status_code == 200
    providers = resp.json()
    assert len(providers) == 1
    assert providers[0]["name"] == "google"


@pytest.mark.asyncio
async def test_cloud_setup_local_provider(client: AsyncClient, db: AsyncSession):
    _, token = await _seed_host_admin(db, "cloud")

    start = await client.post("/api/cloudsetup/start", headers={"Authorization": f"Bearer {token}"})
    assert start.status_code == 200
    assert start.json()["status"] == "in_progress"

    auth = await client.post(
        "/api/cloudsetup/cloud/authenticate",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "local", "credentials": {}},
    )
    assert auth.status_code == 200
    assert auth.json()["cloud_authenticated"] is True

    prov = await client.post(
        "/api/cloudsetup/cloud/provision",
        headers={"Authorization": f"Bearer {token}"},
        json={"region": "eastus", "environment_name": "test"},
    )
    assert prov.status_code == 200

    status = await client.get(
        "/api/cloudsetup/cloud/provision/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status.status_code == 200
    assert status.json()["provisioned"] is True


@pytest.mark.asyncio
async def test_cloud_setup_service_local_validate():
    result = await CloudSetupService().validate_cloud_credentials("local", {})
    assert result["valid"] is True
    assert result["provider"] == "local"


@pytest.mark.asyncio
async def test_cloud_setup_service_gcp_validate_mocked():
    from unittest.mock import MagicMock, patch

    sa_json = json.dumps({
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "key-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
        "client_email": "sa@test-project.iam.gserviceaccount.com",
        "client_id": "123",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    })

    mock_project = MagicMock()
    with patch("google.oauth2.service_account.Credentials.from_service_account_info") as mock_creds, patch(
        "google.cloud.resourcemanager_v3.ProjectsClient"
    ) as mock_client_cls:
        mock_creds.return_value.refresh = MagicMock()
        mock_client_cls.return_value.get_project.return_value = mock_project

        result = await CloudSetupService().validate_cloud_credentials(
            "gcp",
            {"project_id": "test-project", "service_account_json": sa_json},
        )

    assert result["valid"] is True
    assert result["provider"] == "gcp"
    assert result["project_id"] == "test-project"
    assert result["credentials_encrypted"]


@pytest.mark.asyncio
async def test_cloud_setup_service_oci_validate_mocked():
    from unittest.mock import MagicMock, patch

    mock_user = MagicMock()
    mock_user.data.name = "test-user"
    mock_user.data.id = "ocid1.user.oc1..example"

    with patch("oci.identity.IdentityClient") as mock_client_cls:
        mock_client_cls.return_value.get_user.return_value = mock_user

        result = await CloudSetupService().validate_cloud_credentials(
            "oci",
            {
                "tenancy_ocid": "ocid1.tenancy.oc1..aaa",
                "user_ocid": "ocid1.user.oc1..bbb",
                "fingerprint": "aa:bb:cc:dd:ee:ff",
                "private_key": "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----",
                "region": "us-ashburn-1",
            },
        )

    assert result["valid"] is True
    assert result["provider"] == "oci"
    assert result["user_name"] == "test-user"
    assert result["credentials_encrypted"]


@pytest.mark.asyncio
async def test_cloud_setup_oci_provision(client: AsyncClient, db: AsyncSession):
    _, token = await _seed_host_admin(db, "oci")

    await client.post("/api/cloudsetup/start", headers={"Authorization": f"Bearer {token}"})

    auth = await client.post(
        "/api/cloudsetup/cloud/authenticate",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "local", "credentials": {}},
    )
    assert auth.status_code == 200

    # Switch provider context via authenticate with OCI mocked at service layer
    from unittest.mock import MagicMock, patch

    mock_user = MagicMock()
    mock_user.data.name = "oci-user"
    mock_user.data.id = "ocid1.user.oc1..bbb"

    with patch("oci.identity.IdentityClient") as mock_client_cls:
        mock_client_cls.return_value.get_user.return_value = mock_user
        auth_oci = await client.post(
            "/api/cloudsetup/cloud/authenticate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "oci",
                "credentials": {
                    "tenancy_ocid": "ocid1.tenancy.oc1..aaa",
                    "user_ocid": "ocid1.user.oc1..bbb",
                    "fingerprint": "aa:bb:cc:dd:ee:ff",
                    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----",
                },
            },
        )
    assert auth_oci.status_code == 200
    assert auth_oci.json()["cloud_provider"] == "oci"

    prov = await client.post(
        "/api/cloudsetup/cloud/provision",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "region": "us-ashburn-1",
            "environment_name": "test",
            "extra": {"compartment_ocid": "ocid1.compartment.oc1..ccc"},
        },
    )
    assert prov.status_code == 200


@pytest.mark.asyncio
async def test_cloud_setup_rejects_tenant_admin(client: AsyncClient, db: AsyncSession):
    _, _, token = await _seed_tenant_admin(db, "deny")

    start = await client.post("/api/cloudsetup/start", headers={"Authorization": f"Bearer {token}"})
    assert start.status_code == 403


@pytest.mark.asyncio
async def test_saml_email_extraction():
    from app.services.saml_login_service import SamlLoginService

    assert SamlLoginService._extract_email("user@example.com", {}) == "user@example.com"
    attrs = {"http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": ["saml@example.com"]}
    assert SamlLoginService._extract_email(None, attrs) == "saml@example.com"


@pytest.mark.asyncio
async def test_sso_saml_create(client: AsyncClient, db: AsyncSession):
    _, _, token = await _seed_tenant_admin(db, "samlcreate")
    create = await client.post(
        "/api/sso",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "SAML",
            "provider_name": "okta",
            "metadata_url": "https://idp.example.com/metadata",
            "is_enabled": True,
        },
    )
    assert create.status_code == 201
    assert create.json()["provider"] == "SAML"


@pytest.mark.asyncio
async def test_sso_saml_sp_metadata_mocked(client: AsyncClient, db: AsyncSession):
    from unittest.mock import AsyncMock, patch

    tenant, _, token = await _seed_tenant_admin(db, "samlmeta")
    config = SsoConfiguration(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        provider="SAML",
        provider_name="okta",
        metadata_url="https://idp.example.com/metadata",
        is_enabled=True,
    )
    db.add(config)
    await db.commit()

    with patch(
        "app.services.saml_login_service.SamlLoginService.get_sp_metadata",
        new=AsyncMock(return_value="<EntityDescriptor />"),
    ):
        resp = await client.get(f"/api/sso/sp/{config.id}")
    assert resp.status_code == 200
    assert "EntityDescriptor" in resp.text


@pytest.mark.asyncio
async def test_paypal_confirm_mocked(client: AsyncClient, db: AsyncSession):
    from unittest.mock import AsyncMock, patch

    _, user, token = await _seed_tenant_admin(db, "ppconfirm")
    with patch(
        "app.services.paypal_service.PayPalService.confirm_subscription",
        new=AsyncMock(return_value={"status": "active", "activated": True}),
    ):
        resp = await client.post(
            "/api/subscriptions/paypal/confirm?subscription_id=I-SUB123",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["activated"] is True


@pytest.mark.asyncio
async def test_paypal_webhook_idempotency(db: AsyncSession):
    svc = PayPalService(db)
    payload = json.dumps({"id": "evt-1", "event_type": "BILLING.SUBSCRIPTION.ACTIVATED", "resource": {}}).encode()
    await svc.handle_webhook(payload, {})
    await svc.handle_webhook(payload, {})

    from sqlalchemy import select

    rows = (await db.execute(select(PaypalProcessedEvent))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_paypal_api_base_sandbox():
    svc = PayPalService(None)  # type: ignore[arg-type]
    from app.core.config import settings

    original = settings.paypal_mode
    settings.paypal_mode = "sandbox"
    try:
        assert "sandbox" in svc._api_base()
    finally:
        settings.paypal_mode = original


@pytest.mark.asyncio
async def test_feature_flag_create_and_toggle(client: AsyncClient, db: AsyncSession):
    _, token = await _seed_host_admin(db, "flags")
    headers = {"Authorization": f"Bearer {token}"}
    name = f"custom_flag_{uuid.uuid4().hex[:8]}"

    create = await client.post(
        "/api/feature-flags",
        headers=headers,
        json={
            "name": name,
            "is_enabled": True,
            "description": "Custom flag for tests",
            "rollout_percentage": 100,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["name"] == name
    assert body["is_enabled"] is True
    assert body["description"] == "Custom flag for tests"

    dup = await client.post(
        "/api/feature-flags",
        headers=headers,
        json={"name": name, "is_enabled": False},
    )
    assert dup.status_code == 409

    update = await client.put(
        f"/api/feature-flags/{name}",
        headers=headers,
        json={"is_enabled": False},
    )
    assert update.status_code == 200
    assert update.json()["is_enabled"] is False
