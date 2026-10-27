"""
OIDC SSO login — authorization redirect, token exchange, and user provisioning.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BusinessException, ValidationException
from app.core.security import decrypt_value
from app.domain.models.identity import SsoAuthState, SsoConfiguration

log = structlog.get_logger(__name__)

# Well-known OIDC issuer roots (admin UI presets map here)
OIDC_ISSUER_PRESETS: dict[str, str] = {
    "google": "https://accounts.google.com",
    "microsoft": "https://login.microsoftonline.com/common/v2.0",
    "auth0": "",  # custom metadata_url required
    "okta": "",   # custom metadata_url required
    "custom": "",
}


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _normalize_issuer(metadata_url: str) -> str:
    url = metadata_url.strip().rstrip("/")
    if url.endswith("/.well-known/openid-configuration"):
        url = url[: -len("/.well-known/openid-configuration")]
    return url


async def _fetch_oidc_metadata(issuer: str) -> dict[str, Any]:
    issuer = _normalize_issuer(issuer)
    well_known = f"{issuer}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(well_known)
        if resp.status_code >= 400:
            raise ValidationException(f"OIDC discovery failed ({resp.status_code}) for {well_known}")
        return resp.json()


class SsoLoginService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def initiate_login(self, config: SsoConfiguration, return_url: Optional[str]) -> str:
        if config.provider == "SAML":
            from app.services.saml_login_service import SamlLoginService
            return await SamlLoginService(self._db).initiate_login(config, return_url)
        return await self._initiate_oidc_login(config, return_url)

    async def _initiate_oidc_login(self, config: SsoConfiguration, return_url: Optional[str]) -> str:
        if config.provider != "OIDC":
            raise BusinessException("Unsupported SSO provider type.")

        if not config.client_id:
            raise ValidationException("OIDC client_id is required.")
        if not config.metadata_url:
            raise ValidationException("OIDC metadata_url (issuer) is required.")

        metadata = await _fetch_oidc_metadata(config.metadata_url)
        auth_endpoint = metadata.get("authorization_endpoint")
        if not auth_endpoint:
            raise ValidationException("OIDC metadata missing authorization_endpoint")

        state = secrets.token_urlsafe(32)
        verifier, challenge = _pkce_pair()
        self._db.add(
            SsoAuthState(
                state=state,
                config_id=config.id,
                code_verifier=verifier,
                return_url=return_url,
                created_at=datetime.now(timezone.utc),
            )
        )
        await self._db.commit()

        base = settings.app_url.rstrip("/")
        redirect_uri = f"{base}/api/sso/callback/{config.id}"
        params = {
            "response_type": "code",
            "client_id": config.client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{auth_endpoint}?{urlencode(params)}"

    async def consume_state(self, state: Optional[str], config_id: uuid.UUID) -> SsoAuthState:
        if not state:
            raise ValidationException("Missing OAuth state parameter.")
        row = (
            await self._db.execute(
                select(SsoAuthState).where(
                    SsoAuthState.state == state,
                    SsoAuthState.config_id == config_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise ValidationException("Invalid or expired SSO state.")
        # 15-minute TTL
        if row.created_at < datetime.now(timezone.utc) - timedelta(minutes=15):
            await self._db.execute(delete(SsoAuthState).where(SsoAuthState.state == state))
            await self._db.commit()
            raise ValidationException("SSO state expired. Please try again.")
        await self._db.execute(delete(SsoAuthState).where(SsoAuthState.state == state))
        await self._db.commit()
        return row

    async def exchange_code_and_fetch_profile(
        self,
        config: SsoConfiguration,
        code: str,
        code_verifier: str,
    ) -> dict[str, Any]:
        if not config.client_secret:
            raise ValidationException("OIDC client_secret is not configured.")

        metadata = await _fetch_oidc_metadata(config.metadata_url or "")
        token_endpoint = metadata.get("token_endpoint")
        userinfo_endpoint = metadata.get("userinfo_endpoint")
        if not token_endpoint:
            raise ValidationException("OIDC metadata missing token_endpoint")

        base = settings.app_url.rstrip("/")
        redirect_uri = f"{base}/api/sso/callback/{config.id}"
        client_secret = decrypt_value(config.client_secret)

        async with httpx.AsyncClient(timeout=20.0) as client:
            token_resp = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": config.client_id,
                    "client_secret": client_secret,
                    "code_verifier": code_verifier,
                },
                headers={"Accept": "application/json"},
            )
            if token_resp.status_code >= 400:
                log.warning("OIDC token exchange failed", status=token_resp.status_code, body=token_resp.text[:300])
                raise BusinessException("OIDC token exchange failed.")

            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            id_token = token_data.get("id_token")

            profile: dict[str, Any] = {}
            if userinfo_endpoint and access_token:
                ui_resp = await client.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if ui_resp.status_code < 400:
                    profile = ui_resp.json()

            if not profile and id_token:
                profile = await self._verify_id_token(id_token, metadata, config.client_id or "")

        email = profile.get("email") or profile.get("preferred_username") or profile.get("upn")
        if not email:
            raise BusinessException("SSO provider did not return an email address.")

        return {
            "email": str(email).lower(),
            "name": profile.get("given_name") or profile.get("name"),
            "surname": profile.get("family_name"),
            "subject": profile.get("sub"),
        }

    async def _verify_id_token(
        self, id_token: str, metadata: dict[str, Any], client_id: str
    ) -> dict[str, Any]:
        """Verify OIDC id_token signature via JWKS and return claims."""
        import jwt as pyjwt

        jwks_uri = metadata.get("jwks_uri")
        if not jwks_uri:
            raise ValidationException("OIDC metadata missing jwks_uri")

        async with httpx.AsyncClient(timeout=15.0) as client:
            jwks_resp = await client.get(jwks_uri)
            if jwks_resp.status_code >= 400:
                raise ValidationException("JWKS fetch failed.")
            jwks = jwks_resp.json()

        header = pyjwt.get_unverified_header(id_token)
        kid = header.get("kid")
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if not key and jwks.get("keys"):
            key = jwks["keys"][0]
        if not key:
            raise BusinessException("Unable to find matching JWKS key for id_token.")

        issuer = metadata.get("issuer") or ""
        alg = header.get("alg", "RS256")
        # Only asymmetric algorithms: never let the token header pick HMAC/none.
        if alg not in ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"):
            raise BusinessException("Unsupported id_token signing algorithm.")
        claims = pyjwt.decode(
            id_token,
            pyjwt.PyJWK(key).key,
            algorithms=[alg],
            audience=client_id,
            issuer=issuer or None,
            options={"verify_iss": bool(issuer)},
        )
        return claims

    async def process_saml_response(
        self,
        config: SsoConfiguration,
        saml_response: str,
        relay_state: Optional[str],
    ) -> dict[str, Any]:
        from app.services.saml_login_service import SamlLoginService
        return await SamlLoginService(self._db).process_response(config, saml_response, relay_state)
