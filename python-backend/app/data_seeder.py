"""
Data seeder — creates default roles, permissions, subscription plans, admin user, and feature flags.
Run once on first start or via: python -m app.data_seeder

This file is a BOUNDED CORE UPDATE FILE.
AI-generated features may add seed calls below the marker comment.
Do NOT modify the existing seed calls above the marker.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.models.misc import AppSetting
from app.core.permissions import Roles
from app.core.security import hash_password
from app.domain.models.identity import IdentityRole, IdentityRoleClaim, IdentityUser, IdentityUserRole
from app.domain.models.misc import FeatureFlag
from app.domain.models.subscription import SubscriptionPlan
from app.infrastructure.database import async_session_factory, init_db

log = structlog.get_logger(__name__)


async def seed_roles(db: AsyncSession) -> None:
    _SYSTEM_ROLE_NAMES = {Roles.ADMIN.upper(), Roles.USER.upper()}

    for role_name, perms in Roles.DEFAULT_ROLE_PERMISSIONS.items():
        is_system = role_name.upper() in _SYSTEM_ROLE_NAMES
        existing = (await db.execute(
            select(IdentityRole).where(
                IdentityRole.tenant_id.is_(None),
                IdentityRole.normalized_name == role_name.upper(),
            )
        )).scalar_one_or_none()
        if existing:
            # Ensure system flag is correct on pre-existing seed roles
            if is_system and not existing.is_system:
                existing.is_system = True
            continue
        role = IdentityRole(
            id=uuid.uuid4(),
            name=role_name,
            normalized_name=role_name.upper(),
            is_system=is_system,
        )
        db.add(role)
        await db.flush()
        for perm in perms:
            db.add(IdentityRoleClaim(
                role_id=role.id,
                claim_type="Permission",
                claim_value=perm,
            ))
    await db.commit()
    log.info("Roles seeded")


async def seed_admin_user(db: AsyncSession) -> None:
    admin_email = settings.default_admin_email
    admin_password = settings.default_admin_password
    if not admin_email or not admin_password:
        log.warning("DEFAULT_ADMIN_EMAIL / DEFAULT_ADMIN_PASSWORD not set — skipping admin seed")
        return

    existing = (await db.execute(
        select(IdentityUser).where(IdentityUser.normalized_email == admin_email.upper())
    )).scalar_one_or_none()
    if existing:
        return

    user = IdentityUser(
        id=uuid.uuid4(),
        user_name="admin",
        normalized_user_name="ADMIN",
        email=admin_email,
        normalized_email=admin_email.upper(),
        password_hash=hash_password(admin_password),
        name="System",       # IdentityUser uses name/surname, not first_name/last_name
        surname="Admin",
        is_active=True,
        email_confirmed=True,
    )
    db.add(user)
    await db.flush()

    admin_role = (await db.execute(
        select(IdentityRole).where(IdentityRole.normalized_name == "ADMIN")
    )).scalar_one_or_none()
    if admin_role:
        db.add(IdentityUserRole(user_id=user.id, role_id=admin_role.id))

    await db.commit()
    log.info("Admin user seeded", email=admin_email)


async def seed_subscription_plans(db: AsyncSession) -> None:
    # Placeholder tiers with no pricing: set your own prices in Admin -> Subscription Plans.
    plans = [
        {"name": "free", "display_name": "Free", "price_monthly": 0.0, "price_annually": 0.0, "max_users": 3, "max_storage_gb": 1},
        {"name": "starter", "display_name": "Starter", "price_monthly": 0.0, "price_annually": 0.0, "max_users": 10, "max_storage_gb": 10},
        {"name": "pro", "display_name": "Pro", "price_monthly": 0.0, "price_annually": 0.0, "max_users": 50, "max_storage_gb": 50},
        {"name": "enterprise", "display_name": "Enterprise", "price_monthly": 0.0, "price_annually": 0.0, "max_users": None, "max_storage_gb": None},
    ]
    for plan_data in plans:
        existing = (await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == plan_data["name"])
        )).scalar_one_or_none()
        if existing:
            continue
        db.add(SubscriptionPlan(
            id=uuid.uuid4(),
            is_active=True,
            created_at=datetime.now(timezone.utc),
            **plan_data,
        ))
    await db.commit()
    log.info("Subscription plans seeded")


_FEATURE_FLAG_DEFAULTS: list[tuple[str, bool, str]] = [
    (
        "ai_agent_enabled",
        True,
        "AI Agent code generation, staging deploys, and release workflows.",
    ),
    (
        "team_invitations_enabled",
        True,
        "Invite teammates by email and assign roles within a tenant.",
    ),
    (
        "two_factor_auth_enabled",
        True,
        "TOTP two-factor authentication for user login.",
    ),
    (
        "sso_enabled",
        False,
        "Single sign-on via OIDC/SAML tenant configurations.",
    ),
    (
        "stripe_billing_enabled",
        True,
        "Stripe checkout, subscriptions, and billing webhooks.",
    ),
    (
        "sms_notifications_enabled",
        True,
        "SMS notification channel for tenant alerts.",
    ),
    (
        "push_notifications_enabled",
        True,
        "Push notification channel (e.g. Firebase) for tenant alerts.",
    ),
]


async def seed_feature_flags(db: AsyncSession) -> None:
    for name, enabled, description in _FEATURE_FLAG_DEFAULTS:
        existing = (await db.execute(
            select(FeatureFlag).where(FeatureFlag.name == name)
        )).scalar_one_or_none()
        if existing:
            if not existing.description:
                existing.description = description
            continue
        db.add(FeatureFlag(
            id=uuid.uuid4(),
            name=name,
            description=description,
            is_enabled=enabled,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
    await db.commit()
    log.info("Feature flags seeded")


async def seed_app_settings(db: AsyncSession) -> None:
    """Seed default host-level app settings.  Only inserts rows that don't exist yet."""
    defaults: list[tuple[str, str, bool]] = [
        # General
        ("general.app_name",           settings.app_name,                        False),
        ("general.app_url",            settings.app_url,                         False),
        ("general.support_email",      settings.smtp_from_address,               False),
        # Registration
        ("registration.allow_user_registration",       str(settings.allow_registration).lower(), False),
        ("registration.allow_tenant_registration",     str(settings.allow_registration).lower(), False),
        ("registration.new_users_active_by_default",   "true",                   False),
        ("registration.require_email_confirmation",    str(settings.require_email_confirmation).lower(), False),
        ("registration.restricted_email_domains_enabled", "false",              False),
        ("registration.allowed_email_domains",         "",                       False),
        # Security — password
        ("security.password_min_length",       str(settings.password_min_length),         False),
        ("security.password_require_digit",    str(settings.password_require_digit).lower(), False),
        ("security.password_require_lowercase","true",                           False),
        ("security.password_require_uppercase",str(settings.password_require_uppercase).lower(), False),
        ("security.password_require_special",  str(settings.password_require_special).lower(), False),
        # Security — lockout
        ("security.lockout_enabled",           "true",                           False),
        ("security.lockout_max_attempts",      "5",                              False),
        ("security.lockout_duration_seconds",  "300",                            False),
        # Security — 2FA / tokens
        ("security.two_factor_enabled",        "false",                          False),
        ("security.jwt_access_minutes",        str(settings.jwt_access_token_expire_minutes), False),
        ("security.jwt_refresh_days",          str(settings.jwt_refresh_token_expire_days),   False),
        # SMTP
        ("smtp.from_address",  settings.smtp_from_address,  False),
        ("smtp.from_name",     settings.smtp_from_name,     False),
        ("smtp.host",          settings.smtp_host,          False),
        ("smtp.port",          str(settings.smtp_port),     False),
        ("smtp.use_ssl",       str(settings.smtp_use_tls).lower(), False),
        ("smtp.use_auth",      "true" if settings.smtp_username else "false", False),
        ("smtp.username",      settings.smtp_username,      False),
        ("smtp.password",      settings.smtp_password,      True),
        # Payments — Stripe
        ("payments.stripe_enabled",         str(settings.stripe_enabled).lower(),   False),
        ("payments.stripe_publishable_key",  settings.stripe_publishable_key,       False),
        ("payments.stripe_secret_key",       settings.stripe_secret_key,            True),
        ("payments.stripe_webhook_secret",   settings.stripe_webhook_secret,        True),
        # Payments — PayPal
        ("payments.paypal_enabled",          str(settings.paypal_enabled).lower(),  False),
        ("payments.paypal_mode",             settings.paypal_mode,                  False),
        ("payments.paypal_client_id",        settings.paypal_client_id,             False),
        ("payments.paypal_client_secret",    settings.paypal_client_secret,         True),
        ("payments.paypal_webhook_id",       settings.paypal_webhook_id,            False),
        # Storage
        ("storage.backend",                  settings.file_storage_backend,         False),
        ("storage.azure_connection_string",  settings.azure_storage_connection_string, True),
        ("storage.azure_container",          settings.azure_storage_container_name, False),
        ("storage.s3_bucket",                settings.s3_bucket_name,               False),
        ("storage.aws_region",               settings.aws_region,                   False),
        ("storage.aws_access_key_id",        settings.aws_access_key_id,            True),
        ("storage.aws_secret_access_key",    settings.aws_secret_access_key,        True),
    ]

    for key, value, is_encrypted in defaults:
        existing = (await db.execute(
            select(AppSetting)
            .where(AppSetting.key == key)
            .where(AppSetting.tenant_id.is_(None))
        )).scalar_one_or_none()
        if existing:
            continue
        db.add(AppSetting(
            id=uuid.uuid4(), key=key, value=value,
            is_encrypted=is_encrypted, tenant_id=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
    await db.commit()
    log.info("App settings seeded")


async def seed() -> None:
    await init_db()
    async with async_session_factory() as db:
        await seed_roles(db)
        await seed_admin_user(db)
        await seed_subscription_plans(db)
        await seed_feature_flags(db)
        await seed_app_settings(db)

        # AI-generated seed calls — DO NOT REMOVE THIS COMMENT
        # (additional seed calls are inserted here by the AI agent merge helper)

    log.info("Database seeding complete")


if __name__ == "__main__":
    asyncio.run(seed())
