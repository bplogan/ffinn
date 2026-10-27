"""Tenant, subscription, role, and misc schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.alias_generators import to_camel


# ── Tenants ─────────────────────────────────────────────────────
class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: uuid.UUID
    name: str
    tenancy_name: str | None = Field(None, validation_alias="normalized_name")
    is_active: bool
    admin_email_address: str | None = None
    edition_id: uuid.UUID | None = None
    logo_url: str | None = None
    subscription_end_date: datetime | None = Field(None, validation_alias="subscription_end_date_utc")
    created_at: datetime | None = None


class CreateTenantRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str
    tenancy_name: str | None = None
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)
    connection_string: str | None = None
    edition_id: uuid.UUID | None = None


class UpdateTenantRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str | None = None
    is_active: bool | None = None
    edition_id: str | None = None


# ── Roles ─────────────────────────────────────────────────────────────────────

class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    permissions: list[str] = []


class CreateRoleRequest(BaseModel):
    name: str
    permissions: list[str] = []


class UpdateRoleRequest(BaseModel):
    name: str | None = None
    permissions: list[str] | None = None


# ── Subscription ──────────────────────────────────────────────────────────────

class SubscriptionPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    display_name: str = ""
    description: str | None = None
    price_monthly: float | None = None
    price_annually: float | None = None   # model field is price_annually
    currency: str = "USD"
    max_users: int | None = None
    max_storage_gb: int | None = None
    stripe_price_id_monthly: str | None = None
    stripe_price_id_annually: str | None = None
    is_active: bool = True
    is_public: bool = True
    sort_order: int = 0


class SubscriptionStatusResponse(BaseModel):
    status: str
    plan_name: str
    current_period_end: str | None = None
    cancel_at_period_end: bool = False
    trial_ends_at: str | None = None


class CreateCheckoutRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    plan_id: str
    billing_cycle: str = "monthly"  # monthly | annual
    success_url: str
    cancel_url: str
    payment_provider: str = "stripe"  # stripe | paypal


class BillingHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    amount: float
    currency: str
    status: str
    stripe_invoice_id: str | None = None
    created_at: datetime | None = None


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str | None = None


class SetSettingRequest(BaseModel):
    key: str
    value: str | None = None


# ── Feature flags ──────────────────────────────────────────────────────────────

class FeatureFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    is_enabled: bool
    rollout_percentage: int = 100


class SetFeatureFlagRequest(BaseModel):
    name: str
    is_enabled: bool
    description: str | None = None
    rollout_percentage: int = 100


# ── Team invitation ────────────────────────────────────────────────────────────

class SendInvitationRequest(BaseModel):
    email: EmailStr
    role_name: str = "User"
    message: str | None = None


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role_name: str
    status: str = "Pending"
    expires_at: datetime
    created_at: datetime


# ── Audit log ──────────────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    actor_id: str | None = None
    user_name: str | None = None
    http_method: str | None = None
    url: str | None = None
    http_status_code: int | None = None
    execution_duration: int | None = None
    ip_address: str | None = Field(None, alias="client_ip_address")
    created_at: datetime | None = None


# ── Dashboard ──────────────────────────────────────────────────────────────────

class DashboardStatsResponse(BaseModel):
    total_users: int = 0
    total_generations: int = 0
    active_subscriptions: int = 0
    recent_signups: int = 0


class SaveLayoutRequest(BaseModel):
    layout: dict
