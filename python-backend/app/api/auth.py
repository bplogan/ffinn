"""Auth routes — mirrors AuthController.cs."""
from __future__ import annotations

import uuid
from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.dependencies import DBSession, get_current_user, CurrentUser
from app.core.security_middleware import build_rate_limit_dep
from app.core.config import settings
from app.core.app_url import resolve_frontend_url
from app.core.exceptions import UnauthorizedException
from app.schemas.auth_schemas import (
    LoginRequest, LoginResponse, RegisterRequest, TokenResponse, RefreshRequest,
    ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest,
    ConfirmEmailRequest, AuthUserInfo,
)
from app.services.auth_service import AuthService
from app.services.host_settings import HostSettings
from app.services.user_service import UserService
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["Auth"])
log = structlog.get_logger(__name__)

_REFRESH_COOKIE = "ffinn_refresh"
_REFRESH_COOKIE_PATH = "/api/auth/refresh"  # Scoped: only sent to this endpoint


def _refresh_cookie_kwargs() -> dict:
    """Compute SameSite/Secure based on environment.

    - Development: Lax + Secure=False so the cookie works over http://localhost.
    - Production:  None + Secure=True so the cookie is sent on cross-site SPA → API
      calls (frontend on Static Web Apps, API on a different registrable domain).
      Strict would block these cross-site requests entirely.
    """
    if settings.is_development:
        return {"samesite": "lax", "secure": False}
    return {"samesite": "none", "secure": True}


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Attach an HttpOnly refresh-token cookie to *response*."""
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,            # Not accessible from JavaScript
        path=_REFRESH_COOKIE_PATH,
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        **_refresh_cookie_kwargs(),
    )


def _public_auth_result(result: dict, response: Response) -> dict:
    """Set refresh cookie and omit refresh_token from JSON body."""
    if "refresh_token" in result:
        _set_refresh_cookie(response, result["refresh_token"])
        result = {k: v for k, v in result.items() if k != "refresh_token"}
    return result


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(_REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH, **_refresh_cookie_kwargs())


class ImpersonateRequest(BaseModel):
    user_id: uuid.UUID
    tenant_id: Optional[uuid.UUID] = None


async def _make_auth_svc(db: DBSession) -> AuthService:
    """Load HostSettings and build an AuthService wired to DB-stored settings."""
    hs = await HostSettings.load(db)
    return AuthService(db, email_service=hs.build_email_service(), host_settings=hs)


@router.post("/login", response_model=LoginResponse, response_model_exclude_none=True,
             dependencies=[Depends(build_rate_limit_dep(10, 60))])
async def login(body: LoginRequest, db: DBSession, response: Response):
    svc = await _make_auth_svc(db)
    # body.tenant_name is the human-readable tenant name; resolve to a tenant_id
    # before passing into the service so the SQL filter compares UUIDs to UUIDs.
    tenant_id = None
    if body.tenant_name:
        from sqlalchemy import select as _sa_select
        from app.domain.models.tenant import Tenant
        tenant = (await db.execute(
            _sa_select(Tenant).where(Tenant.normalized_name == body.tenant_name.lower())
        )).scalar_one_or_none()
        if tenant is None:
            raise UnauthorizedException("Invalid username/email or password")
        tenant_id = tenant.id
    result = await svc.login(body.username_or_email, body.password, tenant_id)
    return _public_auth_result(result, response)


@router.post("/register", status_code=201,
             dependencies=[Depends(build_rate_limit_dep(5, 60))])
async def register(body: RegisterRequest, request: Request, db: DBSession):
    from app.services.host_settings import HostSettings
    from app.core.exceptions import BusinessException
    import uuid as _uuid
    hs = await HostSettings.load(db)
    edition_id = None
    if body.edition_id:
        try:
            edition_id = _uuid.UUID(body.edition_id)
        except ValueError:
            raise BusinessException("Invalid edition_id format.")
    if hs.paywall_enabled and edition_id is None:
        raise BusinessException("An edition must be selected before registering.")
    svc = await _make_auth_svc(db)
    result = await svc.register(
        username=body.resolved_user_name(),
        email=body.email,
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
        tenant_name=body.tenant_name,
        base_url=resolve_frontend_url(request, hs),
        edition_id=edition_id,
    )
    return result


@router.post("/refresh", response_model=TokenResponse,
             dependencies=[Depends(build_rate_limit_dep(20, 60))])
async def refresh(request: Request, body: RefreshRequest, db: DBSession, response: Response):
    svc = await _make_auth_svc(db)
    # Accept token from body (legacy/explicit) or httpOnly cookie (preferred)
    token = (body.refresh_token if body else None) or request.cookies.get(_REFRESH_COOKIE)
    if not token:
        raise UnauthorizedException("No refresh token provided")
    result = await svc.refresh_token(token)
    return _public_auth_result(result, response)


@router.post("/forgot-password",
             dependencies=[Depends(build_rate_limit_dep(5, 60))])
async def forgot_password(body: ForgotPasswordRequest, request: Request, db: DBSession):
    svc = await _make_auth_svc(db)
    await svc.forgot_password(body.email, resolve_frontend_url(request))
    return {"message": "If an account exists with that email, a reset link has been sent."}


@router.post("/reset-password",
             dependencies=[Depends(build_rate_limit_dep(5, 60))])
async def reset_password(body: ResetPasswordRequest, db: DBSession):
    svc = await _make_auth_svc(db)
    await svc.reset_password(body.token, body.new_password)
    return {"message": "Password reset successfully."}


@router.post("/set-password",
             dependencies=[Depends(build_rate_limit_dep(5, 60))])
async def set_password(body: ResetPasswordRequest, db: DBSession):
    """Set password from an invitation or one-time token (alias for reset-password)."""
    svc = await _make_auth_svc(db)
    await svc.reset_password(body.token, body.new_password)
    return {"message": "Password set successfully."}


@router.get("/validate-invitation")
async def validate_invitation(token: str, db: DBSession):
    """Validate an invitation/reset token and return pre-fill data for the UI."""
    svc = await _make_auth_svc(db)
    return await svc.validate_invitation_token(token)


@router.post("/change-password",
             dependencies=[Depends(build_rate_limit_dep(10, 60))])
async def change_password(
    body: ChangePasswordRequest,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    svc = await _make_auth_svc(db)
    await svc.change_password(current_user.id, body.current_password, body.new_password)
    return {"message": "Password changed successfully."}


@router.post("/confirm-email",
             dependencies=[Depends(build_rate_limit_dep(10, 60))])
async def confirm_email(body: ConfirmEmailRequest, db: DBSession):
    svc = await _make_auth_svc(db)
    await svc.confirm_email(body.token)
    return {"message": "Email confirmed successfully."}


@router.post("/resend-confirmation",
             dependencies=[Depends(build_rate_limit_dep(3, 60))])
async def resend_confirmation(body: ForgotPasswordRequest, request: Request, db: DBSession):
    svc = await _make_auth_svc(db)
    await svc.resend_confirmation_email(body.email, resolve_frontend_url(request))
    return {"message": "Confirmation email re-sent."}


@router.get("/me")
async def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    from app.core.permissions import Roles as RolesConfig
    from sqlalchemy import select
    from app.domain.models.identity import PermissionGrant, IdentityUser
    svc = UserService(db)
    user = await svc.get_user_profile(current_user.id)
    role_names = [ur.role.name for ur in user.roles if ur.role]
    # Role-based permissions
    role_permissions: list[str] = []
    for rn in role_names:
        role_permissions.extend(RolesConfig.DEFAULT_ROLE_PERMISSIONS.get(rn, []))
    # Per-user explicit permission grants
    grants_result = await db.execute(
        select(PermissionGrant).where(
            PermissionGrant.user_id == user.id,
            PermissionGrant.is_granted == True,  # noqa: E712
        )
    )
    user_permissions = [pg.permission_name for pg in grants_result.scalars()]
    all_permissions = list(set(role_permissions + user_permissions))
    impersonator_user_id: str | None = None
    impersonator_user_name: str | None = None
    if current_user.is_impersonating and current_user.impersonator_id:
        impersonator_user_id = str(current_user.impersonator_id)
        imp_result = await db.execute(
            select(IdentityUser).where(IdentityUser.id == current_user.impersonator_id)
        )
        impersonator = imp_result.scalar_one_or_none()
        if impersonator:
            impersonator_user_name = (
                f"{impersonator.name or ''} {impersonator.surname or ''}".strip()
                or impersonator.user_name
            )

    from app.services.identity_services import TwoFactorService
    tfa = await TwoFactorService(db).get_status(user.id)

    # Shown in the portal so people who belong to several organizations can tell which one is open
    tenant_name: str | None = None
    if user.tenant_id:
        from app.domain.models.tenant import Tenant
        tenant_name = (await db.execute(
            select(Tenant.name).where(Tenant.id == user.tenant_id)
        )).scalar_one_or_none()

    return AuthUserInfo(
        id=str(user.id),
        email=user.email,
        user_name=user.user_name,
        first_name=user.name,
        last_name=user.surname,
        full_name=f"{user.name or ''} {user.surname or ''}".strip() or None,
        roles=role_names,
        permissions=all_permissions,
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
        tenant_name=tenant_name,
        is_email_confirmed=user.email_confirmed,
        two_factor_enabled=tfa["is_enabled"],
        is_impersonating=current_user.is_impersonating,
        impersonator_user_id=impersonator_user_id,
        impersonator_user_name=impersonator_user_name,
    ).model_dump(by_alias=True)


class SsoExchangeRequest(BaseModel):
    code: str


@router.post("/sso/exchange", response_model=TokenResponse,
             dependencies=[Depends(build_rate_limit_dep(10, 60))])
async def sso_exchange(body: SsoExchangeRequest, db: DBSession, response: Response):
    """Exchange a one-time SSO code (from redirect) for an access token."""
    svc = await _make_auth_svc(db)
    result = await svc.exchange_sso_code(body.code)
    return _public_auth_result(result, response)


@router.post("/logout")
async def logout(
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    request: Request,
    response: Response,
):
    svc = await _make_auth_svc(db)
    revoke_id = current_user.impersonator_id or current_user.id
    await svc.revoke_refresh_token_for_user(revoke_id)
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token and current_user.is_impersonating:
        try:
            from app.core.security import decode_token
            payload = decode_token(token)
            jti = payload.get("jti")
            if jti:
                await svc.revoke_impersonation_jti(revoke_id, jti)
        except Exception:
            pass
    _clear_refresh_cookie(response)
    return {"message": "Logged out."}


@router.post("/impersonate",
             dependencies=[Depends(build_rate_limit_dep(10, 60))])
async def impersonate(
    body: ImpersonateRequest,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Admin impersonates another user — issues a short-lived token for that user."""
    svc = await _make_auth_svc(db)
    return await svc.impersonate(
        current_user.id,
        body.user_id,
        expected_tenant_id=body.tenant_id,
        actor_is_impersonating=current_user.is_impersonating,
        actor_impersonator_id=current_user.impersonator_id,
    )


@router.post("/end-impersonation")
async def end_impersonation(
    request: Request,
    db: DBSession,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """End impersonation session — revokes the impersonation JWT server-side."""
    if not current_user.is_impersonating:
        return {"message": "Not in an impersonation session."}
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token:
        from app.core.security import decode_token
        try:
            payload = decode_token(token)
            jti = payload.get("jti")
            actor_id = current_user.impersonator_id or current_user.id
            if jti and actor_id:
                svc = await _make_auth_svc(db)
                await svc.revoke_impersonation_jti(actor_id, jti)
        except Exception:
            pass
    return {"message": "Impersonation ended. Please restore your admin session."}


@router.get("/external-login/{provider}")
async def external_login(provider: str, db: DBSession, tenant_name: str = Query(default=None)):
    """Legacy route — redirects to the SSO login endpoint when a matching config exists."""
    from fastapi.responses import RedirectResponse
    from sqlalchemy import select
    from app.domain.models.identity import SsoConfiguration
    from app.domain.models.tenant import Tenant

    if not tenant_name:
        return {
            "message": "Provide tenant_name query parameter or use GET /api/sso/tenant/{tenantName} and /api/sso/login/{configId}.",
            "provider": provider,
            "status": "tenant_required",
        }

    tenant = (
        await db.execute(select(Tenant).where(
            (Tenant.normalized_name == tenant_name.lower()) |
            (Tenant.name.ilike(tenant_name))
        ))
    ).scalar_one_or_none()
    if tenant is None:
        return {"message": f"Tenant '{tenant_name}' not found.", "provider": provider, "status": "not_found"}

    configs = (
        await db.execute(
            select(SsoConfiguration).where(
                SsoConfiguration.tenant_id == tenant.id,
                SsoConfiguration.is_enabled == True,  # noqa: E712
            )
        )
    ).scalars().all()
    match = next(
        (c for c in configs if c.provider_name.lower() == provider.lower()),
        None,
    )
    if match is None:
        return {
            "message": f"No enabled SSO provider '{provider}' for tenant '{tenant_name}'.",
            "provider": provider,
            "status": "not_configured",
        }
    return RedirectResponse(url=f"/api/sso/login/{match.id}", status_code=302)


@router.get("/external-callback")
async def external_callback_get(code: str = None, state: str = None, error: str = None):
    """Legacy OAuth callback — use /api/sso/callback/{configId} instead."""
    from fastapi.responses import RedirectResponse
    from app.core.config import settings
    from urllib.parse import quote

    frontend = settings.app_url.rstrip("/")
    if error:
        log.warning("sso_external_callback_error", error=error[:200])
        return RedirectResponse(
            url=f"{frontend}/auth/login?error={quote('SSO provider returned an error.')}", status_code=302
        )
    return RedirectResponse(
        url=f"{frontend}/auth/login?error={quote('Use /api/sso/callback/{configId} for SSO login.')}",
        status_code=302,
    )


@router.post("/external-callback")
async def external_callback_post(request: Request):
    """Legacy OAuth callback — use /api/sso/callback/{configId} instead."""
    return {
        "message": "External callback is deprecated. Configure redirect URI to /api/sso/callback/{configId}.",
    }


@router.get("/external-providers")
async def external_providers(db: DBSession, tenant_name: str = Query(default=None)):
    """Return enabled SSO providers for a tenant (replaces hard-coded OAuth list)."""
    if not tenant_name:
        return []
    from app.api.sso import SsoService

    try:
        opts = await SsoService(db).get_tenant_sso_options(tenant_name)
        return [
            {
                "id": str(p.id),
                "name": p.provider_name,
                "provider": p.provider,
                "login_url": f"/api/sso/login/{p.id}",
            }
            for p in opts.providers
        ]
    except Exception as e:
        log.warning("external_providers lookup failed", tenant=tenant_name, error=str(e))
        return []
