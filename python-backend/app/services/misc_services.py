"""Feature flags, app settings, audit logs, dashboard, and team invitations services."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ConflictException, BusinessException
from app.domain.models.misc import (
    AppSetting, FeatureDefinition, FeatureValue, FeatureFlag, DashboardLayout
)
from app.domain.models.tenant import TeamInvitation
from app.domain.models.identity import IdentityUser
from app.domain.models.audit import AuditLog

log = structlog.get_logger(__name__)


# ── Settings Service ──────────────────────────────────────────────────────────

class SettingsService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_all_settings(self, tenant_id: Optional[uuid.UUID] = None) -> list[AppSetting]:
        q = select(AppSetting)
        if tenant_id:
            q = q.where(AppSetting.tenant_id == tenant_id)
        return list((await self._db.execute(q.order_by(AppSetting.key))).scalars().all())

    _SENSITIVE_KEY_PARTS = ("password", "secret", "token", "apikey", "api_key", "private")

    def _is_public_setting_key(self, key: str) -> bool:
        lower = key.lower()
        return not any(part in lower for part in self._SENSITIVE_KEY_PARTS)

    async def get_public_settings(self) -> list[AppSetting]:
        """Return global (no-tenant) settings safe to expose unauthenticated."""
        q = select(AppSetting).where(AppSetting.tenant_id.is_(None)).order_by(AppSetting.key)
        settings = list((await self._db.execute(q)).scalars().all())
        return [s for s in settings if self._is_public_setting_key(s.key)]

    async def get_settings_by_prefix(self, prefix: str, tenant_id: Optional[uuid.UUID] = None) -> list[AppSetting]:
        q = select(AppSetting).where(AppSetting.key.like(f"{prefix}%"))
        q = q.where(AppSetting.tenant_id == tenant_id) if tenant_id else q.where(AppSetting.tenant_id.is_(None))
        return list((await self._db.execute(q.order_by(AppSetting.key))).scalars().all())

    async def get_setting_groups(self, tenant_id: Optional[uuid.UUID] = None) -> list[str]:
        """Return distinct top-level key prefixes (up to the first '.')."""
        settings = await self.get_all_settings(tenant_id)
        prefixes: set[str] = set()
        for s in settings:
            if "." in s.key:
                prefixes.add(s.key.split(".")[0])
        return sorted(prefixes)

    async def get_setting(self, key: str, tenant_id: Optional[uuid.UUID] = None) -> Optional[str]:
        q = select(AppSetting).where(AppSetting.key == key)
        q = q.where(AppSetting.tenant_id == tenant_id) if tenant_id else q.where(AppSetting.tenant_id.is_(None))
        result = (await self._db.execute(q)).scalar_one_or_none()
        return result.value if result else None

    async def set_setting(self, key: str, value: str, tenant_id: Optional[uuid.UUID] = None) -> None:
        q = select(AppSetting).where(AppSetting.key == key)
        q = q.where(AppSetting.tenant_id == tenant_id) if tenant_id else q.where(AppSetting.tenant_id.is_(None))
        existing = (await self._db.execute(q)).scalar_one_or_none()
        if existing:
            existing.value = value
            existing.updated_at = datetime.now(timezone.utc)
        else:
            self._db.add(AppSetting(
                id=uuid.uuid4(), key=key, value=value, tenant_id=tenant_id,
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
            ))
        await self._db.commit()

    async def bulk_set_settings(self, settings: list[dict], tenant_id: Optional[uuid.UUID] = None) -> None:
        """Set multiple settings at once. Each dict must have 'key' and 'value'."""
        for item in settings:
            await self.set_setting(item["key"], item["value"], tenant_id)

    async def delete_setting(self, key: str, tenant_id: Optional[uuid.UUID] = None) -> None:
        q = delete(AppSetting).where(AppSetting.key == key)
        if tenant_id:
            q = q.where(AppSetting.tenant_id == tenant_id)
        await self._db.execute(q)
        await self._db.commit()


# ── Feature Flag Service ──────────────────────────────────────────────────────

class FeatureFlagService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def is_enabled(
        self, feature_name: str, tenant_id: Optional[uuid.UUID] = None
    ) -> bool:
        # Check tenant-specific override
        if tenant_id:
            tenant_val = (await self._db.execute(
                select(FeatureValue).where(
                    FeatureValue.name == feature_name,
                    FeatureValue.tenant_id == tenant_id,
                )
            )).scalar_one_or_none()
            if tenant_val:
                return tenant_val.value.lower() == "true"

        # Fall back to global flag
        flag = (await self._db.execute(
            select(FeatureFlag).where(FeatureFlag.name == feature_name)
        )).scalar_one_or_none()
        return flag.is_enabled if flag else False

    async def get_all_flags(self) -> list[FeatureFlag]:
        return list((await self._db.execute(select(FeatureFlag).order_by(FeatureFlag.name))).scalars().all())

    async def get_flag(self, name: str) -> FeatureFlag:
        flag = (await self._db.execute(
            select(FeatureFlag).where(FeatureFlag.name == name)
        )).scalar_one_or_none()
        if not flag:
            raise NotFoundException("Feature flag", name)
        return flag

    async def set_flag(self, name: str, is_enabled: bool) -> None:
        existing = (await self._db.execute(
            select(FeatureFlag).where(FeatureFlag.name == name)
        )).scalar_one_or_none()
        if existing:
            existing.is_enabled = is_enabled
            existing.updated_at = datetime.now(timezone.utc)
        else:
            self._db.add(FeatureFlag(
                id=uuid.uuid4(), name=name, is_enabled=is_enabled,
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
            ))
        await self._db.commit()

    async def create_flag(
        self,
        name: str,
        is_enabled: bool = False,
        description: Optional[str] = None,
        rollout_percentage: int = 100,
    ) -> FeatureFlag:
        existing = (await self._db.execute(
            select(FeatureFlag).where(FeatureFlag.name == name)
        )).scalar_one_or_none()
        if existing:
            raise ConflictException(f"Feature flag '{name}' already exists.")
        flag = FeatureFlag(
            id=uuid.uuid4(),
            name=name,
            description=description,
            is_enabled=is_enabled,
            rollout_percentage=rollout_percentage,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._db.add(flag)
        await self._db.commit()
        await self._db.refresh(flag)
        return flag

    async def update_flag(
        self,
        name: str,
        is_enabled: Optional[bool] = None,
        description: Optional[str] = None,
        rollout_percentage: Optional[int] = None,
    ) -> FeatureFlag:
        flag = await self.get_flag(name)
        if is_enabled is not None:
            flag.is_enabled = is_enabled
        if description is not None:
            flag.description = description
        if rollout_percentage is not None:
            flag.rollout_percentage = rollout_percentage
        flag.updated_at = datetime.now(timezone.utc)
        await self._db.commit()
        return flag

    async def get_definitions(self) -> list[FeatureDefinition]:
        return list((await self._db.execute(select(FeatureDefinition).order_by(FeatureDefinition.name))).scalars().all())

    async def create_definition(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        value_type: str = "Boolean",
        default_value: Optional[str] = None,
    ) -> FeatureDefinition:
        existing = (await self._db.execute(
            select(FeatureDefinition).where(FeatureDefinition.name == name)
        )).scalar_one_or_none()
        if existing:
            raise ConflictException(f"Feature definition '{name}' already exists.")
        defn = FeatureDefinition(
            id=uuid.uuid4(),
            name=name,
            display_name=display_name,
            description=description,
            value_type=value_type,
            default_value=default_value,
        )
        self._db.add(defn)
        await self._db.commit()
        await self._db.refresh(defn)
        return defn

    async def get_plan_features(self, plan_id: uuid.UUID) -> list:
        from app.domain.models.misc import PlanFeatureFlag
        result = await self._db.execute(
            select(PlanFeatureFlag).where(PlanFeatureFlag.plan_id == plan_id)
        )
        return list(result.scalars().all())

    async def set_plan_features(self, plan_id: uuid.UUID, features: list[dict]) -> None:
        """Replace all plan feature flags for a plan."""
        from app.domain.models.misc import PlanFeatureFlag
        from sqlalchemy import delete as sa_delete
        await self._db.execute(
            sa_delete(PlanFeatureFlag).where(PlanFeatureFlag.plan_id == plan_id)
        )
        for feat in features:
            self._db.add(PlanFeatureFlag(
                id=uuid.uuid4(),
                plan_id=plan_id,
                feature_name=feat["feature_name"],
                is_enabled=feat.get("is_enabled", True),
                value=feat.get("value"),
            ))
        await self._db.commit()


# ── Audit Log Service ─────────────────────────────────────────────────────────

class AuditLogService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def log(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[str],
        actor_id: Optional[uuid.UUID],
        tenant_id: Optional[uuid.UUID],
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        ip_address: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> None:
        import json
        entry = AuditLog(
            id=uuid.uuid4(),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            user_id=actor_id,
            tenant_id=tenant_id,
            changes={"old": old_values, "new": new_values} if old_values or new_values else None,
            client_ip_address=ip_address,
            comment=json.dumps(extra) if extra else None,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(entry)
        await self._db.commit()

    async def get_logs(
        self,
        tenant_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        entity_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        q = select(AuditLog)
        if tenant_id:
            q = q.where(AuditLog.tenant_id == tenant_id)
        if actor_id:
            q = q.where(AuditLog.user_id == actor_id)
        if entity_type:
            q = q.where(AuditLog.entity_type == entity_type)
        total = (await self._db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        items = (
            await self._db.execute(
                q.order_by(AuditLog.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return list(items), total


# ── Dashboard Service ─────────────────────────────────────────────────────────

class DashboardService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_layout(self, user_id: uuid.UUID) -> Optional[DashboardLayout]:
        return (await self._db.execute(
            select(DashboardLayout).where(DashboardLayout.user_id == user_id)
        )).scalar_one_or_none()

    async def save_layout(self, user_id: uuid.UUID, layout: dict) -> DashboardLayout:
        import json
        existing = await self.get_layout(user_id)
        if existing:
            existing.layout_json = json.dumps(layout)
            existing.updated_at = datetime.now(timezone.utc)
        else:
            existing = DashboardLayout(
                id=uuid.uuid4(),
                user_id=user_id,
                layout_json=json.dumps(layout),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self._db.add(existing)
        await self._db.commit()
        await self._db.refresh(existing)
        return existing

    async def get_stats(self, tenant_id: uuid.UUID) -> dict:
        """Return basic dashboard statistics for the tenant."""
        from app.domain.models.ai_agent import AIAgentGeneration

        user_count = (await self._db.execute(
            select(func.count(IdentityUser.id)).where(IdentityUser.tenant_id == tenant_id)
        )).scalar() or 0
        gen_count = (await self._db.execute(
            select(func.count(AIAgentGeneration.id)).where(AIAgentGeneration.tenant_id == tenant_id)
        )).scalar() or 0
        return {"total_users": user_count, "total_generations": gen_count}

    async def get_activity(self, tenant_id: Optional[uuid.UUID], limit: int = 20) -> list:
        """Return recent audit log entries as activity feed."""
        q = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if tenant_id:
            q = q.where(AuditLog.tenant_id == tenant_id)
        items = (await self._db.execute(q)).scalars().all()
        return [
            {
                "id": str(item.id),
                "action": item.action,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "actor_id": str(item.user_id) if item.user_id else None,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ]

    async def reset_layout(self, user_id: uuid.UUID) -> None:
        """Delete the stored layout so the default is used."""
        from sqlalchemy import delete as sa_delete
        await self._db.execute(sa_delete(DashboardLayout).where(DashboardLayout.user_id == user_id))
        await self._db.commit()


# ── Team Invitation Service ───────────────────────────────────────────────────

class TeamInvitationService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def send_invitation(
        self,
        tenant_id: uuid.UUID,
        inviter_id: uuid.UUID,
        email: str,
        role_name: str = "User",
        *,
        base_url: str | None = None,
    ) -> TeamInvitation:
        from app.services.host_settings import HostSettings
        hs = await HostSettings.load(self._db)
        email_svc = hs.build_email_service()

        existing_user = (await self._db.execute(
            select(IdentityUser).where(
                IdentityUser.email == email.lower(),
                IdentityUser.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if existing_user:
            raise ConflictException("User is already a member of this tenant.")

        existing_invite = (await self._db.execute(
            select(TeamInvitation).where(
                TeamInvitation.email == email.lower(),
                TeamInvitation.tenant_id == tenant_id,
                TeamInvitation.accepted_at.is_(None),
                TeamInvitation.expires_at > datetime.now(timezone.utc),
            )
        )).scalar_one_or_none()
        if existing_invite:
            raise ConflictException("An invitation for this email is already pending.")

        # Fetch inviter before creating the record so we can capture their email
        inviter = (await self._db.execute(
            select(IdentityUser).where(IdentityUser.id == inviter_id)
        )).scalar_one_or_none()

        token = secrets.token_urlsafe(48)
        invitation = TeamInvitation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            invited_by_user_id=inviter_id,
            invited_by_email=inviter.email if inviter else "",
            email=email.lower(),
            role_name=role_name,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(invitation)
        await self._db.commit()

        from app.domain.models.tenant import Tenant
        tenant = (await self._db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )).scalar_one_or_none()

        await email_svc.send_team_invitation(
            to=email,
            inviter_name=inviter.full_name if inviter else "A teammate",
            tenant_name=tenant.name if tenant else "your team",
            token=token,
            base_url=base_url,
        )
        return invitation

    async def accept_invitation(self, token: str, user_id: uuid.UUID) -> None:
        invite = (await self._db.execute(
            select(TeamInvitation).where(
                TeamInvitation.token == token,
                TeamInvitation.accepted_at.is_(None),
                TeamInvitation.expires_at > datetime.now(timezone.utc),
            )
        )).scalar_one_or_none()
        if not invite:
            raise NotFoundException("Invitation not found or has expired.")

        from app.domain.models.identity import IdentityRole, IdentityUserRole
        user = (await self._db.execute(
            select(IdentityUser).where(IdentityUser.id == user_id)
        )).scalar_one_or_none()
        if user:
            if user.email.lower() != invite.email.lower():
                raise BusinessException("This invitation was sent to a different email address.")
            user.tenant_id = invite.tenant_id
            role = (await self._db.execute(
                select(IdentityRole).where(
                    IdentityRole.tenant_id == invite.tenant_id,
                    IdentityRole.normalized_name == invite.role_name.upper(),
                )
            )).scalar_one_or_none()
            if role:
                self._db.add(IdentityUserRole(user_id=user_id, role_id=role.id))
        invite.accepted_at = datetime.now(timezone.utc)
        await self._db.commit()

    async def get_pending_invitations(self, tenant_id: uuid.UUID) -> list[TeamInvitation]:
        return list((await self._db.execute(
            select(TeamInvitation).where(
                TeamInvitation.tenant_id == tenant_id,
                TeamInvitation.accepted_at.is_(None),
                TeamInvitation.expires_at > datetime.now(timezone.utc),
            ).order_by(TeamInvitation.created_at.desc())
        )).scalars().all())

    async def revoke_invitation(self, invitation_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        invite = (await self._db.execute(
            select(TeamInvitation).where(
                TeamInvitation.id == invitation_id,
                TeamInvitation.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if not invite:
            raise NotFoundException("Invitation not found.")
        await self._db.delete(invite)
        await self._db.commit()

    async def get_invitation(
        self, invitation_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> TeamInvitation:
        invite = (await self._db.execute(
            select(TeamInvitation).where(
                TeamInvitation.id == invitation_id,
                TeamInvitation.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if not invite:
            raise NotFoundException("Invitation", str(invitation_id))
        return invite

    async def cancel_invitation(self, invitation_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        invite = (await self._db.execute(
            select(TeamInvitation).where(
                TeamInvitation.id == invitation_id,
                TeamInvitation.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if not invite:
            raise NotFoundException("Invitation", str(invitation_id))
        if invite.accepted_at:
            raise BusinessException("Cannot cancel an already-accepted invitation.")
        invite.status = "Cancelled"
        await self._db.commit()

    async def resend_invitation(
        self,
        invitation_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        base_url: str | None = None,
    ) -> TeamInvitation:
        invite = await self.get_invitation(invitation_id, tenant_id)
        if invite.accepted_at:
            raise BusinessException("Invitation already accepted.")
        if invite.status == "Cancelled":
            raise BusinessException("Cannot resend a cancelled invitation.")

        # Regenerate token and extend expiry
        invite.token = secrets.token_urlsafe(48)
        invite.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        invite.status = "Pending"
        await self._db.commit()

        from app.services.host_settings import HostSettings
        from app.domain.models.tenant import Tenant
        hs = await HostSettings.load(self._db)
        email_svc = hs.build_email_service()
        tenant = (await self._db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )).scalar_one_or_none()
        await email_svc.send_team_invitation(
            to=invite.email,
            inviter_name=invite.invited_by_email,
            tenant_name=tenant.name if tenant else "your team",
            token=invite.token,
            base_url=base_url,
        )
        return invite

    async def validate_token(self, token: str) -> dict:
        invite = (await self._db.execute(
            select(TeamInvitation).where(TeamInvitation.token == token)
        )).scalar_one_or_none()
        if not invite:
            raise NotFoundException("Invalid invitation token")
        if invite.expires_at < datetime.now(timezone.utc):
            raise BusinessException("Invitation has expired.")
        if invite.accepted_at:
            raise BusinessException("Invitation already accepted.")
        if invite.status == "Cancelled":
            raise BusinessException("Invitation has been cancelled.")
        return {
            "email": invite.email,
            "role_name": invite.role_name,
            "tenant_id": str(invite.tenant_id) if invite.tenant_id else None,
            "is_valid": True,
            "expires_at": invite.expires_at.isoformat(),
        }

    async def accept_publicly(
        self,
        token: str,
        username: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> dict:
        """Accept an invitation by creating a new user account (no prior auth required)."""
        from app.core.security import hash_password, generate_secure_token
        from app.domain.models.identity import IdentityRole, IdentityUserRole

        invite = (await self._db.execute(
            select(TeamInvitation).where(
                TeamInvitation.token == token,
                TeamInvitation.accepted_at.is_(None),
                TeamInvitation.expires_at > datetime.now(timezone.utc),
            )
        )).scalar_one_or_none()
        if not invite:
            raise NotFoundException("Invalid or expired invitation token")
        if invite.status == "Cancelled":
            raise BusinessException("Invitation has been cancelled.")

        # Check if email is already registered in this tenant
        existing = (await self._db.execute(
            select(IdentityUser).where(
                IdentityUser.normalized_email == invite.email.upper(),
                IdentityUser.tenant_id == invite.tenant_id,
            )
        )).scalar_one_or_none()
        if existing:
            raise ConflictException("An account with this email already exists.")

        user = IdentityUser(
            id=uuid.uuid4(),
            tenant_id=invite.tenant_id,
            user_name=username,
            normalized_user_name=username.upper(),
            email=invite.email,
            normalized_email=invite.email.upper(),
            password_hash=hash_password(password),
            name=first_name,
            surname=last_name,
            email_confirmed=True,
            security_stamp=generate_secure_token(16),
            concurrency_stamp=generate_secure_token(16),
        )
        self._db.add(user)
        await self._db.flush()

        role = (await self._db.execute(
            select(IdentityRole).where(
                IdentityRole.normalized_name == invite.role_name.upper(),
                IdentityRole.tenant_id == invite.tenant_id,
            )
        )).scalar_one_or_none()
        if role:
            self._db.add(IdentityUserRole(user_id=user.id, role_id=role.id))

        invite.accepted_at = datetime.now(timezone.utc)
        invite.accepted_by_user_id = user.id
        invite.status = "Accepted"
        await self._db.commit()

        return {"message": "Account created successfully.", "user_id": str(user.id)}


# ── Subscription Plan Service ─────────────────────────────────────────────────

class SubscriptionPlanService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_active_plans(self):
        from app.domain.models.subscription import SubscriptionPlan
        return list((await self._db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active, SubscriptionPlan.is_public)
            .order_by(SubscriptionPlan.sort_order)
        )).scalars().all())

    async def get_all_plans(self):
        from app.domain.models.subscription import SubscriptionPlan
        return list((await self._db.execute(
            select(SubscriptionPlan).order_by(SubscriptionPlan.sort_order)
        )).scalars().all())

    async def get_plan(self, plan_id: uuid.UUID):
        from app.domain.models.subscription import SubscriptionPlan
        plan = (await self._db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )).scalar_one_or_none()
        if not plan:
            raise NotFoundException("SubscriptionPlan", str(plan_id))
        return plan

    async def create_plan(
        self,
        name: str,
        display_name: str,
        price_monthly: float = 0,
        price_annually: float = 0,
        description: Optional[str] = None,
        max_users: Optional[int] = None,
        max_storage_gb: Optional[int] = None,
        currency: str = "USD",
        sort_order: int = 0,
        is_active: bool = True,
        is_public: bool = True,
        stripe_price_id_monthly: Optional[str] = None,
        stripe_price_id_annually: Optional[str] = None,
        paypal_plan_id_monthly: Optional[str] = None,
        paypal_plan_id_annually: Optional[str] = None,
    ):
        from app.domain.models.subscription import SubscriptionPlan
        plan = SubscriptionPlan(
            id=uuid.uuid4(),
            name=name,
            display_name=display_name,
            price_monthly=price_monthly,
            price_annually=price_annually,
            description=description,
            max_users=max_users,
            max_storage_gb=max_storage_gb,
            currency=currency,
            sort_order=sort_order,
            is_active=is_active,
            is_public=is_public,
            stripe_price_id_monthly=stripe_price_id_monthly,
            stripe_price_id_annually=stripe_price_id_annually,
            paypal_plan_id_monthly=paypal_plan_id_monthly,
            paypal_plan_id_annually=paypal_plan_id_annually,
        )
        self._db.add(plan)
        await self._db.commit()
        await self._db.refresh(plan)
        return plan

    async def update_plan(self, plan_id: uuid.UUID, **kwargs):
        plan = await self.get_plan(plan_id)
        for k, v in kwargs.items():
            if hasattr(plan, k) and v is not None:
                setattr(plan, k, v)
        await self._db.commit()
        await self._db.refresh(plan)
        return plan

    async def delete_plan(self, plan_id: uuid.UUID) -> None:
        plan = await self.get_plan(plan_id)
        await self._db.delete(plan)
        await self._db.commit()


# ── Onboarding Service ────────────────────────────────────────────────────────

# Default step definitions (configurable per deployment)
ONBOARDING_STEPS = [
    {"name": "profile", "label": "Complete Your Profile", "is_required": True},
    {"name": "invite_team", "label": "Invite Team Members", "is_required": False},
    {"name": "configure_settings", "label": "Configure Settings", "is_required": False},
    {"name": "explore_features", "label": "Explore Features", "is_required": False},
]


class OnboardingService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def _get_or_create(self, tenant_id: uuid.UUID, user_id: uuid.UUID):
        from app.domain.models.tenant import TenantOnboarding
        record = (await self._db.execute(
            select(TenantOnboarding).where(TenantOnboarding.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not record:
            record = TenantOnboarding(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                completed_steps=[],
                is_completed=False,
            )
            self._db.add(record)
            await self._db.commit()
            await self._db.refresh(record)
        return record

    async def get_status(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        from app.domain.models.tenant import TenantOnboarding
        record = (await self._db.execute(
            select(TenantOnboarding).where(TenantOnboarding.tenant_id == tenant_id)
        )).scalar_one_or_none()
        completed = record.completed_steps or [] if record else []
        return {
            "is_completed": record.is_completed if record else False,
            "completed_at": record.completed_at if record else None,
            "completed_steps": completed,
            "total_steps": len(ONBOARDING_STEPS),
            "completed_count": len(completed),
        }

    async def start(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        await self._get_or_create(tenant_id, user_id)
        return await self.get_status(tenant_id, user_id)

    async def complete_step(self, tenant_id: uuid.UUID, user_id: uuid.UUID, step_name: str) -> dict:
        record = await self._get_or_create(tenant_id, user_id)
        steps = list(record.completed_steps or [])
        if step_name not in steps:
            steps.append(step_name)
        record.completed_steps = steps

        # Auto-complete if all required steps done
        required = {s["name"] for s in ONBOARDING_STEPS if s["is_required"]}
        if required.issubset(set(steps)):
            record.is_completed = True
            record.completed_at = datetime.now(timezone.utc)

        await self._db.commit()
        return await self.get_status(tenant_id, user_id)

    async def skip(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        record = await self._get_or_create(tenant_id, user_id)
        record.is_completed = True
        record.completed_at = datetime.now(timezone.utc)
        await self._db.commit()
        return await self.get_status(tenant_id, user_id)

    async def mark_complete(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        return await self.skip(tenant_id, user_id)

    async def reset(self, tenant_id: uuid.UUID) -> dict:
        from app.domain.models.tenant import TenantOnboarding
        record = (await self._db.execute(
            select(TenantOnboarding).where(TenantOnboarding.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if record:
            record.completed_steps = []
            record.is_completed = False
            record.completed_at = None
            await self._db.commit()
        return {"message": "Onboarding reset successfully."}

    def get_config(self) -> list[dict]:
        return ONBOARDING_STEPS


# ── Editions Service ──────────────────────────────────────────────────────────

class EditionsService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_all(self):
        from app.domain.models.subscription import Edition
        return list((await self._db.execute(
            select(Edition).order_by(Edition.sort_order, Edition.display_name)
        )).scalars().all())

    async def get_public(self):
        """Return publicly visible editions (for registration paywall)."""
        from app.domain.models.subscription import Edition
        return list((await self._db.execute(
            select(Edition).where(Edition.is_public.is_(True)).order_by(Edition.sort_order, Edition.display_name)
        )).scalars().all())

    async def get_for_select(self):
        from app.domain.models.subscription import Edition
        editions = list((await self._db.execute(
            select(Edition).order_by(Edition.sort_order, Edition.display_name)
        )).scalars().all())
        return [{"id": str(e.id), "display_name": e.display_name} for e in editions]

    async def get(self, edition_id: uuid.UUID):
        from app.domain.models.subscription import Edition
        e = (await self._db.execute(
            select(Edition).where(Edition.id == edition_id)
        )).scalar_one_or_none()
        if not e:
            raise NotFoundException("Edition", str(edition_id))
        return e

    async def create(
        self,
        display_name: str,
        is_free: bool = False,
        price_monthly: float = 0,
        price_annually: float = 0,
        currency: str = "USD",
        sort_order: int = 0,
        is_public: bool = True,
        trial_day_count: Optional[int] = None,
        is_trial_active: bool = False,
    ):
        from app.domain.models.subscription import Edition
        edition = Edition(
            id=uuid.uuid4(),
            display_name=display_name,
            is_free=is_free,
            price_monthly=price_monthly,
            price_annually=price_annually,
            currency=currency,
            sort_order=sort_order,
            is_public=is_public,
            trial_day_count=trial_day_count,
            is_trial_active=is_trial_active,
        )
        self._db.add(edition)
        await self._db.commit()
        await self._db.refresh(edition)
        return edition

    async def update(self, edition_id: uuid.UUID, **kwargs):
        edition = await self.get(edition_id)
        for k, v in kwargs.items():
            if hasattr(edition, k) and v is not None:
                setattr(edition, k, v)
        await self._db.commit()
        await self._db.refresh(edition)
        return edition

    async def delete(self, edition_id: uuid.UUID) -> None:
        edition = await self.get(edition_id)
        await self._db.delete(edition)
        await self._db.commit()

    async def get_tenant_count(self, edition_id: uuid.UUID) -> int:
        from app.domain.models.tenant import Tenant
        result = await self._db.execute(
            select(func.count()).select_from(Tenant).where(Tenant.edition_id == edition_id)
        )
        return result.scalar_one()

    async def move_tenants(self, source_edition_id: uuid.UUID, target_edition_id: uuid.UUID) -> int:
        from app.domain.models.tenant import Tenant
        from sqlalchemy import update as sa_update
        # Verify target exists
        await self.get(target_edition_id)
        result = await self._db.execute(
            sa_update(Tenant)
            .where(Tenant.edition_id == source_edition_id)
            .values(edition_id=target_edition_id)
        )
        await self._db.commit()
        return result.rowcount

    # ── Edition features ──────────────────────────────────────────────────────

    async def get_features(self, edition_id: uuid.UUID):
        from app.domain.models.subscription import EditionFeature
        return list((await self._db.execute(
            select(EditionFeature)
            .where(EditionFeature.edition_id == edition_id)
            .order_by(EditionFeature.sort_order)
        )).scalars().all())

    async def add_feature(
        self,
        edition_id: uuid.UUID,
        feature_name: str,
        display_name: str,
        feature_value: Optional[str] = None,
        is_included: bool = True,
        sort_order: int = 0,
    ):
        from app.domain.models.subscription import EditionFeature
        # Ensure edition exists
        await self.get(edition_id)
        feat = EditionFeature(
            id=uuid.uuid4(),
            edition_id=edition_id,
            feature_name=feature_name,
            display_name=display_name,
            feature_value=feature_value,
            is_included=is_included,
            sort_order=sort_order,
        )
        self._db.add(feat)
        await self._db.commit()
        await self._db.refresh(feat)
        return feat

    async def update_feature(self, edition_id: uuid.UUID, feature_id: uuid.UUID, **kwargs):
        from app.domain.models.subscription import EditionFeature
        feat = (await self._db.execute(
            select(EditionFeature).where(
                EditionFeature.id == feature_id,
                EditionFeature.edition_id == edition_id,
            )
        )).scalar_one_or_none()
        if not feat:
            raise NotFoundException("EditionFeature", str(feature_id))
        for k, v in kwargs.items():
            if hasattr(feat, k) and v is not None:
                setattr(feat, k, v)
        await self._db.commit()
        await self._db.refresh(feat)
        return feat

    async def delete_feature(self, edition_id: uuid.UUID, feature_id: uuid.UUID) -> None:
        from app.domain.models.subscription import EditionFeature
        feat = (await self._db.execute(
            select(EditionFeature).where(
                EditionFeature.id == feature_id,
                EditionFeature.edition_id == edition_id,
            )
        )).scalar_one_or_none()
        if not feat:
            raise NotFoundException("EditionFeature", str(feature_id))
        await self._db.delete(feat)
        await self._db.commit()

    async def replace_features(self, edition_id: uuid.UUID, features: list[dict]) -> list:
        """Replace all features for an edition atomically."""
        from app.domain.models.subscription import EditionFeature
        from sqlalchemy import delete as sa_delete
        await self.get(edition_id)
        await self._db.execute(
            sa_delete(EditionFeature).where(EditionFeature.edition_id == edition_id)
        )
        result = []
        for i, f in enumerate(features):
            feat = EditionFeature(
                id=uuid.uuid4(),
                edition_id=edition_id,
                feature_name=f.get("feature_name", f.get("display_name", "")),
                display_name=f.get("display_name", ""),
                feature_value=f.get("feature_value"),
                is_included=f.get("is_included", True),
                sort_order=f.get("sort_order", i),
            )
            self._db.add(feat)
            result.append(feat)
        await self._db.commit()
        return result
