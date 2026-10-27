"""Role management service."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ConflictException, ForbiddenException
from app.core.permissions import Roles as RoleNames
from app.domain.models.identity import IdentityRole, IdentityRoleClaim


class RoleService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_roles(self, tenant_id: Optional[uuid.UUID] = None) -> list[IdentityRole]:
        q = select(IdentityRole)
        if tenant_id:
            q = q.where(IdentityRole.tenant_id == tenant_id)
        return list((await self._db.execute(q.order_by(IdentityRole.name))).scalars().all())

    async def get_role(self, role_id: uuid.UUID) -> IdentityRole:
        result = await self._db.execute(select(IdentityRole).where(IdentityRole.id == role_id))
        role = result.scalar_one_or_none()
        if not role:
            raise NotFoundException("Role not found.")
        return role

    async def create_role(
        self, name: str, tenant_id: Optional[uuid.UUID] = None, permissions: Optional[list[str]] = None
    ) -> IdentityRole:
        existing = await self._db.execute(
            select(IdentityRole).where(
                IdentityRole.tenant_id == tenant_id,
                IdentityRole.normalized_name == name.upper(),
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException(f"Role '{name}' already exists.")
        role = IdentityRole(
            id=uuid.uuid4(),
            name=name,
            normalized_name=name.upper(),
            tenant_id=tenant_id,
        )
        self._db.add(role)
        await self._db.flush()

        for perm in permissions or []:
            self._db.add(IdentityRoleClaim(
                role_id=role.id, claim_type="Permission", claim_value=perm
            ))
        await self._db.commit()
        await self._db.refresh(role)
        return role

    async def update_role(
        self, role_id: uuid.UUID, name: Optional[str] = None, permissions: Optional[list[str]] = None
    ) -> IdentityRole:
        role = await self.get_role(role_id)
        if name and role.is_system and role.normalized_name != name.upper():
            raise ForbiddenException("System roles cannot be renamed.")
        if name:
            role.name = name
            role.normalized_name = name.upper()
        if permissions is not None:
            await self._db.execute(
                delete(IdentityRoleClaim).where(
                    IdentityRoleClaim.role_id == role_id,
                    IdentityRoleClaim.claim_type == "Permission",
                )
            )
            for perm in permissions:
                self._db.add(IdentityRoleClaim(
                    role_id=role_id, claim_type="Permission", claim_value=perm
                ))
        await self._db.commit()
        await self._db.refresh(role)
        return role

    async def delete_role(self, role_id: uuid.UUID) -> None:
        role = await self.get_role(role_id)
        if role.is_system:
            raise ForbiddenException("System roles cannot be deleted.")
        await self._db.delete(role)
        await self._db.commit()

    async def get_role_permissions(self, role_id: uuid.UUID) -> list[str]:
        result = await self._db.execute(
            select(IdentityRoleClaim.claim_value).where(
                IdentityRoleClaim.role_id == role_id,
                IdentityRoleClaim.claim_type == "Permission",
            )
        )
        return list(result.scalars().all())

    async def grant_permission(self, role_id: uuid.UUID, permission: str) -> None:
        existing = await self._db.execute(
            select(IdentityRoleClaim).where(
                IdentityRoleClaim.role_id == role_id,
                IdentityRoleClaim.claim_type == "Permission",
                IdentityRoleClaim.claim_value == permission,
            )
        )
        if not existing.scalar_one_or_none():
            self._db.add(IdentityRoleClaim(
                role_id=role_id, claim_type="Permission", claim_value=permission
            ))
            await self._db.commit()

    async def revoke_permission(self, role_id: uuid.UUID, permission: str) -> None:
        await self._db.execute(
            delete(IdentityRoleClaim).where(
                IdentityRoleClaim.role_id == role_id,
                IdentityRoleClaim.claim_type == "Permission",
                IdentityRoleClaim.claim_value == permission,
            )
        )
        await self._db.commit()


async def seed_tenant_system_roles(db, tenant_id: uuid.UUID) -> None:
    """Create the Admin and User system roles for a newly created tenant.

    These roles are marked is_system=True and cannot be deleted or renamed.
    Safe to call multiple times — skips roles that already exist.
    """
    _SYSTEM_ROLES = {
        RoleNames.ADMIN: RoleNames.DEFAULT_ROLE_PERMISSIONS[RoleNames.ADMIN],
        RoleNames.USER: RoleNames.DEFAULT_ROLE_PERMISSIONS[RoleNames.USER],
    }
    for role_name, perms in _SYSTEM_ROLES.items():
        existing = (await db.execute(
            select(IdentityRole).where(
                IdentityRole.tenant_id == tenant_id,
                IdentityRole.normalized_name == role_name.upper(),
            )
        )).scalar_one_or_none()
        if existing:
            continue
        role = IdentityRole(
            id=uuid.uuid4(),
            name=role_name,
            normalized_name=role_name.upper(),
            tenant_id=tenant_id,
            is_system=True,
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
