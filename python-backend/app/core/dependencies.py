"""
FastAPI dependency injection providers.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Optional

import structlog
from fastapi import Depends, Header, Request, WebSocket
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError as JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.permissions import Roles as RolesConfig
from app.core.security import decode_token
from app.domain.models.identity import (
    IdentityUser,
    IdentityUserRole,
    IdentityUserToken,
    PermissionGrant,
)
from app.infrastructure.database import get_session

log = structlog.get_logger(__name__)

# OAuth2 scheme — token extracted from Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ── Database session ──────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    async for session in get_session():
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]


# ── Current user from JWT ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str
    username: str
    tenant_id: Optional[uuid.UUID]
    roles: tuple[str, ...]           # tuples are hashable/immutable
    permissions: tuple[str, ...]
    is_impersonating: bool = False
    impersonator_id: Optional[uuid.UUID] = None

    def is_in_role(self, *role_names: str) -> bool:
        return any(r in self.roles for r in role_names)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def is_admin(self) -> bool:
        return "Admin" in self.roles


async def resolve_current_user(token: str | None, db: AsyncSession) -> CurrentUser:
    """Decode JWT and validate against live DB state (stamp, roles, impersonation)."""
    if not token:
        raise UnauthorizedException()
    try:
        payload = decode_token(token)
    except JWTError as e:
        raise UnauthorizedException("Invalid or expired token") from e

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Invalid token payload")

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise UnauthorizedException("Invalid user ID in token")

    result = await db.execute(
        select(IdentityUser)
        .options(selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role))
        .where(IdentityUser.id == uid)
    )
    db_user = result.scalar_one_or_none()
    if not db_user or not db_user.is_active:
        raise UnauthorizedException("User not found or inactive.")

    token_stamp = payload.get("sec") or ""
    if (db_user.security_stamp or "") != token_stamp:
        raise UnauthorizedException("Token has been revoked.")

    jti = payload.get("jti")
    if payload.get("impersonating") or payload.get("impersonator_id"):
        revoked = (await db.execute(
            select(IdentityUserToken).where(
                IdentityUserToken.login_provider == "ffinn",
                IdentityUserToken.name == f"impersonation_revoked:{jti}",
            )
        )).scalar_one_or_none()
        if revoked:
            raise UnauthorizedException("Impersonation session ended.")

    role_names = [ur.role.name for ur in db_user.roles if ur.role]
    perms_result = await db.execute(
        select(PermissionGrant).where(
            PermissionGrant.user_id == db_user.id,
            PermissionGrant.is_granted == True,  # noqa: E712
        )
    )
    user_permissions = [pg.permission_name for pg in perms_result.scalars()]
    role_permissions: list[str] = []
    for role_name in role_names:
        role_permissions.extend(RolesConfig.DEFAULT_ROLE_PERMISSIONS.get(role_name, []))
    all_permissions = list(set(role_permissions + user_permissions))

    tenant_id_str = payload.get("tenant_id")
    try:
        tenant_id = uuid.UUID(tenant_id_str) if tenant_id_str else db_user.tenant_id
    except ValueError:
        tenant_id = db_user.tenant_id

    impersonator_str = payload.get("impersonator_id") or payload.get("impersonated_by")
    impersonator_id: Optional[uuid.UUID] = None
    if impersonator_str:
        try:
            impersonator_id = uuid.UUID(str(impersonator_str))
        except ValueError:
            pass

    is_impersonating = bool(payload.get("impersonating")) or impersonator_id is not None

    return CurrentUser(
        id=uid,
        email=db_user.email,
        username=db_user.user_name,
        tenant_id=tenant_id,
        roles=tuple(role_names),
        permissions=tuple(all_permissions),
        is_impersonating=is_impersonating,
        impersonator_id=impersonator_id,
    )


def _extract_current_user(token: str | None) -> CurrentUser:
    """Decode JWT only — prefer resolve_current_user for DB-backed validation."""
    if not token:
        raise UnauthorizedException()
    try:
        payload = decode_token(token)
    except JWTError as e:
        raise UnauthorizedException("Invalid or expired token") from e

    user_id = payload.get("sub")
    email = payload.get("email")
    username = payload.get("username")
    if not user_id or not email or not username:
        raise UnauthorizedException("Invalid token payload")

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise UnauthorizedException("Invalid user ID in token")

    tenant_id_str = payload.get("tenant_id")
    try:
        tenant_id = uuid.UUID(tenant_id_str) if tenant_id_str else None
    except ValueError:
        raise UnauthorizedException("Invalid tenant ID in token")

    impersonator_str = payload.get("impersonator_id") or payload.get("impersonated_by")
    impersonator_id: Optional[uuid.UUID] = None
    if impersonator_str:
        try:
            impersonator_id = uuid.UUID(str(impersonator_str))
        except ValueError:
            pass

    is_impersonating = bool(payload.get("impersonating")) or impersonator_id is not None

    return CurrentUser(
        id=uid,
        email=email,
        username=username,
        tenant_id=tenant_id,
        roles=tuple(payload.get("roles", [])),
        permissions=tuple(payload.get("permissions", [])),
        is_impersonating=is_impersonating,
        impersonator_id=impersonator_id,
    )


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: DBSession,
) -> CurrentUser:
    """Dependency: require authenticated user with live DB validation."""
    return await resolve_current_user(token, db)


async def get_optional_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: DBSession,
) -> Optional[CurrentUser]:
    """Dependency: return user if authenticated, else None."""
    if not token:
        return None
    try:
        return await resolve_current_user(token, db)
    except UnauthorizedException:
        return None


def require_roles(*role_names: str):
    """Dependency factory: require one of the specified roles."""
    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.is_in_role(*role_names):
            raise ForbiddenException(
                f"This action requires one of the following roles: {', '.join(role_names)}"
            )
        return user
    return _dep


def require_permission(permission: str):
    """Dependency factory: require a specific permission."""
    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.has_permission(permission) and not user.is_admin():
            raise ForbiddenException(f"Missing required permission: {permission}")
        return user
    return _dep


# ── Tenant context ────────────────────────────────────────────────────────────
async def get_tenant_id(
    request: Request,
    user: Optional[CurrentUser] = Depends(get_optional_user),
) -> Optional[uuid.UUID]:
    """Resolve tenant ID from: JWT > X-Tenant-Id header > cookie."""
    # From authenticated user (most reliable)
    if user and user.tenant_id:
        return user.tenant_id

    # From header
    tenant_header = request.headers.get("X-Tenant-Id")
    if tenant_header:
        try:
            return uuid.UUID(tenant_header)
        except ValueError:
            pass

    # From cookie
    tenant_cookie = request.cookies.get("TenantId")
    if tenant_cookie:
        try:
            return uuid.UUID(tenant_cookie)
        except ValueError:
            pass

    return None


# ── AI Agent callback auth ────────────────────────────────────────────────────
async def verify_callback_token(
    db: DBSession,
    x_callback_token: Annotated[str | None, Header()] = None,
) -> bool:
    """Verify the X-Callback-Token header for CI/CD callbacks."""
    from app.services.misc_services import SettingsService

    expected = settings.callback_token
    if not expected:
        expected = await SettingsService(db).get_setting("AIAgent.CallbackToken") or ""
    if not expected:
        raise ForbiddenException("Callback token not configured")
    if x_callback_token != expected:
        raise ForbiddenException("Invalid callback token")
    return True


# ── WebSocket auth ────────────────────────────────────────────────────────────
async def get_ws_user(websocket: WebSocket) -> Optional[CurrentUser]:
    """Extract user from WebSocket query param token."""
    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        return _extract_current_user(token)
    except UnauthorizedException:
        return None


async def require_host_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Platform host only — AI Agent and similar tools are not for tenant users."""
    if user.tenant_id is not None:
        raise ForbiddenException("This feature is only available to platform administrators.")
    return user


# Typed shorthand aliases
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
HostUser = Annotated[CurrentUser, Depends(require_host_user)]
AdminUser = Annotated[CurrentUser, Depends(require_roles("Admin"))]
