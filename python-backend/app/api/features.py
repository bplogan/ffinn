"""
Features routes — mirrors FeaturesController.cs.

GET  /api/features              - all feature groups (tenant sees read-only)
GET  /api/features/{name}       - single feature
GET  /api/features/{name}/enabled - bool check
PUT  /api/features              - admin/host: update feature values
"""
from __future__ import annotations

from typing import Any, Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DBSession, get_current_user, CurrentUser
from app.core.exceptions import BusinessException
from app.services.misc_services import SettingsService

router = APIRouter(prefix="/api/features", tags=["Features"])

# ── Default feature catalogue (mirrors .NET GetDefaultFeatures) ───────────────
_DEFAULT_GROUPS: list[dict[str, Any]] = [
    {
        "name": "Application",
        "display_name": "Application Features",
        "features": [
            {
                "name": "App.EnableAuditLogging",
                "display_name": "Enable Audit Logging",
                "description": "When enabled, user actions are logged for auditing purposes.",
                "value_type": "boolean",
                "value": "true",
                "default_value": "true",
                "read_only": False,
            },
            {
                "name": "App.MaxUploadFileSize",
                "display_name": "Max Upload File Size (MB)",
                "description": "Maximum file size allowed for uploads in megabytes.",
                "value_type": "number",
                "value": "10",
                "default_value": "5",
                "read_only": False,
            },
            {
                "name": "App.EnableNotifications",
                "display_name": "Enable Notifications",
                "description": "When enabled, users receive in-app notifications.",
                "value_type": "boolean",
                "value": "true",
                "default_value": "true",
                "read_only": False,
            },
        ],
    },
    {
        "name": "Authentication",
        "display_name": "Authentication Features",
        "features": [
            {
                "name": "Auth.EnableTwoFactor",
                "display_name": "Enable Two-Factor Authentication",
                "description": "When enabled, users can set up two-factor authentication.",
                "value_type": "boolean",
                "value": "true",
                "default_value": "false",
                "read_only": False,
            },
            {
                "name": "Auth.EnableSocialLogin",
                "display_name": "Enable Social Login",
                "description": "When enabled, users can log in using social providers.",
                "value_type": "boolean",
                "value": "false",
                "default_value": "false",
                "read_only": False,
            },
            {
                "name": "Auth.EnableRegistration",
                "display_name": "Enable User Registration",
                "description": "When enabled, new users can register themselves.",
                "value_type": "boolean",
                "value": "true",
                "default_value": "true",
                "read_only": False,
            },
            {
                "name": "Auth.SessionTimeout",
                "display_name": "Session Timeout (minutes)",
                "description": "Number of minutes before an inactive session expires.",
                "value_type": "number",
                "value": "60",
                "default_value": "30",
                "read_only": False,
            },
        ],
    },
    {
        "name": "Tenant",
        "display_name": "Tenant Features",
        "features": [
            {
                "name": "Tenant.MaxUsers",
                "display_name": "Maximum Users",
                "description": "Maximum number of users allowed for a tenant.",
                "value_type": "number",
                "value": "100",
                "default_value": "10",
                "read_only": False,
            },
            {
                "name": "Tenant.EnableCustomBranding",
                "display_name": "Enable Custom Branding",
                "description": "When enabled, tenants can customize their branding.",
                "value_type": "boolean",
                "value": "true",
                "default_value": "false",
                "read_only": False,
            },
            {
                "name": "Tenant.StorageQuota",
                "display_name": "Storage Quota (GB)",
                "description": "Maximum storage space allowed for a tenant in gigabytes.",
                "value_type": "number",
                "value": "10",
                "default_value": "1",
                "read_only": False,
            },
        ],
    },
]


def _get_features_response(
    tenant_overrides: dict[str, str] | None,
    read_only: bool,
) -> dict[str, Any]:
    """Build the features response, applying optional tenant overrides."""
    import copy
    groups = copy.deepcopy(_DEFAULT_GROUPS)
    for group in groups:
        for feat in group["features"]:
            if tenant_overrides and feat["name"] in tenant_overrides:
                feat["value"] = tenant_overrides[feat["name"]]
            if read_only:
                feat["read_only"] = True
    return {"groups": groups}


def _all_features_flat(
    tenant_overrides: dict[str, str] | None,
    read_only: bool,
) -> list[dict[str, Any]]:
    resp = _get_features_response(tenant_overrides, read_only)
    return [f for g in resp["groups"] for f in g["features"]]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def get_features(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    """
    Return all feature groups.
    Tenant users receive a read-only view; host admins can see mutable values.
    """
    tenant_id = current_user.tenant_id
    tenant_overrides: dict[str, str] | None = None

    if tenant_id:
        # Load per-tenant feature overrides from AppSettings (key prefix "Features.")
        svc = SettingsService(db)
        rows = await svc.get_settings_by_prefix("Features.", tenant_id=tenant_id)
        if rows:
            tenant_overrides = {
                r.key.removeprefix("Features."): r.value for r in rows
            }

    return _get_features_response(
        tenant_overrides=tenant_overrides,
        read_only=bool(tenant_id),  # tenants are read-only
    )


@router.get("/{name}/enabled")
async def is_feature_enabled(
    name: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    """Return True/False whether the named boolean feature is enabled."""
    tenant_id = current_user.tenant_id
    tenant_overrides: dict[str, str] | None = None

    if tenant_id:
        svc = SettingsService(db)
        rows = await svc.get_settings_by_prefix("Features.", tenant_id=tenant_id)
        if rows:
            tenant_overrides = {r.key.removeprefix("Features."): r.value for r in rows}

    features = _all_features_flat(tenant_overrides, read_only=bool(tenant_id))
    feat = next((f for f in features if f["name"] == name), None)
    if feat is None:
        raise BusinessException("NOT_FOUND", f"Feature '{name}' not found.")

    enabled = feat["value_type"] == "boolean" and feat.get("value", "").lower() == "true"
    return enabled


@router.get("/{name}")
async def get_feature(
    name: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    """Return a single feature definition."""
    tenant_id = current_user.tenant_id
    tenant_overrides: dict[str, str] | None = None

    if tenant_id:
        svc = SettingsService(db)
        rows = await svc.get_settings_by_prefix("Features.", tenant_id=tenant_id)
        if rows:
            tenant_overrides = {r.key.removeprefix("Features."): r.value for r in rows}

    features = _all_features_flat(tenant_overrides, read_only=bool(tenant_id))
    feat = next((f for f in features if f["name"] == name), None)
    if feat is None:
        raise BusinessException("NOT_FOUND", f"Feature '{name}' not found.")
    return feat


@router.put("")
async def update_features(
    body: dict,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    """
    Update feature values.  Host admins only (mirrors .NET Features.Management policy).

    Body: { "provider_name": "H"|"T", "provider_key": "<tenant_id>|null",
            "features": {"App.EnableAuditLogging": "false", ...} }
    """
    if current_user.tenant_id is not None:
        raise BusinessException("FORBIDDEN", "Only host administrators can modify feature settings.")

    provider_name: str = body.get("provider_name", "H")
    provider_key: str | None = body.get("provider_key")
    features: dict[str, str] = body.get("features", {})

    if not features:
        return {"message": "No features provided."}

    import uuid as _uuid
    svc = SettingsService(db)

    if provider_name == "T" and provider_key:
        try:
            tenant_uuid = _uuid.UUID(provider_key)
        except ValueError:
            raise BusinessException("VALIDATION_ERROR", "provider_key must be a valid UUID for tenant features.")
        for feat_name, value in features.items():
            await svc.set_setting(f"Features.{feat_name}", value, tenant_id=tenant_uuid)
    else:
        # Host-level feature defaults (stored without tenant_id)
        for feat_name, value in features.items():
            await svc.set_setting(f"Features.{feat_name}", value, tenant_id=None)

    return None  # 204-style
