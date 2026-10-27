"""
Permissions management routes.

Endpoints:
  GET  /api/permissions/definitions   — list all known permission names
  GET  /api/permissions/role/{role_id}   — get grants for a role
  PUT  /api/permissions/role/{role_id}   — replace grants for a role
  GET  /api/permissions/user/{user_id}   — get grants for a user
  PUT  /api/permissions/user/{user_id}   — replace grants for a user
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.dependencies import DBSession, AdminUser
from app.services.identity_services import PermissionsService

router = APIRouter(prefix="/api/permissions", tags=["Permissions"])


# ── Request Models ────────────────────────────────────────────────────────────

class RoleGrantsRequest(BaseModel):
    permissions: list[str]
    tenant_id: Optional[uuid.UUID] = None


class UserGrantItem(BaseModel):
    name: str
    is_granted: bool = True


class UserGrantsRequest(BaseModel):
    permissions: list[UserGrantItem]
    tenant_id: Optional[uuid.UUID] = None


class PermissionUpdateItem(BaseModel):
    name: str
    is_granted: bool


class UpdatePermissionsInput(BaseModel):
    provider_name: str   # "R" = Role, "U" = User, "C" = Client
    provider_key: str    # role ID, user ID, or client ID
    permissions: list[PermissionUpdateItem]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def get_permissions(
    db: DBSession,
    _: AdminUser,
    provider_name: Optional[str] = Query(None, alias="providerName"),
    provider_key: Optional[str] = Query(None, alias="providerKey"),
):
    """
    Return all permission groups with grant status.
    Without query params: returns grants for the calling user.
    With providerName + providerKey: returns grants for that specific role/user/client.
    Mirrors .NET PermissionsController HttpGet (root).
    """
    from app.services.identity_services import PermissionsService
    svc = PermissionsService(db)
    all_names = await svc.get_all_permission_names()

    if provider_name and provider_key:
        # Provider-scoped query — return names granted to this provider
        try:
            pid = uuid.UUID(provider_key)
            if provider_name.upper() == "R":
                grants = await svc.get_grants_for_role(pid)
            elif provider_name.upper() == "U":
                grants = await svc.get_grants_for_user(pid, None)
            else:
                grants = []
            granted_set = {g.permission_name for g in grants if g.is_granted}
        except Exception:
            granted_set = set()
    else:
        granted_set = set(all_names)  # current-user fallback — all known names

    groups: dict[str, list] = {}
    for name in all_names:
        top = name.split(".")[0]
        groups.setdefault(top, []).append({"name": name, "is_granted": name in granted_set})

    return [
        {"name": g, "display_name": g, "permissions": perms}
        for g, perms in groups.items()
    ]


@router.put("")
async def update_permissions(body: UpdatePermissionsInput, db: DBSession, _: AdminUser):
    """
    Bulk-update permissions for a role (R), user (U), or client (C).
    Mirrors .NET PermissionsController HttpPut (root).
    """
    if body.provider_name.upper() not in ("R", "U", "C"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="provider_name must be R, U, or C.")

    svc = PermissionsService(db)
    pid = uuid.UUID(body.provider_key)
    perms = [{"name": p.name, "is_granted": p.is_granted} for p in body.permissions]

    if body.provider_name.upper() == "R":
        granted = [p["name"] for p in perms if p["is_granted"]]
        await svc.update_role_grants(pid, granted, None)
    elif body.provider_name.upper() == "U":
        await svc.update_user_grants(pid, perms, None)
    # C (client) — stub, no client model yet
    return None  # 204


@router.get("/definitions")
async def get_definitions(db: DBSession, _: AdminUser):
    """Return all distinct permission names currently in use."""
    svc = PermissionsService(db)
    names = await svc.get_all_permission_names()
    return {"items": names}


@router.get("/role/{role_id}")
async def get_role_grants(role_id: uuid.UUID, db: DBSession, _: AdminUser):
    """Return all permission grants assigned to a role."""
    svc = PermissionsService(db)
    grants = await svc.get_grants_for_role(role_id)
    return {
        "role_id": str(role_id),
        "items": [
            {"id": str(g.id), "permission_name": g.permission_name, "is_granted": g.is_granted}
            for g in grants
        ],
    }


@router.put("/role/{role_id}")
async def update_role_grants(role_id: uuid.UUID, body: RoleGrantsRequest, db: DBSession, _: AdminUser):
    """Replace all permission grants for a role."""
    svc = PermissionsService(db)
    await svc.update_role_grants(role_id, body.permissions, body.tenant_id)
    return {"message": "Role permissions updated."}


@router.get("/user/{user_id}")
async def get_user_grants(
    user_id: uuid.UUID,
    db: DBSession,
    _: AdminUser,
    tenant_id: Optional[uuid.UUID] = Query(None),
):
    """Return all explicit permission grants for a user."""
    svc = PermissionsService(db)
    grants = await svc.get_grants_for_user(user_id, tenant_id)
    return {
        "user_id": str(user_id),
        "items": [
            {"id": str(g.id), "permission_name": g.permission_name, "is_granted": g.is_granted}
            for g in grants
        ],
    }


@router.put("/user/{user_id}")
async def update_user_grants(user_id: uuid.UUID, body: UserGrantsRequest, db: DBSession, _: AdminUser):
    """Replace all explicit permission grants for a user."""
    svc = PermissionsService(db)
    perms = [{"name": p.name, "is_granted": p.is_granted} for p in body.permissions]
    await svc.update_user_grants(user_id, perms, body.tenant_id)
    return {"message": "User permissions updated."}
