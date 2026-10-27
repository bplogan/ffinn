"""
Staging demo tenant — fake users (one per role) and realistic sample data for host QA.

Idempotent: safe to run on every staging API startup and after agent deploys.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, UTC

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.permissions import Roles
from app.core.security import hash_password
from app.domain.models.audit import AuditLog
from app.domain.models.identity import IdentityRole, IdentityRoleClaim, IdentityUser, IdentityUserRole
from app.domain.models.notifications import NotificationConfiguration
from app.domain.models.projects import Project, ProjectStatus
from app.domain.models.subscription import EnhancedTenantSubscription, SubscriptionPlan
from app.domain.models.tenant import TeamInvitation, Tenant

log = structlog.get_logger(__name__)

STAGING_DEMO_EMAIL_DOMAIN = "staging-demo.ffinn"


def should_seed_staging_demo() -> bool:
    if settings.seed_staging_demo:
        return True
    return settings.environment.lower() == "staging"


def _role_slug(role_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", role_name.lower()).strip("-")
    return slug or "user"


def demo_email_for_role(role_name: str) -> str:
    return f"{_role_slug(role_name)}@{STAGING_DEMO_EMAIL_DOMAIN}"


async def ensure_staging_tenant(db: AsyncSession) -> Tenant:
    name = settings.staging_demo_tenant_name
    normalized = name.strip().lower()
    tenant = (
        await db.execute(select(Tenant).where(Tenant.normalized_name == normalized))
    ).scalar_one_or_none()
    if tenant:
        return tenant

    tenant = Tenant(
        id=uuid.uuid4(),
        name=name.strip(),
        normalized_name=normalized,
        is_active=True,
        is_available=True,
        admin_email_address=demo_email_for_role(Roles.ADMIN),
        created_at=datetime.now(UTC),
    )
    db.add(tenant)
    await db.flush()
    log.info("Created staging demo tenant", tenant=normalized)
    return tenant


async def ensure_tenant_roles(db: AsyncSession, tenant_id: uuid.UUID) -> list[IdentityRole]:
    """Ensure every default framework role exists on the tenant (adapts when Roles change)."""
    for role_name, perms in Roles.DEFAULT_ROLE_PERMISSIONS.items():
        role = (
            await db.execute(
                select(IdentityRole).where(
                    IdentityRole.tenant_id == tenant_id,
                    IdentityRole.normalized_name == role_name.upper(),
                )
            )
        ).scalar_one_or_none()
        if not role:
            role = IdentityRole(
                id=uuid.uuid4(),
                name=role_name,
                normalized_name=role_name.upper(),
                tenant_id=tenant_id,
                is_system=role_name in (Roles.ADMIN, Roles.USER),
            )
            db.add(role)
            await db.flush()
            for perm in perms:
                db.add(IdentityRoleClaim(
                    role_id=role.id,
                    claim_type="Permission",
                    claim_value=perm,
                ))

    await db.flush()
    return list(
        (
            await db.execute(
                select(IdentityRole)
                .where(IdentityRole.tenant_id == tenant_id)
                .order_by(IdentityRole.name)
            )
        ).scalars().all()
    )


async def ensure_role_demo_users(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    roles: list[IdentityRole],
) -> list[dict[str, str]]:
    """One confirmed user per tenant role — emails are fake and skip verification."""
    password = settings.staging_demo_password
    accounts: list[dict[str, str]] = []
    tenant_name = settings.staging_demo_tenant_name

    for role in roles:
        role_name = role.name
        email = demo_email_for_role(role_name)
        username = f"staging-{_role_slug(role_name)}"
        user = (
            await db.execute(
                select(IdentityUser).where(
                    IdentityUser.tenant_id == tenant_id,
                    IdentityUser.normalized_email == email.upper(),
                )
            )
        ).scalar_one_or_none()
        if not user:
            user = IdentityUser(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_name=username,
                normalized_user_name=username.upper(),
                email=email,
                normalized_email=email.upper(),
                password_hash=hash_password(password),
                name="Staging",
                surname=role_name,
                is_active=True,
                email_confirmed=True,
            )
            db.add(user)
            await db.flush()

        link = (
            await db.execute(
                select(IdentityUserRole).where(
                    IdentityUserRole.user_id == user.id,
                    IdentityUserRole.role_id == role.id,
                )
            )
        ).scalar_one_or_none()
        if not link:
            db.add(IdentityUserRole(user_id=user.id, role_id=role.id))

        accounts.append({
            "role": role_name,
            "email": email,
            "username": username,
            "tenant_name": tenant_name,
        })

    await db.flush()
    return accounts


async def ensure_staging_subscription(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    existing = (
        await db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.tenant_id == tenant_id,
                EnhancedTenantSubscription.status.in_(["active", "trialing"]),
            )
        )
    ).scalar_one_or_none()
    if existing:
        return

    plan = (
        await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == "pro").limit(1)
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    db.add(EnhancedTenantSubscription(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        plan_id=plan.id if plan else None,
        plan_name=plan.name if plan else "pro",
        billing_cycle="monthly",
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=365),
        payment_provider="manual",
        created_at=now,
    ))
    await db.flush()


async def seed_staging_core_demo_data(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Baseline sample rows for common admin/tenant screens."""
    admin = (
        await db.execute(
            select(IdentityUser).where(
                IdentityUser.tenant_id == tenant_id,
                IdentityUser.normalized_email == demo_email_for_role(Roles.ADMIN).upper(),
            )
        )
    ).scalar_one_or_none()
    if not admin:
        return

    audit_count = (
        await db.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.tenant_id == tenant_id)
        )
    ).scalar() or 0
    if audit_count < 5:
        samples = [
            ("User", "Create", "Created staging demo user"),
            ("Project", "Update", "Updated website redesign project"),
            ("Role", "Read", "Viewed role permissions"),
            ("Subscription", "View", "Viewed subscription details"),
            ("Settings", "Update", "Updated notification preferences"),
        ]
        for entity, action, comment in samples:
            db.add(AuditLog(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=admin.id,
                user_name=admin.user_name,
                entity_type=entity,
                action=action,
                comment=comment,
                http_method="POST",
                http_status_code=200,
                created_at=datetime.now(UTC),
            ))

    invite_count = (
        await db.execute(
            select(func.count()).select_from(TeamInvitation).where(TeamInvitation.tenant_id == tenant_id)
        )
    ).scalar() or 0
    if invite_count == 0:
        db.add(TeamInvitation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            email="pending-invite@staging-demo.ffinn",
            role_name=Roles.USER,
            token=f"staging-demo-invite-{uuid.uuid4().hex}",
            invited_by_user_id=admin.id,
            invited_by_email=admin.email or demo_email_for_role(Roles.ADMIN),
            status="Pending",
            message="Join the staging demo workspace.",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=14),
        ))

    notif = (
        await db.execute(
            select(NotificationConfiguration).where(NotificationConfiguration.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not notif:
        db.add(NotificationConfiguration(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sms_enabled=False,
            push_enabled=True,
            push_provider="firebase",
        ))

    await db.flush()


async def seed_projects_demo_data(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    count = (
        await db.execute(
            select(func.count()).select_from(Project).where(Project.tenant_id == tenant_id)
        )
    ).scalar() or 0
    if count > 0:
        return

    samples = [
        ("Website redesign", "Refresh marketing site and onboarding flow.", ProjectStatus.ACTIVE),
        ("Mobile app MVP", "First release for iOS and Android clients.", ProjectStatus.ACTIVE),
        ("Customer portal", "Self-service billing and support hub.", ProjectStatus.DRAFT),
        ("Data migration", "Move legacy CRM records into ffinn.", ProjectStatus.COMPLETED),
        ("Q3 compliance review", "SOC2 evidence collection and policy updates.", ProjectStatus.ARCHIVED),
    ]
    now = datetime.now(UTC)
    for title, description, status in samples:
        db.add(Project(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            title=title,
            description=description,
            status=status,
            created_at=now,
            updated_at=now,
        ))
    await db.flush()
    log.info("Seeded staging demo projects", tenant_id=str(tenant_id), count=len(samples))


async def repair_staging_demo_users_if_missing(db: AsyncSession) -> list[dict[str, str]]:
    """Backfill demo users when the staging tenant exists but has no accounts."""
    normalized = settings.staging_demo_tenant_name.strip().lower()
    tenant = (
        await db.execute(select(Tenant).where(Tenant.normalized_name == normalized))
    ).scalar_one_or_none()
    if not tenant:
        return []

    user_count = (
        await db.execute(
            select(func.count()).select_from(IdentityUser).where(
                IdentityUser.tenant_id == tenant.id
            )
        )
    ).scalar() or 0
    if user_count > 0:
        return []

    roles = await ensure_tenant_roles(db, tenant.id)
    accounts = await ensure_role_demo_users(db, tenant.id, roles)
    await ensure_staging_subscription(db, tenant.id)
    await seed_staging_core_demo_data(db, tenant.id)
    await seed_projects_demo_data(db, tenant.id)
    await db.commit()
    log.info("Repaired empty staging demo tenant", tenant=normalized, users=len(accounts))
    return accounts


async def seed_staging_demo(db: AsyncSession) -> list[dict[str, str]]:
    """Create/update the staging tenant, role users, and demo feature data."""
    try:
        tenant = await ensure_staging_tenant(db)
        roles = await ensure_tenant_roles(db, tenant.id)
        accounts = await ensure_role_demo_users(db, tenant.id, roles)
        await ensure_staging_subscription(db, tenant.id)
        await seed_staging_core_demo_data(db, tenant.id)

        # AI-generated staging demo seed calls — DO NOT REMOVE THIS COMMENT
        await seed_projects_demo_data(db, tenant.id)

        await db.commit()
        log.info(
            "Staging demo seed complete",
            tenant=tenant.normalized_name,
            role_accounts=len(accounts),
            password_configured=bool(settings.staging_demo_password),
        )
        return accounts
    except Exception:
        await db.rollback()
        raise


async def list_staging_demo_accounts(db: AsyncSession) -> dict:
    tenant = (
        await db.execute(
            select(Tenant).where(
                Tenant.normalized_name == settings.staging_demo_tenant_name.strip().lower()
            )
        )
    ).scalar_one_or_none()
    if not tenant:
        return {
            "tenant_name": settings.staging_demo_tenant_name,
            "password": settings.staging_demo_password,
            "accounts": [],
        }

    roles = list(
        (
            await db.execute(
                select(IdentityRole)
                .where(IdentityRole.tenant_id == tenant.id)
                .order_by(IdentityRole.name)
            )
        ).scalars().all()
    )
    accounts = [
        {
            "role": role.name,
            "email": demo_email_for_role(role.name),
            "username": f"staging-{_role_slug(role.name)}",
            "tenant_name": tenant.normalized_name,
        }
        for role in roles
    ]
    return {
        "tenant_name": tenant.normalized_name,
        "password": settings.staging_demo_password,
        "login_hint": f'Use tenant name "{tenant.normalized_name}" on the login page.',
        "accounts": accounts,
    }
