"""
SSO (Single Sign-On) configuration routes + service.
Mirrors SsoController.cs.

Routes:
  GET    /api/sso                       - list configs for current tenant (Settings.Security)
  GET    /api/sso/{id}                  - get single config (Settings.Security)
  POST   /api/sso                       - create config (Settings.Security)
  PUT    /api/sso/{id}                  - update config (Settings.Security)
  DELETE /api/sso/{id}                  - delete config (Settings.Security)
  GET    /api/sso/{id}/test             - get test URL (Settings.Security)
  GET    /api/sso/tenant/{tenantName}   - public: enabled providers for login page
  GET    /api/sso/login/{configId}      - public: initiate SSO login (redirects)
  GET|POST /api/sso/callback/{configId} - public: SSO callback handler
"""
from __future__ import annotations

import uuid
import structlog
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import DBSession, get_current_user, CurrentUser
from app.core.exceptions import BusinessException, ForbiddenException, ValidationException
from app.core.security import encrypt_value as _encrypt
from app.domain.models.identity import SsoConfiguration

router = APIRouter(prefix="/api/sso", tags=["SSO"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SsoConfigurationDto(BaseModel):
    id: uuid.UUID
    tenant_id: Optional[uuid.UUID]
    provider: str
    provider_name: str
    client_id: Optional[str]
    metadata_url: Optional[str]
    is_enabled: bool
    auto_provision_users: bool
    default_role: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SsoConfigurationDetailDto(SsoConfigurationDto):
    """Includes metadata_xml but NOT client_secret (never exposed)."""
    metadata_xml: Optional[str]


class CreateSsoConfigurationInput(BaseModel):
    provider: str  # SAML | OIDC
    provider_name: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None  # will be encrypted at rest
    metadata_url: Optional[str] = None
    metadata_xml: Optional[str] = None
    is_enabled: bool = True
    auto_provision_users: bool = True
    default_role: Optional[str] = None


class UpdateSsoConfigurationInput(BaseModel):
    provider_name: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None  # None = keep existing
    metadata_url: Optional[str] = None
    metadata_xml: Optional[str] = None
    is_enabled: Optional[bool] = None
    auto_provision_users: Optional[bool] = None
    default_role: Optional[str] = None


class SsoTestUrlDto(BaseModel):
    test_url: str
    config_id: uuid.UUID
    provider: str


class SsoTenantOptionsDto(BaseModel):
    tenant_name: str
    providers: list[SsoConfigurationDto]


# ── Service ───────────────────────────────────────────────────────────────────

class SsoService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_configurations(
        self, tenant_id: Optional[uuid.UUID]
    ) -> list[SsoConfiguration]:
        q = select(SsoConfiguration)
        if tenant_id:
            q = q.where(SsoConfiguration.tenant_id == tenant_id)
        return list((await self._db.execute(q)).scalars().all())

    async def get_configuration(self, config_id: uuid.UUID) -> SsoConfiguration:
        obj = (
            await self._db.execute(
                select(SsoConfiguration).where(SsoConfiguration.id == config_id)
            )
        ).scalar_one_or_none()
        if obj is None:
            raise BusinessException("NOT_FOUND", f"SSO configuration '{config_id}' not found.")
        return obj

    async def create_configuration(
        self,
        inp: CreateSsoConfigurationInput,
        tenant_id: Optional[uuid.UUID],
    ) -> SsoConfiguration:
        if inp.provider not in ("SAML", "OIDC"):
            raise BusinessException("VALIDATION_ERROR", "provider must be 'SAML' or 'OIDC'.")
        if inp.provider == "SAML" and not inp.metadata_xml and not inp.metadata_url:
            raise BusinessException("VALIDATION_ERROR", "SAML requires metadata_xml or metadata_url.")
        if inp.provider == "OIDC" and not inp.client_id:
            raise BusinessException("VALIDATION_ERROR", "OIDC requires client_id.")

        encrypted_secret: str | None = None
        if inp.client_secret:
            encrypted_secret = _encrypt(inp.client_secret)  # raises RuntimeError if key not set

        obj = SsoConfiguration(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            provider=inp.provider,
            provider_name=inp.provider_name,
            client_id=inp.client_id,
            client_secret=encrypted_secret,
            metadata_url=inp.metadata_url,
            metadata_xml=inp.metadata_xml,
            is_enabled=inp.is_enabled,
            auto_provision_users=inp.auto_provision_users,
            default_role=inp.default_role,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(obj)
        await self._db.commit()
        await self._db.refresh(obj)
        return obj

    async def update_configuration(
        self,
        config_id: uuid.UUID,
        inp: UpdateSsoConfigurationInput,
    ) -> SsoConfiguration:
        obj = await self.get_configuration(config_id)
        if inp.provider_name is not None:
            obj.provider_name = inp.provider_name
        if inp.client_id is not None:
            obj.client_id = inp.client_id
        if inp.client_secret is not None:
            obj.client_secret = _encrypt(inp.client_secret)  # raises RuntimeError if key not set
        if inp.metadata_url is not None:
            obj.metadata_url = inp.metadata_url
        if inp.metadata_xml is not None:
            obj.metadata_xml = inp.metadata_xml
        if inp.is_enabled is not None:
            obj.is_enabled = inp.is_enabled
        if inp.auto_provision_users is not None:
            obj.auto_provision_users = inp.auto_provision_users
        if inp.default_role is not None:
            obj.default_role = inp.default_role
        obj.updated_at = datetime.now(timezone.utc)
        await self._db.commit()
        await self._db.refresh(obj)
        return obj

    async def delete_configuration(self, config_id: uuid.UUID) -> None:
        await self.get_configuration(config_id)  # raises NOT_FOUND if missing
        await self._db.execute(
            delete(SsoConfiguration).where(SsoConfiguration.id == config_id)
        )
        await self._db.commit()

    async def get_test_url(self, config_id: uuid.UUID) -> SsoTestUrlDto:
        obj = await self.get_configuration(config_id)
        if not obj.is_enabled:
            raise BusinessException("VALIDATION_ERROR", "SSO configuration is disabled.")
        # Build a test login URL pointing to our own initiate endpoint
        base = settings.app_url.rstrip("/")
        return SsoTestUrlDto(
            test_url=f"{base}/api/sso/login/{config_id}?returnUrl=/auth/callback",
            config_id=config_id,
            provider=obj.provider,
        )

    async def get_tenant_sso_options(self, tenant_name: str) -> SsoTenantOptionsDto:
        from app.domain.models.tenant import Tenant
        from sqlalchemy import func, or_
        norm = tenant_name.strip().lower()
        tenant = (
            await self._db.execute(
                select(Tenant).where(
                    or_(
                        Tenant.normalized_name == norm,
                        func.lower(Tenant.name) == norm,
                    )
                )
            )
        ).scalar_one_or_none()
        if tenant is None:
            raise BusinessException("NOT_FOUND", f"Tenant '{tenant_name}' not found.")
        configs = await self.get_configurations(tenant_id=tenant.id)
        enabled = [c for c in configs if c.is_enabled]
        return SsoTenantOptionsDto(
            tenant_name=tenant_name,
            providers=enabled,  # type: ignore[arg-type]
        )

    async def initiate_sso_login(
        self, config_id: uuid.UUID, return_url: Optional[str]
    ) -> str:
        """Return the IdP redirect URL for the given SSO config."""
        from app.services.sso_login_service import SsoLoginService

        obj = await self.get_configuration(config_id)
        if not obj.is_enabled:
            raise BusinessException("VALIDATION_ERROR", "SSO configuration is disabled.")
        return await SsoLoginService(self._db).initiate_login(obj, return_url)

    async def handle_sso_callback(
        self,
        config_id: uuid.UUID,
        code: Optional[str],
        state: Optional[str],
    ) -> dict:
        """Exchange OIDC auth code, provision/login user, return JWT access token."""
        from app.services.sso_login_service import SsoLoginService

        if not code:
            return {"success": False, "token": None, "refresh_token": None, "error": "No authorization code received."}

        config = await self.get_configuration(config_id)
        if not config.is_enabled:
            return {"success": False, "token": None, "refresh_token": None, "error": "SSO configuration is disabled."}

        login_svc = SsoLoginService(self._db)
        try:
            auth_state = await login_svc.consume_state(state, config_id)
            profile = await login_svc.exchange_code_and_fetch_profile(
                config, code, auth_state.code_verifier or ""
            )
        except (BusinessException, ValidationException) as e:
            return {"success": False, "token": None, "refresh_token": None, "error": str(e)}

        return await self._login_sso_profile(config, profile)

    async def handle_saml_callback(
        self,
        config_id: uuid.UUID,
        saml_response: str,
        relay_state: Optional[str],
    ) -> dict:
        """Validate SAML assertion and return JWT access token."""
        from app.services.sso_login_service import SsoLoginService

        config = await self.get_configuration(config_id)
        if not config.is_enabled:
            return {"success": False, "token": None, "refresh_token": None, "error": "SSO configuration is disabled."}
        if config.provider != "SAML":
            return {"success": False, "token": None, "refresh_token": None, "error": "This endpoint is for SAML providers only."}

        login_svc = SsoLoginService(self._db)
        try:
            profile = await login_svc.process_saml_response(config, saml_response, relay_state)
        except (BusinessException, ValidationException) as e:
            return {"success": False, "token": None, "refresh_token": None, "error": str(e)}

        return await self._login_sso_profile(config, profile)

    async def _login_sso_profile(self, config: SsoConfiguration, profile: dict) -> dict:
        from app.services.auth_service import AuthService
        from app.services.host_settings import HostSettings

        hs = await HostSettings.load(self._db)
        auth_svc = AuthService(self._db, email_service=hs.build_email_service(), host_settings=hs)
        try:
            user = await auth_svc.login_or_provision_sso_user(
                email=profile["email"],
                tenant_id=config.tenant_id,
                first_name=profile.get("name"),
                last_name=profile.get("surname"),
                auto_provision=config.auto_provision_users,
                default_role=config.default_role,
            )
            tokens = await auth_svc._build_auth_response(user)
        except BusinessException as e:
            return {"success": False, "token": None, "refresh_token": None, "error": e.message}

        return {
            "success": True,
            "exchange_code": await auth_svc.create_sso_exchange_code(user.id),
            "refresh_token": tokens.get("refresh_token"),
            "error": None,
        }


# ── Route helpers ─────────────────────────────────────────────────────────────

def _require_security_policy(user: CurrentUser) -> None:
    """Enforces Settings.Security policy — admin or security-role required."""
    if not user.is_admin() and not user.has_permission("Settings.Security"):
        raise ForbiddenException("Settings.Security permission required.")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[SsoConfigurationDto])
async def get_configurations(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_security_policy(current_user)
    svc = SsoService(db)
    return await svc.get_configurations(tenant_id=current_user.tenant_id)


@router.get("/tenant/{tenant_name}", response_model=SsoTenantOptionsDto)
async def get_tenant_sso_options(tenant_name: str, db: DBSession):
    """Public — used by the Angular login page to show available SSO providers."""
    svc = SsoService(db)
    return await svc.get_tenant_sso_options(tenant_name)


@router.get("/login/{config_id}")
async def initiate_sso_login(
    config_id: uuid.UUID,
    db: DBSession,
    return_url: Optional[str] = Query(default=None),
):
    """Public — redirects the browser to the IdP login page."""
    svc = SsoService(db)
    redirect_url = await svc.initiate_sso_login(config_id, return_url)
    return RedirectResponse(url=redirect_url)


@router.get("/sp/{config_id}")
async def get_sp_metadata(config_id: uuid.UUID, db: DBSession):
    """Public — SAML service provider metadata for IdP configuration."""
    from fastapi.responses import Response as FastAPIResponse
    from app.services.saml_login_service import SamlLoginService

    svc = SsoService(db)
    config = await svc.get_configuration(config_id)
    if config.provider != "SAML":
        raise BusinessException("VALIDATION_ERROR", "SP metadata is only available for SAML configurations.")
    xml = await SamlLoginService(db).get_sp_metadata(config)
    return FastAPIResponse(content=xml, media_type="application/xml")


@router.get("/callback/{config_id}")
@router.post("/callback/{config_id}")
async def handle_sso_callback(
    config_id: uuid.UUID,
    db: DBSession,
    response: Response,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    SAMLResponse: Optional[str] = Form(default=None),
    RelayState: Optional[str] = Form(default=None),
):
    """Public — handles the IdP redirect back after authentication (OIDC GET or SAML POST)."""
    from app.api.auth import _set_refresh_cookie
    from urllib.parse import quote

    frontend_base = settings.app_url.rstrip("/")
    svc = SsoService(db)

    if error:
        # The IdP-supplied text is never echoed back into the redirect URL.
        structlog.get_logger(__name__).warning("sso_idp_error", config_id=str(config_id), error=error[:200])
        return RedirectResponse(
            url=f"{frontend_base}/auth/login?error={quote('SSO provider returned an error.')}", status_code=302
        )

    if SAMLResponse:
        result = await svc.handle_saml_callback(config_id, SAMLResponse, RelayState)
    else:
        if not code:
            return RedirectResponse(
                url=f"{frontend_base}/auth/login?error={quote('No authorization code received from SSO provider.')}",
                status_code=302,
            )
        result = await svc.handle_sso_callback(config_id, code, state)

    if result.get("success") and result.get("exchange_code"):
        redirect = RedirectResponse(
            url=f"{frontend_base}/auth/login?sso_code={quote(result['exchange_code'])}", status_code=302
        )
        if result.get("refresh_token"):
            _set_refresh_cookie(redirect, result["refresh_token"])
        return redirect
    err_msg = result.get("error") or "SSO authentication failed."
    return RedirectResponse(
        url=f"{frontend_base}/auth/login?error={quote(err_msg)}", status_code=302
    )


@router.get("/{config_id}", response_model=SsoConfigurationDetailDto)
async def get_configuration(
    config_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_security_policy(current_user)
    svc = SsoService(db)
    return await svc.get_configuration(config_id)


@router.post("", response_model=SsoConfigurationDto, status_code=201)
async def create_configuration(
    body: CreateSsoConfigurationInput,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_security_policy(current_user)
    svc = SsoService(db)
    return await svc.create_configuration(body, tenant_id=current_user.tenant_id)


@router.put("/{config_id}", status_code=204)
async def update_configuration(
    config_id: uuid.UUID,
    body: UpdateSsoConfigurationInput,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_security_policy(current_user)
    svc = SsoService(db)
    await svc.update_configuration(config_id, body)
    return None


@router.delete("/{config_id}", status_code=204)
async def delete_configuration(
    config_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_security_policy(current_user)
    svc = SsoService(db)
    await svc.delete_configuration(config_id)
    return None


@router.get("/{config_id}/test", response_model=SsoTestUrlDto)
async def test_configuration(
    config_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_security_policy(current_user)
    svc = SsoService(db)
    return await svc.get_test_url(config_id)
