"""
Provision GitHub repository CI/CD for the AI agent pipeline.

Pushes workflow files, sets FFINN_CALLBACK_TOKEN + API_BASE_URL, and updates
the agent configuration with default workflow IDs.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_agent.source_control import GitHubClient, create_source_control_client
from app.core.config import settings
from app.core.security import decrypt_value
from app.domain.models.ai_agent import AIAgentConfiguration
from app.services.misc_services import SettingsService

log = structlog.get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "workflows"
_STAGING_WORKFLOW = "ai-agent-staging.yml"
_PRODUCTION_WORKFLOW = "ai-agent-production.yml"
_CALLBACK_SECRET_NAME = "FFINN_CALLBACK_TOKEN"
_API_BASE_URL_VAR = "API_BASE_URL"
_CALLBACK_SETTING_KEY = "AIAgent.CallbackToken"

_WORKFLOW_DEPLOYMENTS: tuple[tuple[str, str], ...] = (
    (_STAGING_WORKFLOW, f".github/workflows/{_STAGING_WORKFLOW}"),
    (_PRODUCTION_WORKFLOW, f".github/workflows/{_PRODUCTION_WORKFLOW}"),
)

_MANUAL_AZURE_SECRETS = (
    "AZURE_CREDENTIALS",
    "STAGING_DATABASE_URL",
    "STAGING_JWT_SECRET_KEY",
    "STAGING_ENCRYPTION_KEY",
    "SWA_DEPLOYMENT_TOKEN",
)

_MANUAL_AZURE_VARS = (
    "AZURE_REGISTRY",
    "AZURE_RESOURCE_GROUP",
    "AZURE_CONTAINER_APP_STAGING_NAME",
    "AZURE_CONTAINER_APP_NAME",
    "STAGING_URL",
    "STAGING_FRONTEND_URL",
    "PRODUCTION_API_URL",
)


@dataclass
class SetupStepResult:
    name: str
    success: bool
    detail: str = ""


@dataclass
class RepositorySetupResult:
    success: bool
    steps: list[SetupStepResult] = field(default_factory=list)
    manual_steps: list[str] = field(default_factory=list)
    callback_token_configured: bool = False
    api_base_url: str = ""


class RepositorySetupService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_setup_status(
        self, config: AIAgentConfiguration, sc: GitHubClient, branch: str
    ) -> dict:
        callback_ok = bool(await self._resolve_callback_token())
        secrets = await sc.list_actions_secrets()
        workflows_present = []
        for _, repo_path in _WORKFLOW_DEPLOYMENTS:
            content = await sc.get_file_content(repo_path, ref=branch)
            workflows_present.append({"path": repo_path, "present": content is not None})

        return {
            "repository_connected": await sc.verify_connection(),
            "callback_token_configured": callback_ok,
            "github_callback_secret_set": _CALLBACK_SECRET_NAME in secrets,
            "api_base_url_variable_set": _API_BASE_URL_VAR in await self._list_variables(sc),
            "workflows": workflows_present,
            "staging_workflow_id": config.staging_workflow_id,
            "release_workflow_id": config.release_workflow_id,
            "manual_azure_secrets": list(_MANUAL_AZURE_SECRETS),
            "manual_azure_variables": list(_MANUAL_AZURE_VARS),
        }

    async def setup_repository(
        self,
        config: AIAgentConfiguration,
        api_base_url: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> RepositorySetupResult:
        result = RepositorySetupResult(success=False)
        api_url = (api_base_url or config.api_base_url or settings.api_base_url).rstrip("/")
        result.api_base_url = api_url

        sc_token = decrypt_value(config.source_control_token_encrypted, settings.encryption_key)
        sc = create_source_control_client(
            config.source_control_type or "github",
            sc_token,
            config.repository_url,
        )

        if not await sc.verify_connection():
            result.steps.append(SetupStepResult("verify_repository", False, "Cannot access repository"))
            return result
        result.steps.append(SetupStepResult("verify_repository", True))

        deploy_branch = branch or await sc.get_default_branch()

        callback_token = await self._ensure_callback_token()
        result.callback_token_configured = bool(callback_token)
        if not callback_token:
            result.steps.append(SetupStepResult(
                "callback_token", False, "Could not configure CALLBACK_TOKEN"
            ))
            result.manual_steps.append(
                "Set CALLBACK_TOKEN in python-backend/.env (generate with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(32))\")"
            )
            return result
        result.steps.append(SetupStepResult("callback_token", True, "Token ready for CI callbacks"))

        for template_name, repo_path in _WORKFLOW_DEPLOYMENTS:
            # Never replace a workflow the repository already has: it may be adapted to a different cloud.
            if await sc.get_file_content(repo_path, ref=deploy_branch) is not None:
                result.steps.append(SetupStepResult(
                    f"workflow:{repo_path}", True, "Already present, left unchanged"
                ))
                continue
            content = self._load_template(template_name)
            if not content:
                result.steps.append(SetupStepResult(
                    f"workflow:{repo_path}", False, "Template missing on server"
                ))
                continue
            ok = await sc.upsert_file(
                repo_path,
                content,
                deploy_branch,
                f"chore(ai-agent): add {template_name}",
            )
            result.steps.append(SetupStepResult(
                f"workflow:{repo_path}", ok, "Created/updated" if ok else "Failed to push file"
            ))

        secret_ok = await sc.upsert_actions_secret(_CALLBACK_SECRET_NAME, callback_token)
        result.steps.append(SetupStepResult(
            "github_secret", secret_ok,
            f"{_CALLBACK_SECRET_NAME} set" if secret_ok else "Failed — check token has admin:repo scope",
        ))

        var_ok = await sc.upsert_actions_variable(_API_BASE_URL_VAR, api_url)
        result.steps.append(SetupStepResult(
            "github_variable", var_ok,
            f"{_API_BASE_URL_VAR}={api_url}" if var_ok else "Failed to set API_BASE_URL variable",
        ))

        if not config.staging_workflow_id:
            config.staging_workflow_id = _STAGING_WORKFLOW
        if not config.release_workflow_id:
            config.release_workflow_id = _PRODUCTION_WORKFLOW
        if api_url and not config.api_base_url:
            config.api_base_url = api_url
        config.updated_at = datetime.now(timezone.utc)
        await self._db.commit()

        result.steps.append(SetupStepResult(
            "configuration", True,
            f"Workflow IDs: {_STAGING_WORKFLOW}, {_PRODUCTION_WORKFLOW}",
        ))

        result.manual_steps.extend([
            f"Add Azure secrets to GitHub if deploying to Azure: {', '.join(_MANUAL_AZURE_SECRETS)}",
            f"Add Azure variables: {', '.join(_MANUAL_AZURE_VARS)}",
            "Ensure CALLBACK_TOKEN in .env matches FFINN_CALLBACK_TOKEN in GitHub (auto-synced when possible)",
        ])

        result.success = all(s.success for s in result.steps)
        return result

    async def _resolve_callback_token(self) -> str:
        if settings.callback_token:
            return settings.callback_token
        stored = await SettingsService(self._db).get_setting(_CALLBACK_SETTING_KEY, tenant_id=None)
        return stored or ""

    async def _ensure_callback_token(self) -> str:
        existing = await self._resolve_callback_token()
        if existing:
            return existing
        generated = secrets.token_urlsafe(32)
        await SettingsService(self._db).set_setting(
            _CALLBACK_SETTING_KEY, generated, tenant_id=None
        )
        log.info(
            "Generated CALLBACK_TOKEN stored in app settings — "
            "add CALLBACK_TOKEN to .env for persistence across restarts",
            key=_CALLBACK_SETTING_KEY,
        )
        return generated

    @staticmethod
    def _load_template(name: str) -> Optional[str]:
        path = _TEMPLATES_DIR / name
        if not path.is_file():
            # Fallback: monorepo checkout layout
            fallback = Path(__file__).resolve().parents[3] / ".github" / "workflows" / name
            path = fallback if fallback.is_file() else path
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    @staticmethod
    async def _list_variables(sc: GitHubClient) -> list[str]:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{sc.BASE_URL}/repos/{sc._owner}/{sc._repo}/actions/variables",
                    headers=sc._headers,
                    params={"per_page": 100},
                )
                if resp.status_code != 200:
                    return []
                return [v["name"] for v in resp.json().get("variables", [])]
        except Exception:
            return []
