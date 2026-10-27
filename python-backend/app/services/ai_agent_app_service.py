"""
AI Agent application service — thin CRUD layer for configurations and generation history.
The heavy orchestration lives in app/ai_agent/ai_agent_service.py.
"""
from __future__ import annotations

import ipaddress
import socket
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.security import encrypt_value, decrypt_value
from app.core.config import settings
from app.domain.models.ai_agent import AIAgentConfiguration, AIProviderConfiguration
from app.ai_agent.source_control import create_source_control_client
import structlog

log = structlog.get_logger(__name__)


# Hosts permitted for outbound provider connectivity tests. This prevents
# server-side request forgery (SSRF) where a tenant user could supply an
# endpoint pointing at internal services or cloud metadata endpoints.
_AZURE_OPENAI_ALLOWED_SUFFIXES: tuple[str, ...] = (
    ".openai.azure.com",
    ".cognitiveservices.azure.com",
)


def _validate_azure_openai_endpoint(raw: str) -> str:
    """Validate a user-supplied Azure OpenAI endpoint.

    Returns the trimmed base URL if safe; raises ValueError otherwise.
    Rules:
      - scheme must be https
      - host must end with an allow-listed Azure suffix
      - host must resolve to public, non-loopback, non-link-local IPs only
    """
    parsed = urlparse(raw.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Endpoint must be an https:// URL with a hostname.")
    host = parsed.hostname.lower()
    if not any(host.endswith(suffix) for suffix in _AZURE_OPENAI_ALLOWED_SUFFIXES):
        raise ValueError(
            "Endpoint host must be an Azure OpenAI/Cognitive Services hostname."
        )
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(f"Endpoint host could not be resolved: {exc}") from exc
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError("Endpoint resolves to a non-public address.")
    # Reconstruct without path/query to avoid open-proxying user-supplied paths.
    return f"https://{host}"


def _validate_http_url(raw: str) -> None:
    """Self-hosted/OpenAI-compatible endpoints are user-supplied (this API is host-admin only)."""
    parsed = urlparse(raw.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Base URL must start with http:// or https:// and include a host.")


def _azure_resource_name_from_endpoint(raw: str) -> Optional[str]:
    parsed = urlparse(raw.strip())
    host = (parsed.hostname or "").lower()
    suffix = ".openai.azure.com"
    if host.endswith(suffix):
        return host[: -len(suffix)]
    return None


def _format_provider_test_failure(
    provider: str,
    deployment: str,
    endpoint: str,
    exc: Optional[Exception] = None,
    available: Optional[list[dict[str, str]]] = None,
) -> str:
    azure_aliases = {"azure", "azure-openai", "azure_openai", "azureopenai"}
    detail = str(exc).strip() if exc else ""
    resource = _azure_resource_name_from_endpoint(endpoint) if provider in azure_aliases else None
    if resource and deployment.lower() == resource.lower():
        msg = (
            f"'{deployment}' is your Azure resource name (from the endpoint URL), not a deployment. "
            f"Open Azure Portal → {resource} → Model deployments and copy the Deployment name column."
        )
    elif detail:
        msg = f"Test request failed for deployment '{deployment}': {detail}"
    else:
        msg = (
            f"Test request failed for deployment '{deployment}'. "
            "Use the Deployment name from Azure Portal → Model deployments."
        )
    if available:
        formatted = ", ".join(
            f"{row['deployment_name']} (model: {row['model']})" for row in available
        )
        msg += f" Available on this resource: {formatted}."
    return msg


class AIAgentAppService:
    def __init__(self, db: AsyncSession):
        self._db = db

    # ── Configurations ────────────────────────────────────────────────────────

    async def ensure_default_build_agent(self, tenant_id, user_id: Optional[uuid.UUID] = None) -> AIAgentConfiguration:
        """Every tenant has one undeletable build agent. Adopt the oldest existing one, else create it."""
        rows = list((await self._db.execute(
            select(AIAgentConfiguration)
            .where(AIAgentConfiguration.tenant_id == tenant_id, AIAgentConfiguration.kind == "build")
            .order_by(AIAgentConfiguration.is_default.desc(), AIAgentConfiguration.created_at.asc())
        )).scalars())
        if rows:
            agent = rows[0]
            if not agent.is_default:
                agent.is_default = True
                await self._db.commit()
            return agent
        agent = AIAgentConfiguration(
            id=uuid.uuid4(), tenant_id=tenant_id, created_by_id=user_id,
            name="Build Agent", kind="build", is_default=True, avatar="build",
            description="Turns plain-English feature requests into code, pull requests and deployments.",
            source_control_type="github", repository_url="", source_control_token_encrypted="",
            ai_provider="", ai_model="", ai_api_key_encrypted="",
            staging_workflow_id="ai-agent-staging.yml", release_workflow_id="ai-agent-production.yml",
            is_active=True, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        self._db.add(agent)
        await self._db.commit()
        await self._db.refresh(agent)
        return agent

    async def get_configurations(
        self, tenant_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[AIAgentConfiguration], int]:
        q = select(AIAgentConfiguration).where(AIAgentConfiguration.tenant_id == tenant_id)
        total = (await self._db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        items = (
            await self._db.execute(
                q.order_by(AIAgentConfiguration.is_default.desc(), AIAgentConfiguration.created_at.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return list(items), total

    async def get_configuration(
        self, config_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> AIAgentConfiguration:
        result = await self._db.execute(
            select(AIAgentConfiguration).where(
                AIAgentConfiguration.id == config_id,
                AIAgentConfiguration.tenant_id == tenant_id,
            )
        )
        config = result.scalar_one_or_none()
        if not config:
            raise NotFoundException("Configuration not found.")
        return config

    async def create_configuration(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        source_control_type: str,
        repository_url: str,
        source_control_token: str,
        ai_provider: str = "",
        ai_model: str = "",
        ai_api_key: str = "",
        provider_config_id: Optional[uuid.UUID] = None,
        staging_workflow_id: Optional[str] = None,
        release_workflow_id: Optional[str] = None,
        azure_openai_endpoint: Optional[str] = None,
        azure_deployment_name: Optional[str] = None,
        kind: str = "build",
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        avatar: Optional[str] = None,
    ) -> AIAgentConfiguration:
        enc_key = settings.encryption_key
        linked_id: Optional[uuid.UUID] = None
        if provider_config_id:
            # Link, do not copy: the key/endpoint/model are read from the saved provider
            # at generation time, so rotating a key on the Providers page just works.
            provider_cfg = await self.get_provider_config_by_id(provider_config_id, tenant_id)
            linked_id = provider_cfg.id
            ai_provider = (ai_provider or provider_cfg.provider_name).strip()
            ai_api_key = ""
            azure_openai_endpoint = None
        config = AIAgentConfiguration(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            created_by_id=user_id,
            name=name,
            kind=kind,
            is_default=False,
            description=description,
            system_prompt=system_prompt,
            temperature=temperature,
            avatar=avatar,
            source_control_type=source_control_type,
            repository_url=repository_url,
            source_control_token_encrypted=encrypt_value(source_control_token, enc_key),
            provider_id=linked_id,
            ai_provider=ai_provider,
            ai_model=ai_model,
            azure_deployment_name=azure_deployment_name,
            ai_api_key_encrypted=encrypt_value(ai_api_key, enc_key),
            staging_workflow_id=staging_workflow_id or "ai-agent-staging.yml",
            release_workflow_id=release_workflow_id or "ai-agent-production.yml",
            azure_openai_endpoint=azure_openai_endpoint,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._db.add(config)
        await self._db.commit()
        await self._db.refresh(config)
        return config

    async def update_configuration(
        self,
        config_id: uuid.UUID,
        tenant_id: uuid.UUID,
        source_control_token: Optional[str] = None,
        ai_api_key: Optional[str] = None,
        **kwargs,
    ) -> AIAgentConfiguration:
        config = await self.get_configuration(config_id, tenant_id)
        enc_key = settings.encryption_key
        provider_id = kwargs.pop("provider_id", None)
        if provider_id:
            provider_cfg = await self.get_provider_config_by_id(provider_id, tenant_id)
            config.provider_id = provider_cfg.id
            config.ai_provider = provider_cfg.provider_name
            # The provider now owns credentials; drop the stale per-agent copies.
            config.ai_api_key_encrypted = ""
            config.azure_openai_endpoint = None
            config.azure_deployment_name = None
            kwargs.pop("ai_provider", None)
            ai_api_key = None
        if source_control_token:
            config.source_control_token_encrypted = encrypt_value(source_control_token, enc_key)
        if ai_api_key:
            config.ai_api_key_encrypted = encrypt_value(ai_api_key, enc_key)
        for k, v in kwargs.items():
            if hasattr(config, k) and v is not None:
                setattr(config, k, v)
        config.updated_at = datetime.now(timezone.utc)
        await self._db.commit()
        await self._db.refresh(config)
        return config

    async def delete_configuration(self, config_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        config = await self.get_configuration(config_id, tenant_id)
        if config.is_default:
            raise ValueError("The build agent is part of the framework and cannot be removed.")
        await self._db.delete(config)
        await self._db.commit()

    async def verify_connection(
        self, config_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> dict:
        config = await self.get_configuration(config_id, tenant_id)
        token = decrypt_value(config.source_control_token_encrypted, settings.encryption_key)
        try:
            sc = create_source_control_client(
                config.source_control_type or "github", token, config.repository_url
            )
            ok = await sc.verify_connection()
            return {"connected": ok, "message": "Connection successful." if ok else "Could not connect."}
        except Exception as e:
            log.warning("verify_connection failed", config_id=str(config_id), error=str(e))
            return {"connected": False, "message": "Connection failed. Check your credentials and repository URL."}

    # ── Provider configs (per-tenant AI provider overrides) ───────────────────

    async def get_provider_configs(self, tenant_id: uuid.UUID) -> list[AIProviderConfiguration]:
        return list((await self._db.execute(
            select(AIProviderConfiguration).where(AIProviderConfiguration.tenant_id == tenant_id)
        )).scalars().all())

    async def get_provider_config_by_id(
        self, config_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> AIProviderConfiguration:
        result = await self._db.execute(
            select(AIProviderConfiguration).where(
                AIProviderConfiguration.id == config_id,
                AIProviderConfiguration.tenant_id == tenant_id,
            )
        )
        cfg = result.scalar_one_or_none()
        if not cfg:
            raise NotFoundException("Provider configuration not found.")
        return cfg

    async def delete_provider_config(self, config_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        cfg = await self.get_provider_config_by_id(config_id, tenant_id)
        await self._db.delete(cfg)
        await self._db.commit()

    async def test_provider_config(self, config_id: uuid.UUID, tenant_id: uuid.UUID) -> dict:
        """Run the same kind of request generation uses: key + endpoint + deployment/model."""
        from app.ai_agent.azure_config import azure_deployment_name, azure_model_name, is_azure_provider

        cfg = await self.get_provider_config_by_id(config_id, tenant_id)
        try:
            api_key = decrypt_value(cfg.api_key_encrypted, settings.encryption_key)
        except Exception:
            return {"success": False, "message": "Failed to decrypt API key.", "details": None}

        azure = is_azure_provider(cfg.provider_name)
        deployment = azure_deployment_name(cfg) if azure else (cfg.model_name or "").strip()
        model = azure_model_name(cfg) if azure else deployment
        return await self._run_provider_test(
            cfg.provider_name, api_key, cfg.endpoint or "", deployment, model
        )

    async def test_credentials(self, tenant_id: uuid.UUID, req) -> dict:
        """Test credentials that have not been saved yet (setup form Test button)."""
        from app.ai_agent.azure_config import is_azure_provider

        api_key = await self._probe_api_key(tenant_id, req)
        model = (req.model_name or "").strip()
        endpoint = (req.endpoint or "").strip()
        if not model:
            return {"success": False, "message": "Choose a model (or Azure deployment) to test.", "details": None}
        return await self._run_provider_test(
            req.provider_name, api_key, endpoint, model, "" if is_azure_provider(req.provider_name) else model
        )

    async def list_models(self, tenant_id: uuid.UUID, req) -> dict:
        """Live model list for the setup form. Also proves the key works."""
        from app.ai_agent.azure_config import is_azure_provider, list_azure_deployments
        from app.ai_agent.providers import canonical_provider, list_provider_models

        api_key = await self._probe_api_key(tenant_id, req)
        endpoint = (req.endpoint or "").strip()
        name = canonical_provider(req.provider_name)
        needs_key = name not in ("ollama", "custom")
        if needs_key and not api_key:
            return {"models": [], "deployments": [], "error": "Enter an API key first."}
        try:
            if is_azure_provider(req.provider_name):
                if not endpoint:
                    return {"models": [], "deployments": [], "error": "Enter your Azure endpoint first."}
                endpoint = _validate_azure_openai_endpoint(endpoint)
                result = await list_azure_deployments(endpoint, api_key)
                return {
                    "models": [],
                    "deployments": result.deployments,
                    "error": None if result.deployments else result.error,
                }
            if endpoint:
                _validate_http_url(endpoint)
            models = await list_provider_models(req.provider_name, api_key, endpoint or None)
            return {"models": models, "deployments": [], "error": None if models else "No models were returned."}
        except ValueError as exc:
            return {"models": [], "deployments": [], "error": str(exc)}

    async def _probe_api_key(self, tenant_id: uuid.UUID, req) -> str:
        api_key = (req.api_key or "").strip()
        if not api_key and req.provider_id:
            cfg = await self.get_provider_config_by_id(req.provider_id, tenant_id)
            api_key = decrypt_value(cfg.api_key_encrypted, settings.encryption_key)
        return api_key

    async def _run_provider_test(
        self, provider_name: str, api_key: str, endpoint: str, deployment: str, model: str
    ) -> dict:
        from app.ai_agent.azure_config import is_azure_provider, list_azure_deployments
        from app.ai_agent.providers import canonical_provider, create_ai_provider

        provider = (provider_name or "").lower()
        azure = is_azure_provider(provider)
        if not deployment:
            return {
                "success": False,
                "message": "Set a deployment name (Azure) or model before testing.",
                "details": None,
            }
        try:
            if azure:
                if not endpoint:
                    return {"success": False, "message": "Endpoint required for Azure OpenAI.", "details": None}
                endpoint = _validate_azure_openai_endpoint(endpoint)
            elif endpoint:
                _validate_http_url(endpoint)
            client = create_ai_provider(canonical_provider(provider), api_key, deployment, endpoint or None)
        except ValueError as exc:
            return {"success": False, "message": str(exc), "details": None}

        ok, error = await client.verify()
        if ok:
            if azure and model and model != deployment:
                message = f"Verified deployment '{deployment}' (model: {model})."
            elif azure:
                message = f"Verified deployment '{deployment}'."
            else:
                message = f"Verified model '{deployment}'."
            return {"success": True, "message": message, "details": None}

        log.warning("provider test failed", provider=provider, error=error)
        available = None
        if azure and endpoint:
            try:
                available = (await list_azure_deployments(endpoint, api_key)).deployments
            except Exception:
                available = None
        if azure:
            message = _format_provider_test_failure(
                provider, deployment, endpoint, Exception(error) if error else None, available=available
            )
        else:
            message = error or f"Test request failed for model '{deployment}'."
        return {"success": False, "message": message, "details": error}

    async def create_provider_config(
        self,
        tenant_id: uuid.UUID,
        provider_name: str,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        display_name: Optional[str] = None,
        deployment_name: Optional[str] = None,
    ) -> AIProviderConfiguration:
        """Always creates a new provider, so several keys of one type (dev/prod) can coexist."""
        from app.ai_agent.azure_config import apply_azure_provider_fields, is_azure_provider
        from app.ai_agent.providers import canonical_provider

        needs_key = canonical_provider(provider_name) not in ("ollama", "custom")
        if needs_key and not api_key:
            raise ValueError("api_key is required when creating a new provider configuration.")
        label = (display_name or "").strip() or provider_name
        cfg = AIProviderConfiguration(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            provider_name=provider_name,
            display_name=label,
            api_key_encrypted=encrypt_value(api_key or "", settings.encryption_key),
            model_name=None if is_azure_provider(provider_name) else model_name,
            endpoint=endpoint,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        if is_azure_provider(provider_name):
            apply_azure_provider_fields(
                cfg,
                deployment_name=deployment_name if deployment_name is not None else model_name,
                model_name=model_name,
            )
        self._db.add(cfg)
        await self._db.commit()
        await self._db.refresh(cfg)
        return cfg
