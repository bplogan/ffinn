"""Tenants, roles, subscription, settings, feature flags, team invitations, audit, dashboard routes."""
from __future__ import annotations
import math
import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from app.core.dependencies import DBSession, get_current_user, CurrentUser, AdminUser
from app.core.app_url import resolve_frontend_url
from app.core.security_middleware import build_rate_limit_dep
from app.schemas.common_schemas import (
    CreateTenantRequest, UpdateTenantRequest, TenantResponse,
    CreateRoleRequest, UpdateRoleRequest,
    CreateCheckoutRequest, SetSettingRequest,
    SetFeatureFlagRequest,
    SendInvitationRequest, SaveLayoutRequest,
)


# ────────────────────────────────────────────────────────────────────────────
# Tenants
# ────────────────────────────────────────────────────────────────────────────
tenants_router = APIRouter(prefix="/api/tenants", tags=["Tenants"])


@tenants_router.get("")
async def list_tenants(
    db: DBSession, _: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    filter_q: Optional[str] = Query(None, alias="filter"),
):
    from app.services.tenant_service import TenantService
    svc = TenantService(db)
    term = search or filter_q
    items, total = await svc.get_tenants(page, page_size, term)
    return {
        "items": [TenantResponse.model_validate(t).model_dump(by_alias=True, mode="json") for t in items],
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


@tenants_router.get("/by-name/{name}")
async def get_tenant_by_name(name: str, db: DBSession):
    """Public — resolve a tenant by its subdomain/name for login UI."""
    from app.services.tenant_service import TenantService
    tenant = await TenantService(db).get_by_name(name)
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"id": str(tenant.id), "name": tenant.name, "logo_url": tenant.logo_url}


@tenants_router.post("", status_code=201)
async def create_tenant(body: CreateTenantRequest, db: DBSession, _: AdminUser):
    from app.services.tenant_service import TenantService

    tenant = await TenantService(db).create_tenant(
        name=body.name,
        tenancy_name=body.tenancy_name,
        connection_string=body.connection_string,
        admin_email=str(body.admin_email),
        admin_password=body.admin_password,
        admin_first_name="Admin",
        admin_last_name=body.name,
    )

    return TenantResponse.model_validate(tenant).model_dump(by_alias=True, mode="json")


@tenants_router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, db: DBSession, _: AdminUser):
    from app.services.tenant_service import TenantService
    tenant = await TenantService(db).get_tenant(uuid.UUID(tenant_id))
    return TenantResponse.model_validate(tenant).model_dump(by_alias=True, mode="json")


@tenants_router.put("/{tenant_id}")
async def update_tenant(tenant_id: str, body: UpdateTenantRequest, db: DBSession, _: AdminUser):
    from app.services.tenant_service import TenantService
    tenant = await TenantService(db).update_tenant(uuid.UUID(tenant_id), **body.model_dump(exclude_none=True))
    return TenantResponse.model_validate(tenant).model_dump(by_alias=True, mode="json")


@tenants_router.put("/{tenant_id}/status")
async def set_tenant_status(
    tenant_id: str, db: DBSession, _: AdminUser, is_active: bool = Query(...)
):
    from app.services.tenant_service import TenantService
    tenant = await TenantService(db).toggle_status(uuid.UUID(tenant_id), is_active)
    return TenantResponse.model_validate(tenant).model_dump(by_alias=True, mode="json")


@tenants_router.get("/{tenant_id}/users")
async def get_tenant_users(
    tenant_id: str, db: DBSession, _: AdminUser,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    filter: str | None = Query(None),
):
    import math
    from app.services.user_service import UserService
    from app.schemas.user_schemas import UserResponse

    tid = uuid.UUID(tenant_id)
    result = await UserService(db).get_users(
        tenant_id=tid,
        page=page,
        page_size=page_size,
        search=filter or None,
    )
    total = result["total"]
    return {
        "items": [UserResponse.model_validate(u) for u in result["items"]],
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


@tenants_router.get("/{tenant_id}/features")
async def get_tenant_features(tenant_id: str, db: DBSession, _: AdminUser):
    """Return feature-flag values scoped to a specific tenant."""
    from sqlalchemy import select as sa_select
    from app.domain.models.misc import FeatureFlag, FeatureValue
    flags = (await db.execute(sa_select(FeatureFlag).order_by(FeatureFlag.name))).scalars().all()
    values = (await db.execute(
        sa_select(FeatureValue).where(FeatureValue.tenant_id == uuid.UUID(tenant_id))
    )).scalars().all()
    value_map = {v.name: v.value for v in values}
    return [
        {
            "name": f.name,
            "is_enabled": value_map.get(f.name, str(f.is_enabled).lower()) in ("true", "True", True),
            "description": f.description,
        }
        for f in flags
    ]


@tenants_router.put("/{tenant_id}/features")
async def set_tenant_features(
    tenant_id: str,
    features: list[dict],
    db: DBSession,
    _: AdminUser,
):
    """Bulk-update feature-flag overrides for a specific tenant."""
    from sqlalchemy import select as sa_select
    from app.domain.models.misc import FeatureValue
    tid = uuid.UUID(tenant_id)
    for item in features:
        name = item.get("name")
        is_enabled = item.get("is_enabled", False)
        if not name:
            continue
        existing = (await db.execute(
            sa_select(FeatureValue).where(
                FeatureValue.name == name,
                FeatureValue.tenant_id == tid,
            )
        )).scalar_one_or_none()
        if existing:
            existing.value = str(is_enabled).lower()
        else:
            db.add(FeatureValue(
                id=uuid.uuid4(),
                name=name,
                tenant_id=tid,
                value=str(is_enabled).lower(),
                provider_name="Tenant",
            ))
    await db.commit()
    return {"message": "Tenant features updated."}


@tenants_router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(tenant_id: str, db: DBSession, _: AdminUser):
    from app.services.tenant_service import TenantService
    await TenantService(db).delete_tenant(uuid.UUID(tenant_id))


# ────────────────────────────────────────────────────────────────────────────
# Tenant self-registration (public)
# ────────────────────────────────────────────────────────────────────────────
tenant_registration_router = APIRouter(prefix="/api/tenant-registration", tags=["TenantRegistration"])


class TenantSelfRegisterRequest(BaseModel):
    tenant_name: str
    admin_email: str
    admin_password: str
    admin_first_name: Optional[str] = None
    admin_last_name: Optional[str] = None
    edition_id: Optional[uuid.UUID] = None


@tenant_registration_router.post("", status_code=201,
                                  dependencies=[Depends(build_rate_limit_dep(3, 60))])
async def register_tenant(body: TenantSelfRegisterRequest, db: DBSession):
    """Self-service tenant registration — creates tenant + admin user."""
    from app.services.auth_service import AuthService
    from app.services.host_settings import HostSettings
    from app.core.exceptions import BusinessException
    from app.core.config import settings
    if not settings.multi_tenancy_enabled:
        raise BusinessException("Multi-tenancy is disabled on this instance")
    hs = await HostSettings.load(db)
    if not hs.allow_tenant_registration:
        raise BusinessException("New tenant registration is currently disabled")
    if hs.paywall_enabled and body.edition_id is None:
        raise BusinessException("An edition must be selected before registering.")
    return await AuthService(db, host_settings=hs).register(
        username=body.admin_email.split("@")[0],
        email=body.admin_email,
        password=body.admin_password,
        first_name=body.admin_first_name,
        last_name=body.admin_last_name,
        tenant_name=body.tenant_name,
        edition_id=body.edition_id,
    )


# ────────────────────────────────────────────────────────────────────────────
# Roles
# ────────────────────────────────────────────────────────────────────────────
roles_router = APIRouter(prefix="/api/roles", tags=["Roles"])


@roles_router.get("")
async def list_roles(db: DBSession, current_user: AdminUser):
    from app.services.role_service import RoleService
    return await RoleService(db).get_roles(current_user.tenant_id)


@roles_router.post("", status_code=201)
async def create_role(body: CreateRoleRequest, db: DBSession, current_user: AdminUser):
    from app.services.role_service import RoleService
    return await RoleService(db).create_role(
        body.name, tenant_id=current_user.tenant_id, permissions=body.permissions
    )


@roles_router.get("/{role_id}")
async def get_role(role_id: str, db: DBSession, _: AdminUser):
    from app.services.role_service import RoleService
    return await RoleService(db).get_role(uuid.UUID(role_id))


@roles_router.put("/{role_id}")
async def update_role(role_id: str, body: UpdateRoleRequest, db: DBSession, _: AdminUser):
    from app.services.role_service import RoleService
    return await RoleService(db).update_role(uuid.UUID(role_id), body.name, body.permissions)


@roles_router.delete("/{role_id}", status_code=204)
async def delete_role(role_id: str, db: DBSession, _: AdminUser):
    from app.services.role_service import RoleService
    await RoleService(db).delete_role(uuid.UUID(role_id))


@roles_router.get("/{role_id}/permissions")
async def get_role_permissions(role_id: str, db: DBSession, _: AdminUser):
    from app.services.role_service import RoleService
    return await RoleService(db).get_role_permissions(uuid.UUID(role_id))


# ────────────────────────────────────────────────────────────────────────────
# Subscription Plans (CRUD)
# ────────────────────────────────────────────────────────────────────────────
subscription_plans_router = APIRouter(prefix="/api/subscription-plans", tags=["SubscriptionPlans"])


class CreateSubscriptionPlanRequest(BaseModel):
    name: str
    display_name: str
    price_monthly: float = 0
    price_annually: float = 0
    description: Optional[str] = None
    max_users: Optional[int] = None
    max_storage_gb: Optional[int] = None
    currency: str = "USD"
    sort_order: int = 0
    is_active: bool = True
    is_public: bool = True
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_annually: Optional[str] = None
    paypal_plan_id_monthly: Optional[str] = None
    paypal_plan_id_annually: Optional[str] = None


class UpdateSubscriptionPlanRequest(BaseModel):
    display_name: Optional[str] = None
    price_monthly: Optional[float] = None
    price_annually: Optional[float] = None
    description: Optional[str] = None
    max_users: Optional[int] = None
    max_storage_gb: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_annually: Optional[str] = None
    paypal_plan_id_monthly: Optional[str] = None
    paypal_plan_id_annually: Optional[str] = None


@subscription_plans_router.get("")
async def list_active_plans(db: DBSession):
    """Public — active, publicly available plans."""
    from app.services.misc_services import SubscriptionPlanService
    return await SubscriptionPlanService(db).get_active_plans()


@subscription_plans_router.get("/all")
async def list_all_plans(db: DBSession, _: AdminUser):
    from app.services.misc_services import SubscriptionPlanService
    return await SubscriptionPlanService(db).get_all_plans()


@subscription_plans_router.get("/{plan_id}")
async def get_plan(plan_id: uuid.UUID, db: DBSession):
    from app.services.misc_services import SubscriptionPlanService
    return await SubscriptionPlanService(db).get_plan(plan_id)


@subscription_plans_router.post("", status_code=201)
async def create_plan(body: CreateSubscriptionPlanRequest, db: DBSession, _: AdminUser):
    from app.services.misc_services import SubscriptionPlanService
    return await SubscriptionPlanService(db).create_plan(**body.model_dump())


@subscription_plans_router.put("/{plan_id}")
async def update_plan(plan_id: uuid.UUID, body: UpdateSubscriptionPlanRequest, db: DBSession, _: AdminUser):
    from app.services.misc_services import SubscriptionPlanService
    return await SubscriptionPlanService(db).update_plan(plan_id, **body.model_dump(exclude_none=True))


@subscription_plans_router.delete("/{plan_id}", status_code=204)
async def delete_plan(plan_id: uuid.UUID, db: DBSession, _: AdminUser):
    from app.services.misc_services import SubscriptionPlanService
    await SubscriptionPlanService(db).delete_plan(plan_id)


# ────────────────────────────────────────────────────────────────────────────
# Subscriptions
# ────────────────────────────────────────────────────────────────────────────
subscriptions_router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions"])


@subscriptions_router.get("/status")
async def subscription_status(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.services.stripe_service import StripeService
    from app.services.paypal_service import PayPalService

    status = await StripeService(db).get_subscription_status(current_user.tenant_id)
    if status:
        return status
    return await PayPalService(db).get_subscription_status(current_user.tenant_id) or {"status": "none"}


@subscriptions_router.get("/current")
async def subscription_current(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.services.stripe_service import StripeService
    from app.services.paypal_service import PayPalService

    status = await StripeService(db).get_subscription_status(current_user.tenant_id)
    if status:
        return status
    return await PayPalService(db).get_subscription_status(current_user.tenant_id) or {"status": "none"}


@subscriptions_router.post("/checkout")
async def create_checkout(
    body: CreateCheckoutRequest,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    provider = (body.payment_provider or "stripe").lower()
    if provider == "paypal":
        from app.services.paypal_service import PayPalService
        url = await PayPalService(db).create_subscription_checkout(
            current_user.tenant_id,
            current_user.id,
            uuid.UUID(body.plan_id),
            body.billing_cycle,
            body.success_url,
            body.cancel_url,
        )
    else:
        from app.services.stripe_service import StripeService
        url = await StripeService(db).create_checkout_session(
            current_user.tenant_id,
            current_user.id,
            uuid.UUID(body.plan_id),
            body.success_url,
            body.cancel_url,
            body.billing_cycle,
        )
    return {"checkout_url": url, "payment_provider": provider}


@subscriptions_router.post("/portal")
async def customer_portal(
    return_url: str,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from sqlalchemy import select
    from app.domain.models.subscription import EnhancedTenantSubscription
    from app.services.stripe_service import StripeService
    from app.services.paypal_service import PayPalService

    sub = (
        await db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.tenant_id == current_user.tenant_id,
                EnhancedTenantSubscription.status.in_(["active", "trialing", "past_due"]),
            ).order_by(EnhancedTenantSubscription.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if sub and sub.payment_provider == "paypal":
        url = await PayPalService(db).create_management_url(current_user.tenant_id)
    else:
        url = await StripeService(db).create_customer_portal_session(current_user.tenant_id, return_url)
    return {"portal_url": url}


@subscriptions_router.post("/cancel")
async def cancel_subscription(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.services.stripe_service import StripeService
    from app.services.paypal_service import PayPalService
    from sqlalchemy import select
    from app.domain.models.subscription import EnhancedTenantSubscription

    sub = (
        await db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.tenant_id == current_user.tenant_id,
                EnhancedTenantSubscription.status.in_(["active", "trialing"]),
            ).order_by(EnhancedTenantSubscription.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if sub and sub.payment_provider == "paypal":
        await PayPalService(db).cancel_subscription(current_user.tenant_id)
    else:
        await StripeService(db).cancel_subscription(current_user.tenant_id)
    return {"message": "Subscription will be cancelled at period end."}


@subscriptions_router.post("/reactivate")
async def reactivate_subscription(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from sqlalchemy import select
    from app.domain.models.subscription import EnhancedTenantSubscription
    from app.services.stripe_service import StripeService
    from app.services.paypal_service import PayPalService

    sub = (
        await db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.tenant_id == current_user.tenant_id,
                EnhancedTenantSubscription.status.in_(["active", "trialing", "past_due", "cancelled"]),
            ).order_by(EnhancedTenantSubscription.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if sub and sub.payment_provider == "paypal":
        await PayPalService(db).reactivate_subscription(current_user.tenant_id)
    else:
        await StripeService(db).reactivate_subscription(current_user.tenant_id)
    return {"message": "Subscription reactivated."}


@subscriptions_router.post("/paypal/confirm")
async def confirm_paypal_subscription(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    subscription_id: str = Query(..., min_length=1),
):
    """Confirm PayPal subscription after user returns from PayPal approval."""
    from app.services.paypal_service import PayPalService

    return await PayPalService(db).confirm_subscription(
        current_user.tenant_id, current_user.id, subscription_id
    )


class UpgradeRequest(BaseModel):
    plan_id: uuid.UUID
    billing_cycle: str = "monthly"


@subscriptions_router.post("/upgrade")
async def upgrade_subscription(
    body: UpgradeRequest,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from sqlalchemy import select
    from app.domain.models.subscription import EnhancedTenantSubscription
    from app.services.stripe_service import StripeService
    from app.core.exceptions import BusinessException

    sub = (
        await db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.tenant_id == current_user.tenant_id,
                EnhancedTenantSubscription.status.in_(["active", "trialing", "past_due"]),
            ).order_by(EnhancedTenantSubscription.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if sub and sub.payment_provider == "paypal":
        raise BusinessException("Plan changes for PayPal subscriptions must be done via PayPal.")
    await StripeService(db).upgrade_subscription(current_user.tenant_id, body.plan_id, body.billing_cycle)
    return {"message": "Subscription updated."}


@subscriptions_router.get("/invoices")
async def get_invoices(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
):
    from sqlalchemy import select
    from app.domain.models.subscription import EnhancedTenantSubscription
    from app.services.stripe_service import StripeService
    from app.services.paypal_service import PayPalService

    sub = (
        await db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.tenant_id == current_user.tenant_id,
            ).order_by(EnhancedTenantSubscription.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if sub and sub.payment_provider == "paypal":
        items, total = await PayPalService(db).get_billing_history(current_user.tenant_id, page, page_size)
    else:
        items, total = await StripeService(db).get_billing_history(current_user.tenant_id, page, page_size)
        items = [
            {
                "id": str(i.id),
                "amount": float(i.amount),
                "currency": i.currency,
                "status": i.status,
                "createdAt": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ]
    return {"items": items, "total_count": total}


@subscriptions_router.get("/billing-history")
async def billing_history(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
):
    return await get_invoices(db, current_user, page, page_size)


@subscriptions_router.get("/payment-methods")
async def list_payment_methods(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.services.stripe_service import StripeService
    return await StripeService(db).get_payment_methods(current_user.tenant_id)


class AddPaymentMethodRequest(BaseModel):
    payment_method_id: str


@subscriptions_router.post("/payment-methods")
async def add_payment_method(
    body: AddPaymentMethodRequest,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.services.stripe_service import StripeService
    await StripeService(db).add_payment_method(current_user.tenant_id, body.payment_method_id)
    return {"message": "Payment method added."}


@subscriptions_router.delete("/payment-methods/{pm_id}", status_code=204)
async def remove_payment_method(
    pm_id: str,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.services.stripe_service import StripeService
    await StripeService(db).remove_payment_method(current_user.tenant_id, pm_id)


@subscriptions_router.post("/payment-methods/{pm_id}/set-default")
async def set_default_payment_method(
    pm_id: str,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.services.stripe_service import StripeService
    await StripeService(db).set_default_payment_method(current_user.tenant_id, pm_id)
    return {"message": "Default payment method updated."}


@subscriptions_router.post("/paypal/webhook")
async def paypal_webhook(request: Request, db: DBSession):
    from app.services.paypal_service import PayPalService

    payload = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    await PayPalService(db).handle_webhook(payload, headers)
    return {"received": True}


@subscriptions_router.post("/webhook")
async def stripe_webhook(request: Request, db: DBSession):
    from app.services.stripe_service import StripeService
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    await StripeService(db).handle_webhook(payload, sig)
    return {"received": True}


# ────────────────────────────────────────────────────────────────────────────
# Settings
# ────────────────────────────────────────────────────────────────────────────
settings_router = APIRouter(prefix="/api/settings", tags=["Settings"])


@settings_router.get("/public")
async def get_public_settings(db: DBSession):
    """No auth — returns global public settings."""
    from app.services.misc_services import SettingsService
    return await SettingsService(db).get_public_settings()


@settings_router.get("/groups")
async def get_setting_groups(
    db: DBSession,
    _: AdminUser,
):
    from app.services.misc_services import SettingsService
    return await SettingsService(db).get_setting_groups(None)


@settings_router.get("/group/{prefix}")
async def get_settings_by_prefix(
    prefix: str,
    db: DBSession,
    _: AdminUser,
):
    from app.services.misc_services import SettingsService
    return await SettingsService(db).get_settings_by_prefix(prefix, None)


@settings_router.get("")
async def get_settings(
    db: DBSession,
    _: AdminUser,
):
    from app.services.misc_services import SettingsService
    return await SettingsService(db).get_all_settings(None)


@settings_router.get("/{key}")
async def get_setting(
    key: str,
    db: DBSession,
    _: AdminUser,
):
    from app.services.misc_services import SettingsService
    value = await SettingsService(db).get_setting(key, None)
    return {"key": key, "value": value}


@settings_router.post("")
async def set_setting(
    body: SetSettingRequest,
    db: DBSession,
    _: AdminUser,
):
    from app.services.misc_services import SettingsService
    await SettingsService(db).set_setting(body.key, body.value, None)
    return {"message": "Setting saved."}


class BulkSetSettingsRequest(BaseModel):
    settings: list[dict]


@settings_router.put("")
async def bulk_set_settings(
    body: BulkSetSettingsRequest,
    db: DBSession,
    _: AdminUser,
):
    from app.services.misc_services import SettingsService
    await SettingsService(db).bulk_set_settings(body.settings, None)
    # Invalidate HostSettings cache so next request picks up new values immediately
    from app.services.host_settings import HostSettings
    HostSettings.invalidate_cache()
    return {"message": f"{len(body.settings)} setting(s) saved."}


class TestEmailRequest(BaseModel):
    to: str


@settings_router.post("/test-email")
async def send_test_email(
    body: TestEmailRequest,
    db: DBSession,
    _: AdminUser,
):
    """Send a test email using the SMTP settings stored in app_settings."""
    from app.services.misc_services import SettingsService
    from app.infrastructure.email import EmailService
    from app.core.config import settings as cfg

    svc = SettingsService(db)
    host         = (await svc.get_setting("smtp.host"))         or cfg.smtp_host
    port         = int((await svc.get_setting("smtp.port"))     or cfg.smtp_port)
    use_ssl      = ((await svc.get_setting("smtp.use_ssl"))     or str(cfg.smtp_use_tls)).lower() == "true"
    username     = (await svc.get_setting("smtp.username"))     or cfg.smtp_username
    password     = (await svc.get_setting("smtp.password"))     or cfg.smtp_password
    from_address = (await svc.get_setting("smtp.from_address")) or cfg.smtp_from_address
    from_name    = (await svc.get_setting("smtp.from_name"))    or cfg.smtp_from_name

    email_svc = EmailService.from_config(
        host=host, port=port, use_ssl=use_ssl,
        username=username, password=password,
        from_address=from_address, from_name=from_name,
        app_url=cfg.app_url, app_name=cfg.app_name,
    )
    success = await email_svc.send_test(body.to)
    if not success:
        reason = email_svc.last_error or "Check the SMTP settings and try again."
        raise HTTPException(status_code=502, detail=f"Failed to send test email. {reason}")
    return {"message": f"Test email sent to {body.to}"}


@settings_router.delete("/{key}")
async def delete_setting(
    key: str,
    db: DBSession,
    _: AdminUser,
):
    from app.services.misc_services import SettingsService
    await SettingsService(db).delete_setting(key, None)
    return {"message": "Setting deleted."}


# ────────────────────────────────────────────────────────────────────────────
# Feature flags
# ────────────────────────────────────────────────────────────────────────────
feature_flags_router = APIRouter(prefix="/api/feature-flags", tags=["FeatureFlags"])


@feature_flags_router.get("/definitions")
async def list_definitions(db: DBSession, _: AdminUser):
    from app.services.misc_services import FeatureFlagService
    return await FeatureFlagService(db).get_definitions()


class CreateDefinitionRequest(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    value_type: str = "Boolean"
    default_value: Optional[str] = None


@feature_flags_router.post("/definitions", status_code=201)
async def create_definition(body: CreateDefinitionRequest, db: DBSession, _: AdminUser):
    from app.services.misc_services import FeatureFlagService
    return await FeatureFlagService(db).create_definition(**body.model_dump())


@feature_flags_router.get("")
async def list_flags(db: DBSession, _: AdminUser):
    from app.services.misc_services import FeatureFlagService
    return await FeatureFlagService(db).get_all_flags()


@feature_flags_router.post("", status_code=201)
async def create_flag(body: SetFeatureFlagRequest, db: DBSession, _: AdminUser):
    from app.services.misc_services import FeatureFlagService
    flag = await FeatureFlagService(db).create_flag(
        name=body.name,
        is_enabled=body.is_enabled,
        description=body.description,
        rollout_percentage=body.rollout_percentage,
    )
    return flag


@feature_flags_router.get("/{name}/enabled")
async def is_flag_enabled(name: str, db: DBSession, tenant_id: Optional[uuid.UUID] = Query(None)):
    """No auth — check if a feature flag is enabled."""
    from app.services.misc_services import FeatureFlagService
    enabled = await FeatureFlagService(db).is_enabled(name, tenant_id)
    return {"name": name, "is_enabled": enabled}


@feature_flags_router.get("/plans/{plan_id}")
async def get_plan_features(plan_id: uuid.UUID, db: DBSession, _: AdminUser):
    from app.services.misc_services import FeatureFlagService
    return await FeatureFlagService(db).get_plan_features(plan_id)


@feature_flags_router.put("/plans/{plan_id}")
async def set_plan_features(plan_id: uuid.UUID, features: list[dict], db: DBSession, _: AdminUser):
    from app.services.misc_services import FeatureFlagService
    await FeatureFlagService(db).set_plan_features(plan_id, features)
    return {"message": "Plan features updated."}


@feature_flags_router.get("/{name}")
async def get_flag(name: str, db: DBSession, _: AdminUser):
    from app.services.misc_services import FeatureFlagService
    return await FeatureFlagService(db).get_flag(name)


class UpdateFlagRequest(BaseModel):
    is_enabled: Optional[bool] = None
    description: Optional[str] = None
    rollout_percentage: Optional[int] = None


@feature_flags_router.put("/{name}")
async def update_flag(name: str, body: UpdateFlagRequest, db: DBSession, _: AdminUser):
    from app.services.misc_services import FeatureFlagService
    return await FeatureFlagService(db).update_flag(
        name,
        is_enabled=body.is_enabled,
        description=body.description,
        rollout_percentage=body.rollout_percentage,
    )


# ────────────────────────────────────────────────────────────────────────────
# Team invitations
# ────────────────────────────────────────────────────────────────────────────
invitations_router = APIRouter(prefix="/api/team-invitations", tags=["TeamInvitations"])


@invitations_router.get("/validate/{token}")
async def validate_invitation_token(token: str, db: DBSession):
    """Public — validate an invitation token and return pre-fill data."""
    from app.services.misc_services import TeamInvitationService
    return await TeamInvitationService(db).validate_token(token)


class AcceptInvitationRequest(BaseModel):
    token: str
    username: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


@invitations_router.post("/register")
async def register_from_invitation(body: AcceptInvitationRequest, db: DBSession):
    """Public — create a new account from an invitation."""
    from app.services.misc_services import TeamInvitationService
    return await TeamInvitationService(db).accept_publicly(
        token=body.token,
        username=body.username,
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
    )


@invitations_router.post("/accept")
async def accept_invitation(
    token: str,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Accept an invitation for an already-authenticated user."""
    from app.services.misc_services import TeamInvitationService
    await TeamInvitationService(db).accept_invitation(token, current_user.id)
    return {"message": "Invitation accepted."}


@invitations_router.get("")
async def list_invitations(
    db: DBSession,
    current_user: AdminUser,
):
    from app.services.misc_services import TeamInvitationService
    return await TeamInvitationService(db).get_pending_invitations(current_user.tenant_id)


@invitations_router.post("", status_code=201)
async def invite_user(
    body: SendInvitationRequest,
    request: Request,
    db: DBSession,
    current_user: AdminUser,
):
    from app.services.misc_services import TeamInvitationService
    inv = await TeamInvitationService(db).send_invitation(
        current_user.tenant_id,
        current_user.id,
        body.email,
        body.role_name,
        base_url=resolve_frontend_url(request),
    )
    return {"id": str(inv.id), "message": "Invitation sent."}


@invitations_router.get("/{invitation_id}")
async def get_invitation(
    invitation_id: uuid.UUID,
    db: DBSession,
    current_user: AdminUser,
):
    from app.services.misc_services import TeamInvitationService
    inv = await TeamInvitationService(db).get_invitation(invitation_id, current_user.tenant_id)
    return {
        "id": str(inv.id),
        "email": inv.email,
        "roleName": inv.role_name,
        "status": inv.status,
        "expiresAt": inv.expires_at.isoformat() if inv.expires_at else None,
        "createdAt": inv.created_at.isoformat() if inv.created_at else None,
    }


@invitations_router.post("/{invitation_id}/resend")
async def resend_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: AdminUser,
):
    from app.services.misc_services import TeamInvitationService
    await TeamInvitationService(db).resend_invitation(
        invitation_id,
        current_user.tenant_id,
        base_url=resolve_frontend_url(request),
    )
    return {"message": "Invitation resent."}


@invitations_router.post("/{invitation_id}/cancel")
async def cancel_invitation(
    invitation_id: uuid.UUID,
    db: DBSession,
    current_user: AdminUser,
):
    from app.services.misc_services import TeamInvitationService
    await TeamInvitationService(db).cancel_invitation(invitation_id, current_user.tenant_id)
    return {"message": "Invitation cancelled."}


@invitations_router.delete("/{invitation_id}", status_code=204)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    db: DBSession,
    current_user: AdminUser,
):
    from app.services.misc_services import TeamInvitationService
    await TeamInvitationService(db).revoke_invitation(invitation_id, current_user.tenant_id)


# ────────────────────────────────────────────────────────────────────────────
# Audit logs
# ────────────────────────────────────────────────────────────────────────────
audit_router = APIRouter(prefix="/api/audit-logs", tags=["AuditLogs"])


@audit_router.get("")
async def get_audit_logs(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    entity_type: Optional[str] = None,
    actor_id: Optional[uuid.UUID] = None,
):
    from app.services.misc_services import AuditLogService
    items, total = await AuditLogService(db).get_logs(
        tenant_id=current_user.tenant_id,
        actor_id=actor_id,
        page=page,
        page_size=page_size,
        entity_type=entity_type,
    )
    return {"items": items, "total_count": total}


@audit_router.get("/{log_id}")
async def get_audit_log(
    log_id: str,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Return a single audit log entry by ID."""
    from sqlalchemy import select as sa_select
    from app.domain.models.audit import AuditLog
    try:
        entry = (await db.execute(
            sa_select(AuditLog).where(AuditLog.id == uuid.UUID(log_id))
        )).scalar_one_or_none()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid log ID")
    if not entry:
        raise HTTPException(status_code=404, detail="Audit log not found")
    # Tenant filter for non-admins
    if not current_user.is_admin() and entry.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return entry


# ────────────────────────────────────────────────────────────────────────────
# Dashboard
# ────────────────────────────────────────────────────────────────────────────
dashboard_router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@dashboard_router.get("/stats")
async def get_stats(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.services.misc_services import DashboardService
    return await DashboardService(db).get_stats(current_user.tenant_id)


@dashboard_router.get("/activity")
async def get_activity(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = Query(20, ge=1, le=100),
):
    from app.services.misc_services import DashboardService
    return await DashboardService(db).get_activity(current_user.tenant_id, limit)


@dashboard_router.get("/layout")
async def get_layout(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.services.misc_services import DashboardService
    layout = await DashboardService(db).get_layout(current_user.id)
    return layout.layout_json if layout else {}


@dashboard_router.post("/layout")
async def save_layout(
    body: SaveLayoutRequest,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.services.misc_services import DashboardService
    await DashboardService(db).save_layout(current_user.id, body.layout)
    return {"message": "Layout saved."}


@dashboard_router.put("/layout")
async def update_layout(
    body: SaveLayoutRequest,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """PUT alias for save_layout — mirrors .NET DashboardController."""
    from app.services.misc_services import DashboardService
    await DashboardService(db).save_layout(current_user.id, body.layout)
    return {"message": "Layout saved."}


@dashboard_router.delete("/layout", status_code=204)
async def reset_layout(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.services.misc_services import DashboardService
    await DashboardService(db).reset_layout(current_user.id)

