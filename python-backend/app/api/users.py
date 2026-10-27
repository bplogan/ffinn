"""User management routes."""
from __future__ import annotations

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from pydantic import BaseModel

from app.core.dependencies import DBSession, get_current_user, CurrentUser, AdminUser
from app.core.app_url import resolve_frontend_url
from app.core.security_middleware import build_rate_limit_dep
from app.schemas.user_schemas import (
    UserResponse, CreateUserRequest, UpdateUserAdminRequest, PagedResult,
)
from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.schemas.auth_schemas import ChangePasswordRequest, ForgotPasswordRequest

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("", response_model=PagedResult)
async def list_users(
    db: DBSession,
    current_user: AdminUser,
    filter: str | None = Query(None),
    maxResultCount: int = Query(20, ge=1, le=100),
    skipCount: int = Query(0, ge=0),
    sorting: str | None = Query(None),
    role: str | None = Query(None),
):
    page_size = maxResultCount
    page = (skipCount // page_size) + 1
    svc = UserService(db)
    result = await svc.get_users(
        tenant_id=current_user.tenant_id,
        page=page,
        page_size=page_size,
        search=filter or None,
        role_name=role,
    )
    total = result["total"]
    return {
        "items": [UserResponse.model_validate(u) for u in result["items"]],
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


# ── Self-service profile endpoints (any authenticated user) ─────────────────

class UpdateProfileRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    body: UpdateProfileRequest,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Update the signed-in user's own profile (name / phone)."""
    svc = UserService(db)
    data: dict = {}
    if body.first_name is not None:
        data["name"] = body.first_name
    if body.last_name is not None:
        data["surname"] = body.last_name
    if body.phone_number is not None:
        data["phone_number"] = body.phone_number
    return await svc.update_user(
        current_user.id, data, requestor_id=current_user.id, is_admin=False
    )


@router.post("/me/avatar", response_model=UserResponse)
async def upload_my_avatar(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    """Upload / replace the signed-in user's avatar image."""
    from app.infrastructure.storage import StorageService, read_upload_capped
    _ALLOWED = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    _MAX_BYTES = 5 * 1024 * 1024  # 5 MB
    content_type = file.content_type or ""
    if content_type not in _ALLOWED:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Only JPEG/PNG/GIF/WebP images accepted.")
    content = await read_upload_capped(file, _MAX_BYTES)
    storage = StorageService()
    meta = await storage.save_file(
        content=content,
        original_filename=file.filename or "avatar",
        mime_type=content_type,
        tenant_id=str(current_user.tenant_id),
    )
    svc = UserService(db)
    user = await svc.get_user(current_user.id)
    user.profile_picture_url = meta["url"]
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, db: DBSession, current_user: AdminUser):
    svc = UserService(db)
    # Enforce tenant scope so a tenant admin can only see users in their own tenant.
    # Host admins (tenant_id is None) bypass the constraint.
    return await svc.get_user(
        user_id,
        tenant_id=current_user.tenant_id,
        enforce_tenant=current_user.tenant_id is not None,
    )


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    _: AdminUser,
):
    svc = UserService(db)
    return await svc.create_user(body, tenant_id=current_user.tenant_id)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserAdminRequest,
    db: DBSession,
    current_user: AdminUser,
):
    svc = UserService(db)
    # Tenant guard before mutating
    await svc.get_user(
        user_id,
        tenant_id=current_user.tenant_id,
        enforce_tenant=current_user.tenant_id is not None,
    )
    data: dict = {}
    if body.first_name is not None:
        data["name"] = body.first_name
    if body.last_name is not None:
        data["surname"] = body.last_name
    if body.is_active is not None:
        data["is_active"] = body.is_active

    user = await svc.update_user(
        user_id,
        data,
        requestor_id=current_user.id,
        is_admin=True,  # dependency already enforces admin role
    )

    if body.role_names is not None:
        await svc.assign_roles(user_id, body.role_names, current_user.tenant_id)

    return user


async def _tenant_guard(svc: UserService, user_id: uuid.UUID, current_user: CurrentUser) -> None:
    """Raise 404 if `user_id` does not belong to the admin's tenant. Host admins bypass."""
    await svc.get_user(
        user_id,
        tenant_id=current_user.tenant_id,
        enforce_tenant=current_user.tenant_id is not None,
    )


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: uuid.UUID, db: DBSession, current_user: AdminUser):
    svc = UserService(db)
    await _tenant_guard(svc, user_id, current_user)
    await svc.delete_user(user_id)


@router.post("/{user_id}/lock")
async def lock_user(user_id: uuid.UUID, db: DBSession, current_user: AdminUser):
    svc = UserService(db)
    await _tenant_guard(svc, user_id, current_user)
    await svc.deactivate_user(user_id)
    return {"message": "User locked."}


@router.post("/{user_id}/unlock")
async def unlock_user(user_id: uuid.UUID, db: DBSession, current_user: AdminUser):
    svc = UserService(db)
    await _tenant_guard(svc, user_id, current_user)
    await svc.unlock_user(user_id)
    return {"message": "User unlocked."}


@router.post("/{user_id}/activate")
async def activate_user(user_id: uuid.UUID, db: DBSession, current_user: AdminUser):
    svc = UserService(db)
    await _tenant_guard(svc, user_id, current_user)
    await svc.activate_user(user_id)
    return {"message": "User activated."}


@router.get("/{user_id}/roles")
async def get_user_roles(user_id: uuid.UUID, db: DBSession, current_user: AdminUser):
    svc = UserService(db)
    await _tenant_guard(svc, user_id, current_user)
    roles = await svc.get_user_roles(user_id)
    return {"roles": roles}


@router.put("/{user_id}/roles")
async def assign_roles(
    user_id: uuid.UUID,
    role_names: list[str],
    db: DBSession,
    current_user: AdminUser,
):
    svc = UserService(db)
    await _tenant_guard(svc, user_id, current_user)
    await svc.assign_roles(user_id, role_names, current_user.tenant_id)
    return {"message": "Roles updated."}


@router.post("/{user_id}/resend-confirmation")
async def resend_confirmation(
    user_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: AdminUser,
):
    """Admin resends email confirmation to a user."""
    from app.services.host_settings import HostSettings
    svc = UserService(db)
    await _tenant_guard(svc, user_id, current_user)
    user = await svc.get_user(user_id)
    hs = await HostSettings.load(db)
    auth_svc = AuthService(db, email_service=hs.build_email_service(), host_settings=hs)
    await auth_svc.resend_confirmation_email(user.email, resolve_frontend_url(request, hs))
    return {"message": "Confirmation email sent."}


@router.post("/{user_id}/resend-invitation")
async def resend_invitation(
    user_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: AdminUser,
):
    """Resend a pending invitation email to a user."""
    svc = UserService(db)
    await _tenant_guard(svc, user_id, current_user)
    user = await svc.get_user(user_id)
    from app.services.misc_services import TeamInvitationService
    inv_svc = TeamInvitationService(db)
    from sqlalchemy import select as sa_select
    from app.domain.models.tenant import TeamInvitation
    invitation = (await db.execute(
        sa_select(TeamInvitation)
        .where(
            TeamInvitation.email == user.email,
            TeamInvitation.tenant_id == current_user.tenant_id,
        )
        .order_by(TeamInvitation.created_at.desc())
    )).scalars().first()
    if invitation:
        await inv_svc.resend_invitation(
            invitation.id,
            invitation.tenant_id,
            base_url=resolve_frontend_url(request),
        )
    return {"message": "Invitation resent."}


@router.post("/{user_id}/reset-password")
async def admin_reset_password(
    user_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: AdminUser,
):
    """Admin triggers a password reset email for a user."""
    svc = UserService(db)
    await _tenant_guard(svc, user_id, current_user)
    await svc.admin_send_password_reset(user_id, resolve_frontend_url(request))
    return {"message": "Password reset email sent."}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Allow an authenticated user to change their own password (mirrors UsersController)."""
    svc = AuthService(db)
    await svc.change_password(current_user.id, body.current_password, body.new_password)
    return {"message": "Password changed successfully."}


@router.post("/forgot-password", dependencies=[Depends(build_rate_limit_dep(5, 60))])
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: DBSession,
):
    """Initiate a password-reset flow from the users context (mirrors UsersController)."""
    from app.services.host_settings import HostSettings
    hs = await HostSettings.load(db)
    svc = AuthService(db, email_service=hs.build_email_service(), host_settings=hs)
    await svc.forgot_password(body.email, resolve_frontend_url(request, hs))
    return {"message": "If an account exists with that email, a reset link has been sent."}
