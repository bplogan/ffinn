"""
Two-factor authentication routes.

Endpoints:
  GET  /api/2fa/status                 — get current 2FA status
  POST /api/2fa/setup                  — generate TOTP secret + QR code
  POST /api/2fa/verify                 — enable 2FA (verify first TOTP code)
  POST /api/2fa/disable                — disable 2FA (requires password)
  POST /api/2fa/recovery-codes/regenerate  — regenerate backup codes
  POST /api/2fa/verify-login           — complete 2FA login (anonymous)
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import DBSession, get_current_user, CurrentUser
from app.core.security_middleware import build_rate_limit_dep, check_rate_limit_by_key
from app.domain.models.identity import IdentityUser, IdentityUserRole
from app.services.auth_service import AuthService
from app.services.host_settings import HostSettings
from app.services.identity_services import TwoFactorService
from app.api.auth import _public_auth_result


router = APIRouter(prefix="/api/2fa", tags=["Two-Factor Auth"])


async def _require_2fa_feature(db: DBSession) -> None:
    hs = await HostSettings.load(db)
    if not hs.two_factor_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Two-factor authentication is disabled.")


# ── Request / Response Models ─────────────────────────────────────────────────

class VerifyCodeRequest(BaseModel):
    code: str


class VerifyLoginRequest(BaseModel):
    user_id: uuid.UUID
    code: str
    is_recovery: bool = False


class DisableRequest(BaseModel):
    """Accept either a TOTP code (preferred) or account password."""
    code: Optional[str] = None
    password: Optional[str] = None

    def validate_has_credential(self) -> None:
        if not self.code and not self.password:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Provide either 'code' (TOTP) or 'password'.")


class RegenerateCodesRequest(BaseModel):
    code: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status(
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return the current 2FA status for the authenticated user."""
    svc = TwoFactorService(db)
    result = await svc.get_status(current_user.id)
    return {
        "isEnabled": result["is_enabled"],
        "hasAuthenticator": result["is_enabled"],
        "hasBackupCodes": result["has_backup_codes"],
    }


@router.post("/setup")
async def setup(
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
):
    await _require_2fa_feature(db)
    """
    Generate a TOTP secret and QR code for the authenticated user.
    The secret is saved but 2FA is NOT enabled until /verify is called.
    """
    svc = TwoFactorService(db)
    result = await svc.setup(current_user.id)
    return {
        "sharedKey": result["secret"],
        "qrCodeUri": f"data:image/png;base64,{result['qr_image_base64']}",
        "authenticatorUri": result["qr_uri"],
    }


@router.post("/verify")
async def verify_and_enable(
    body: VerifyCodeRequest,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
):
    await _require_2fa_feature(db)
    """Verify the first TOTP code to confirm setup and enable 2FA."""
    svc = TwoFactorService(db)
    backup_codes = await svc.verify_and_enable(current_user.id, body.code)
    if backup_codes is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code.")
    # Return plaintext backup codes once — they are stored hashed, never retrievable again
    return {
        "message": "Two-factor authentication has been enabled.",
        "recoveryCodes": backup_codes,
    }


@router.post("/disable")
async def disable(
    body: DisableRequest,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Disable 2FA using a TOTP code or account password."""
    body.validate_has_credential()
    svc = TwoFactorService(db)
    if body.code:
        success = await svc.disable_with_code(current_user.id, body.code)
    else:
        success = await svc.disable(current_user.id, body.password)  # type: ignore[arg-type]
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code or password.")
    return {"message": "Two-factor authentication has been disabled."}


@router.post("/recovery-codes/regenerate")
async def regenerate_recovery_codes(
    body: RegenerateCodesRequest,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Regenerate backup/recovery codes (invalidates previous codes). Requires TOTP."""
    await _require_2fa_feature(db)
    svc = TwoFactorService(db)
    codes = await svc.regenerate_backup_codes(current_user.id, totp_code=body.code)
    return {"recovery_codes": codes}


@router.post("/verify-login", dependencies=[Depends(build_rate_limit_dep(5, 60))])
async def verify_login(
    body: VerifyLoginRequest,
    db: DBSession,
    response: Response,
):
    """
    Verify a 2FA code during the login flow and issue JWT tokens on success.
    Pass is_recovery=true to use a backup/recovery code.

    Rate-limited: 5 attempts per IP per 60 s, and 5 attempts per user_id per 60 s.
    """
    check_rate_limit_by_key(str(body.user_id), max_requests=5, window_seconds=60)
    svc = TwoFactorService(db)
    valid = await svc.verify_login_code(body.user_id, body.code, body.is_recovery)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid 2FA code.")

    user = (await db.execute(
        select(IdentityUser)
        .options(selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role))
        .where(IdentityUser.id == body.user_id)
    )).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user.")

    hs = await HostSettings.load(db)
    auth_svc = AuthService(db, email_service=hs.build_email_service(), host_settings=hs)
    result = await auth_svc._build_auth_response(user)
    return _public_auth_result(result, response)
