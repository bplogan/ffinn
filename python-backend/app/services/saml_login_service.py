"""SAML 2.0 SP-initiated SSO login."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BusinessException, ValidationException
from app.core.security import decrypt_value
from app.domain.models.identity import SsoAuthState, SsoConfiguration
from app.services.sso_login_service import SsoLoginService

log = structlog.get_logger(__name__)

EMAIL_CLAIM_URIS = (
    "email",
    "mail",
    "Email",
    "emailAddress",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
)


def _request_base() -> dict[str, Any]:
    parsed = urlparse(settings.app_url.rstrip("/"))
    host = parsed.hostname or "localhost"
    port = str(parsed.port or (443 if parsed.scheme == "https" else 80))
    return {
        "https": "on" if parsed.scheme == "https" else "off",
        "http_host": host,
        "script_name": "",
        "server_port": port,
        "get_data": {},
        "post_data": {},
    }


def _acs_url(config_id: uuid.UUID) -> str:
    return f"{settings.app_url.rstrip('/')}/api/sso/callback/{config_id}"


def _sp_entity_id(config: SsoConfiguration) -> str:
    if config.client_id:
        return config.client_id
    return f"{settings.app_url.rstrip('/')}/api/sso/sp/{config.id}"


class SamlLoginService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def _load_idp_metadata(self, config: SsoConfiguration) -> dict[str, Any]:
        from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser

        if config.metadata_xml:
            return OneLogin_Saml2_IdPMetadataParser.parse(config.metadata_xml)

        if config.metadata_url:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(config.metadata_url)
                if resp.status_code >= 400:
                    raise ValidationException(f"Failed to fetch IdP metadata ({resp.status_code}).")
                return OneLogin_Saml2_IdPMetadataParser.parse(resp.text)

        raise ValidationException("SAML requires metadata_xml or metadata_url.")

    def _build_settings(self, config: SsoConfiguration, idp_data: dict[str, Any]) -> Any:
        from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
        from onelogin.saml2.settings import OneLogin_Saml2_Settings

        sp = {
            "entityId": _sp_entity_id(config),
            "assertionConsumerService": {
                "url": _acs_url(config.id),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        }
        security: dict[str, Any] = {
            "authnRequestsSigned": False,
            "wantAssertionsSigned": True,
            "wantMessagesSigned": False,
        }
        if config.client_secret:
            try:
                private_key = decrypt_value(config.client_secret)
                sp["privateKey"] = private_key
                security["authnRequestsSigned"] = True
            except Exception:
                log.warning("SAML SP private key could not be decrypted; requests will be unsigned.")

        merged = OneLogin_Saml2_IdPMetadataParser.merge_settings(
            idp_data, sp, security=security, contact_info=None
        )
        return OneLogin_Saml2_Settings(settings=merged)

    async def initiate_login(self, config: SsoConfiguration, return_url: Optional[str]) -> str:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth

        idp_data = await self._load_idp_metadata(config)
        saml_settings = self._build_settings(config, idp_data)
        relay_state = secrets.token_urlsafe(32)
        self._db.add(
            SsoAuthState(
                state=relay_state,
                config_id=config.id,
                code_verifier=None,
                return_url=return_url,
                created_at=datetime.now(timezone.utc),
            )
        )
        await self._db.commit()

        req = _request_base()
        auth = OneLogin_Saml2_Auth(req, old_settings=saml_settings.get_settings())
        redirect_url = auth.login(return_to=return_url or "", relay_state=relay_state)
        if not redirect_url:
            raise BusinessException("SAML IdP did not return a login URL.")
        return redirect_url

    async def process_response(
        self,
        config: SsoConfiguration,
        saml_response: str,
        relay_state: Optional[str],
    ) -> dict[str, Any]:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth

        if relay_state:
            await SsoLoginService(self._db).consume_state(relay_state, config.id)

        idp_data = await self._load_idp_metadata(config)
        saml_settings = self._build_settings(config, idp_data)
        req = _request_base()
        req["post_data"] = {
            "SAMLResponse": saml_response,
            "RelayState": relay_state or "",
        }
        auth = OneLogin_Saml2_Auth(req, old_settings=saml_settings.get_settings())
        auth.process_response()
        errors = auth.get_errors()
        if errors:
            reason = auth.get_last_error_reason() or "; ".join(errors)
            log.warning("SAML response validation failed", errors=errors, reason=reason)
            raise BusinessException(f"SAML authentication failed: {reason}")
        if not auth.is_authenticated():
            raise BusinessException("SAML authentication failed.")

        email = self._extract_email(auth.get_nameid(), auth.get_attributes())
        if not email:
            raise BusinessException("SAML assertion did not include an email address.")

        attrs = auth.get_attributes()
        first = self._first_attr(attrs, "givenName", "firstName", "first_name")
        last = self._first_attr(attrs, "surname", "lastName", "last_name", "sn")
        return {
            "email": email.lower(),
            "name": first,
            "surname": last,
            "subject": auth.get_nameid(),
        }

    def sp_metadata_xml(self, config: SsoConfiguration, idp_data: dict[str, Any]) -> str:
        saml_settings = self._build_settings(config, idp_data)
        return saml_settings.get_sp_metadata()

    async def get_sp_metadata(self, config: SsoConfiguration) -> str:
        idp_data = await self._load_idp_metadata(config)
        return self.sp_metadata_xml(config, idp_data)

    @staticmethod
    def _first_attr(attrs: dict[str, list[str]], *keys: str) -> Optional[str]:
        for key in keys:
            if key in attrs and attrs[key]:
                return str(attrs[key][0])
        return None

    @staticmethod
    def _extract_email(name_id: Optional[str], attrs: dict[str, list[str]]) -> Optional[str]:
        if name_id and "@" in name_id:
            return name_id
        for key in EMAIL_CLAIM_URIS:
            if key in attrs and attrs[key]:
                val = str(attrs[key][0])
                if "@" in val:
                    return val
        for values in attrs.values():
            for val in values:
                s = str(val)
                if "@" in s:
                    return s
        return None
