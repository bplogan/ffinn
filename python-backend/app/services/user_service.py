"""
User management service.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessException, ConflictException, NotFoundException
from app.core.security import hash_password, generate_secure_token
from app.domain.models.identity import (
    IdentityUser, IdentityRole, IdentityUserRole, PermissionGrant,
)
from app.schemas.user_schemas import CreateUserRequest

log = structlog.get_logger(__name__)


class UserService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_users(
        self,
        tenant_id: Optional[uuid.UUID],
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> dict:
        query = select(IdentityUser).options(
            selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role)
        )
        if tenant_id is not None:
            query = query.where(IdentityUser.tenant_id == tenant_id)

        if search:
            s = f"%{search.upper()}%"
            query = query.where(
                (IdentityUser.normalized_user_name.like(s))
                | (IdentityUser.normalized_email.like(s))
            )
        if role_name:
            query = query.join(IdentityUser.roles).join(IdentityUserRole.role).where(
                IdentityRole.normalized_name == role_name.upper()
            )

        total = await self._db.scalar(
            select(func.count(1)).select_from(query.subquery())
        )
        users = await self._db.scalars(
            query.order_by(IdentityUser.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        return {"items": list(users), "total": total, "page": page, "page_size": page_size}

    async def get_user(
        self,
        user_id: uuid.UUID,
        tenant_id: Optional[uuid.UUID] = None,
        enforce_tenant: bool = False,
    ) -> IdentityUser:
        """Fetch a user by id.

        When `enforce_tenant` is True the query is constrained to `tenant_id`,
        which prevents IDOR across tenants for endpoints called by tenant
        administrators. Host-level admins (no tenant_id) bypass the filter.
        """
        stmt = (
            select(IdentityUser)
            .options(selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role))
            .where(IdentityUser.id == user_id)
        )
        if enforce_tenant and tenant_id is not None:
            stmt = stmt.where(IdentityUser.tenant_id == tenant_id)
        result = await self._db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException("User", str(user_id))
        return user

    async def get_user_profile(self, user_id: uuid.UUID) -> IdentityUser:
        return await self.get_user(user_id)

    async def update_user(
        self,
        user_id: uuid.UUID,
        data: dict,
        requestor_id: uuid.UUID,
        is_admin: bool = False,
    ) -> IdentityUser:
        user = await self.get_user(user_id)

        # Non-admins can only update their own profile
        if not is_admin and user_id != requestor_id:
            raise BusinessException("You can only update your own profile")

        allowed = {"name", "surname", "phone_number", "language", "timezone_id"}
        if is_admin:
            allowed |= {"user_name", "email", "is_active", "email_confirmed"}

        for field, value in data.items():
            if field not in allowed or value is None:
                continue
            if field == "user_name":
                user.user_name = value
                user.normalized_user_name = value.upper()
            elif field == "email":
                user.email = value
                user.normalized_email = value.upper()
            else:
                setattr(user, field, value)

        await self._db.commit()
        await self._db.refresh(user)
        return user

    async def delete_user(self, user_id: uuid.UUID) -> bool:
        user = await self.get_user(user_id)
        await self._db.delete(user)
        await self._db.commit()
        return True

    async def activate_user(self, user_id: uuid.UUID) -> IdentityUser:
        user = await self.get_user(user_id)
        user.is_active = True
        await self._db.commit()
        return user

    async def deactivate_user(self, user_id: uuid.UUID) -> IdentityUser:
        user = await self.get_user(user_id)
        user.is_active = False
        await self._db.commit()
        return user

    async def assign_roles(self, user_id: uuid.UUID, role_names: list[str], tenant_id: Optional[uuid.UUID]) -> bool:
        await self.get_user(user_id)

        # Remove existing roles
        existing = await self._db.execute(
            select(IdentityUserRole).where(IdentityUserRole.user_id == user_id)
        )
        for ur in existing.scalars():
            await self._db.delete(ur)

        # Assign new roles
        for role_name in role_names:
            role_result = await self._db.execute(
                select(IdentityRole).where(
                    IdentityRole.tenant_id == tenant_id,
                    IdentityRole.normalized_name == role_name.upper(),
                )
            )
            role = role_result.scalar_one_or_none()
            if role:
                self._db.add(IdentityUserRole(user_id=user_id, role_id=role.id))

        await self._db.commit()
        return True

    async def get_user_permissions(self, user_id: uuid.UUID) -> list[str]:
        """Get all effective permissions for a user."""
        user = await self.get_user(user_id)
        role_names = [ur.role.name for ur in user.roles if ur.role]

        from app.core.permissions import Roles as RolesConfig
        role_permissions: list[str] = []
        for role_name in role_names:
            role_permissions.extend(RolesConfig.DEFAULT_ROLE_PERMISSIONS.get(role_name, []))

        # Add user-specific grants
        result = await self._db.execute(
            select(PermissionGrant).where(
                PermissionGrant.user_id == user_id,
                PermissionGrant.is_granted == True,  # noqa: E712
            )
        )
        user_perms = [pg.permission_name for pg in result.scalars()]

        return list(set(role_permissions + user_perms))

    async def reset_user_password(self, user_id: uuid.UUID, new_password: str) -> bool:
        user = await self.get_user(user_id)
        user.password_hash = hash_password(new_password)
        user.security_stamp = generate_secure_token(16)
        await self._db.commit()
        return True

    async def unlock_user(self, user_id: uuid.UUID) -> IdentityUser:
        user = await self.get_user(user_id)
        user.lockout_end = None
        user.lockout_enabled = False
        user.access_failed_count = 0
        await self._db.commit()
        return user

    async def create_user(self, body: CreateUserRequest, tenant_id: Optional[uuid.UUID] = None) -> IdentityUser:
        """Admin-level user creation (bypasses registration flow)."""
        normalized_email = body.email.upper()
        normalized_username = body.user_name.upper()

        existing = await self._db.execute(
            select(IdentityUser).where(
                IdentityUser.tenant_id == tenant_id,
                (IdentityUser.normalized_email == normalized_email)
                | (IdentityUser.normalized_user_name == normalized_username),
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException("Email or username is already in use")

        user = IdentityUser(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_name=body.user_name,
            normalized_user_name=normalized_username,
            email=body.email,
            normalized_email=normalized_email,
            password_hash=hash_password(body.password),
            name=body.first_name,
            surname=body.last_name,
            email_confirmed=True,  # Admin-created users are pre-confirmed
            security_stamp=generate_secure_token(16),
            concurrency_stamp=generate_secure_token(16),
        )
        self._db.add(user)
        await self._db.flush()

        if body.role_names:
            await self.assign_roles(user.id, body.role_names, tenant_id)
        else:
            # Auto-assign the User role; prefer tenant-scoped, fall back to global
            from sqlalchemy import select as _select
            role_result = await self._db.execute(
                _select(IdentityRole).where(
                    IdentityRole.tenant_id == tenant_id,
                    IdentityRole.normalized_name == "USER",
                )
            )
            default_role = role_result.scalar_one_or_none()
            if default_role is None and tenant_id is not None:
                role_result = await self._db.execute(
                    _select(IdentityRole).where(
                        IdentityRole.tenant_id.is_(None),
                        IdentityRole.normalized_name == "USER",
                    )
                )
                default_role = role_result.scalar_one_or_none()
            if default_role:
                self._db.add(IdentityUserRole(user_id=user.id, role_id=default_role.id))
            await self._db.commit()

        return user

    async def get_user_roles(self, user_id: uuid.UUID) -> list[str]:
        """Return the list of role names assigned to a user."""
        user = await self.get_user(user_id)
        return [ur.role.name for ur in user.roles if ur.role]

    async def admin_send_password_reset(self, user_id: uuid.UUID, base_url: str) -> None:
        """Admin-triggered password reset: send a reset email to the user."""
        from app.core.security import generate_secure_token
        from app.domain.models.identity import PasswordResetToken
        from datetime import timedelta
        from app.services.host_settings import HostSettings

        user = await self.get_user(user_id)
        token_value = generate_secure_token(48)

        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token_value,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self._db.add(reset_token)
        await self._db.commit()

        hs = await HostSettings.load(self._db)
        email_svc = hs.build_email_service()
        await email_svc.send_password_reset(
            user.email, user.full_name, token_value, base_url=base_url
        )
