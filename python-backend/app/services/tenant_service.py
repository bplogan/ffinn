"""Tenant management service."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ConflictException, BusinessException
from app.domain.models.tenant import Tenant
from app.domain.models.identity import IdentityUser


class TenantService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_tenants(
        self, page: int = 1, page_size: int = 20, search: Optional[str] = None
    ) -> tuple[list[Tenant], int]:
        q = select(Tenant)
        if search:
            q = q.where(Tenant.name.ilike(f"%{search}%"))
        total = (await self._db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        items = (
            await self._db.execute(
                q.order_by(Tenant.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return list(items), total

    async def get_tenant(self, tenant_id: uuid.UUID) -> Tenant:
        result = await self._db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise NotFoundException("Tenant not found.")
        return tenant

    async def create_tenant(
        self,
        name: str,
        admin_email: str,
        admin_password: str,
        connection_string: Optional[str] = None,
        tenancy_name: Optional[str] = None,
        admin_first_name: Optional[str] = None,
        admin_last_name: Optional[str] = None,
    ) -> Tenant:
        admin_email = (admin_email or "").strip()
        if not admin_email or not admin_password:
            raise BusinessException("Admin email and password are required when creating a tenant")

        normalized = (tenancy_name or name).strip().lower()
        existing = await self._db.execute(select(Tenant).where(Tenant.name == name))
        if existing.scalar_one_or_none():
            raise ConflictException(f"Tenant '{name}' already exists.")
        dup_norm = await self._db.execute(select(Tenant).where(Tenant.normalized_name == normalized))
        if dup_norm.scalar_one_or_none():
            raise ConflictException(f"Tenancy name '{tenancy_name or name}' is already taken.")
        tenant = Tenant(
            id=uuid.uuid4(),
            name=name,
            normalized_name=normalized,
            connection_string=connection_string,
            admin_email_address=admin_email,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(tenant)
        await self._db.commit()
        await self._db.refresh(tenant)

        from app.services.role_service import seed_tenant_system_roles
        await seed_tenant_system_roles(self._db, tenant.id)

        from app.schemas.user_schemas import CreateUserRequest
        from app.services.user_service import UserService

        local_part = admin_email.split("@")[0] or "admin"
        await UserService(self._db).create_user(
            CreateUserRequest(
                user_name=local_part,
                email=admin_email,
                password=admin_password,
                first_name=admin_first_name or "Admin",
                last_name=admin_last_name or name,
                role_names=["Admin"],
            ),
            tenant_id=tenant.id,
        )

        return tenant

    async def update_tenant(self, tenant_id: uuid.UUID, **kwargs) -> Tenant:
        tenant = await self.get_tenant(tenant_id)
        for k, v in kwargs.items():
            if hasattr(tenant, k) and v is not None:
                setattr(tenant, k, v)
        await self._db.commit()
        await self._db.refresh(tenant)
        return tenant

    async def delete_tenant(self, tenant_id: uuid.UUID) -> None:
        tenant = await self.get_tenant(tenant_id)
        await self._db.delete(tenant)
        await self._db.commit()

    async def get_by_name(self, name: str) -> Optional[Tenant]:
        normalized = name.lower()
        result = await self._db.execute(
            select(Tenant).where(Tenant.normalized_name == normalized)
        )
        return result.scalar_one_or_none()

    async def toggle_status(self, tenant_id: uuid.UUID, is_active: bool) -> Tenant:
        tenant = await self.get_tenant(tenant_id)
        tenant.is_active = is_active
        tenant.is_available = is_active
        await self._db.commit()
        await self._db.refresh(tenant)
        return tenant

    async def get_tenant_users(
        self, tenant_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[IdentityUser], int]:
        q = select(IdentityUser).where(IdentityUser.tenant_id == tenant_id)
        total = (await self._db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        items = (
            await self._db.execute(
                q.offset((page - 1) * page_size).limit(page_size)
            )
        ).scalars().all()
        return list(items), total
