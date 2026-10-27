"""
Tenant logo upload/retrieval routes.

Endpoints:
  POST   /api/tenantlogo                  — upload / replace current tenant logo
  GET    /api/tenantlogo                  — get current tenant logo URL
  GET    /api/tenantlogo/{identifier}     — get logo by tenant name or ID (public)
  DELETE /api/tenantlogo                  — delete current tenant logo
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select

from app.core.dependencies import DBSession, get_current_user, CurrentUser, AdminUser
from app.domain.models.tenant import Tenant
from app.infrastructure.storage import StorageService, read_upload_capped

router = APIRouter(prefix="/api/tenantlogo", tags=["Tenant Logo"])

# SVG is intentionally excluded — it can contain inline scripts and would
# bypass our magic-byte sniff. Use raster formats only for logos.
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_LOGO_SIZE_MB = 2
_MAX_LOGO_BYTES = _MAX_LOGO_SIZE_MB * 1024 * 1024


async def _get_tenant(tenant_id: uuid.UUID, db: DBSession) -> Tenant:
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    return t


@router.post("")
async def upload_logo(
    db: DBSession,
    current_user: AdminUser,
    file: UploadFile = File(...),
):
    """Upload (or replace) the current tenant's logo. Admin only. Max 2 MB, images only."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant context.")

    content_type = file.content_type or ""
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{content_type}' is not allowed. Only images are accepted.",
        )

    content = await read_upload_capped(file, _MAX_LOGO_BYTES)

    storage = StorageService()
    try:
        meta = await storage.save_file(
            content=content,
            original_filename=file.filename or "logo",
            mime_type=content_type,
            tenant_id=str(current_user.tenant_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    tenant = await _get_tenant(current_user.tenant_id, db)
    tenant.logo_url = meta["url"]
    await db.commit()

    return {"logo_url": meta["url"]}


@router.get("")
async def get_logo(db: DBSession, current_user: CurrentUser = Depends(get_current_user)):
    """Return the logo URL for the current user's tenant."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant context.")
    tenant = await _get_tenant(current_user.tenant_id, db)
    return {"logo_url": tenant.logo_url}


@router.get("/{identifier}")
async def get_logo_by_identifier(
    identifier: str,
    db: DBSession,
):
    """
    Public endpoint — return the logo URL for a tenant identified by its ID
    (UUID string) or normalized name.
    """
    tenant = None

    # Try UUID first
    try:
        tid = uuid.UUID(identifier)
        tenant = (await db.execute(select(Tenant).where(Tenant.id == tid))).scalar_one_or_none()
    except ValueError:
        pass

    # Fall back to normalized name lookup
    if tenant is None:
        tenant = (await db.execute(
            select(Tenant).where(Tenant.normalized_name == identifier.lower())
        )).scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

    return {"logo_url": tenant.logo_url}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_logo(db: DBSession, current_user: AdminUser):
    """Remove the current tenant's logo URL."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant context.")
    tenant = await _get_tenant(current_user.tenant_id, db)
    tenant.logo_url = None
    await db.commit()
