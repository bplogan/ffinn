"""AI Agent routes — the core feature."""
from __future__ import annotations
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator
import math

from sqlalchemy import select as sa_select, delete as sa_delete

from app.core.dependencies import DBSession, AdminUser, AIAgentUser, verify_callback_token
from app.core.config import settings
from app.core.security_middleware import build_rate_limit_dep
from app.schemas.ai_agent_schemas import (
    CreateConfigurationRequest, UpdateConfigurationRequest, ConfigurationResponse,
    CreateGenerationRequest, GenerationResponse,
    BuildCallbackRequest, DeployCallbackRequest, ReleaseCallbackRequest, PrValidationCallbackRequest,
    RepositorySetupRequest, RepositorySetupResponse, RepositorySetupStepResponse,
    ProviderConfigRequest, AzureDeploymentsRequest, ProviderProbeRequest,
)
from app.schemas.user_schemas import PagedResult
from app.services.ai_agent_app_service import AIAgentAppService
from app.ai_agent.ai_agent_service import AIAgentService
from app.infrastructure.websocket_manager import ws_manager

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/aiagent", tags=["AIAgent"])

# Keep a strong reference to background generation tasks so they are not
# garbage-collected before completion.
_background_tasks: set[asyncio.Task] = set()


# ── Utility / status routes ───────────────────────────────────────────────────

@router.get("/queue")
async def get_queue(
    db: DBSession,
    current_user: AIAgentUser,
):
    """Return the current AI generation queue items for this tenant."""
    from app.domain.models.ai_agent import AIAgentQueueItem, AIAgentGeneration
    rows = (await db.execute(
        sa_select(AIAgentQueueItem)
        .join(AIAgentGeneration, AIAgentQueueItem.generation_id == AIAgentGeneration.id)
        .where(
            AIAgentGeneration.tenant_id == current_user.tenant_id,
            AIAgentQueueItem.status.in_(["Queued", "Running"]),
        )
        .order_by(AIAgentQueueItem.enqueued_at)
    )).scalars().all()
    return [
        {
            "id": str(q.id),
            "generation_id": str(q.generation_id),
            "status": q.status,
            "priority": q.priority,
            "queued_at": q.enqueued_at.isoformat() if q.enqueued_at else None,
        }
        for q in rows
    ]


@router.get("/source-control-providers")
async def list_source_control_providers():
    """Return supported source-control provider names."""
    return [
        {"name": "github", "display_name": "GitHub", "type": "git", "supported": True},
        {"name": "gitlab", "display_name": "GitLab", "type": "git", "supported": False, "coming_soon": True},
        {"name": "bitbucket", "display_name": "Bitbucket", "type": "git", "supported": False, "coming_soon": True},
        {"name": "azure-devops", "display_name": "Azure DevOps", "type": "git", "supported": False, "coming_soon": True},
    ]


class TestConnectionRequest(BaseModel):
    source_control_type: str = "github"
    repository_url: str
    access_token: str


class GitHubTokenRequest(BaseModel):
    access_token: str
    organization: Optional[str] = None


@router.post(
    "/test-connection",
    dependencies=[Depends(build_rate_limit_dep(20, 60))],
)
async def test_connection_direct(
    body: TestConnectionRequest,
    current_user: AIAgentUser,
):
    """Test source-control connectivity using raw credentials (no saved config required)."""
    from app.ai_agent.source_control import create_source_control_client
    try:
        sc = create_source_control_client(
            body.source_control_type, body.access_token, body.repository_url
        )
        ok = await sc.verify_connection()
        return {"connected": ok, "message": "Connection successful." if ok else "Could not connect."}
    except Exception as e:
        log.warning("Source control connection test failed", error=str(e))
        return {"connected": False, "message": "Connection failed. Check your credentials and repository URL."}


@router.post(
    "/test-github-connection",
    dependencies=[Depends(build_rate_limit_dep(20, 60))],
)
async def test_github_connection(
    body: GitHubTokenRequest,
    current_user: AIAgentUser,
):
    """Validate a GitHub personal-access or fine-grained token."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {body.access_token}", "Accept": "application/vnd.github+json"},
            )
        if r.status_code == 200:
            data = r.json()
            return {"valid": True, "login": data.get("login"), "name": data.get("name")}
        return {"valid": False, "message": f"GitHub returned HTTP {r.status_code}"}
    except Exception as e:
        log.warning("GitHub connection test failed", error=str(e))
        return {"valid": False, "message": "Connection failed. Check your token and try again."}


@router.post(
    "/github-organizations",
    dependencies=[Depends(build_rate_limit_dep(20, 60))],
)
async def list_github_organizations(
    body: GitHubTokenRequest,
    current_user: AIAgentUser,
):
    """List GitHub organizations accessible to the provided token."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.github.com/user/orgs",
                headers={"Authorization": f"Bearer {body.access_token}", "Accept": "application/vnd.github+json"},
            )
        if r.status_code == 200:
            return [{"login": o["login"], "avatar_url": o.get("avatar_url")} for o in r.json()]
        return []
    except Exception:
        return []


class GitHubRepoRequest(BaseModel):
    access_token: str
    organization: Optional[str] = None
    page: int = 1
    per_page: int = 30


@router.post("/github-repositories")
async def list_github_repositories(
    body: GitHubRepoRequest,
    current_user: AIAgentUser,
):
    """List GitHub repositories for the token owner or an organization."""
    try:
        import httpx
        if body.organization:
            url = f"https://api.github.com/orgs/{body.organization}/repos"
        else:
            url = "https://api.github.com/user/repos"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                url,
                params={"page": body.page, "per_page": body.per_page, "sort": "updated"},
                headers={"Authorization": f"Bearer {body.access_token}", "Accept": "application/vnd.github+json"},
            )
        if r.status_code == 200:
            return [
                {"full_name": rp["full_name"], "clone_url": rp.get("clone_url"), "private": rp.get("private")}
                for rp in r.json()
            ]
        return []
    except Exception:
        return []


# ── Per-tenant source-control configuration ───────────────────────────────────
# Stores source-control defaults for a tenant in the settings table (tenant-scoped).
# This is separate from the admin-only global settings endpoints and is accessible
# to any authenticated user within their tenant.

_SC_KEYS = [
    "SourceControl.Provider",
    "SourceControl.RepoUrl",
    "SourceControl.Branch",
    "SourceControl.AutoSync",
    "SourceControl.SyncPath",
]


@router.get("/source-control-config")
async def get_source_control_config(
    db: DBSession,
    current_user: AIAgentUser,
):
    """Return the tenant-scoped source-control configuration."""
    from app.services.misc_services import SettingsService
    svc = SettingsService(db)
    result: dict = {}
    for key in _SC_KEYS:
        result[key] = await svc.get_setting(key, current_user.tenant_id)
    return result


class SourceControlConfigRequest(BaseModel):
    provider: str = "github"
    repo_url: str = ""
    branch: str = "main"
    access_token: Optional[str] = None   # If None/empty, existing token is preserved
    auto_sync: bool = False
    sync_path: str = "/"


@router.put("/source-control-config")
async def save_source_control_config(
    body: SourceControlConfigRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Save source-control configuration for the current tenant."""
    from app.services.misc_services import SettingsService
    from app.core.security import encrypt_value
    svc = SettingsService(db)
    batch = [
        {"key": "SourceControl.Provider",  "value": body.provider},
        {"key": "SourceControl.RepoUrl",   "value": body.repo_url},
        {"key": "SourceControl.Branch",    "value": body.branch},
        {"key": "SourceControl.AutoSync",  "value": str(body.auto_sync).lower()},
        {"key": "SourceControl.SyncPath",  "value": body.sync_path},
    ]
    # Only overwrite the stored access token when a new one is explicitly provided
    if body.access_token:
        batch.append({
            "key": "SourceControl.AccessToken",
            "value": encrypt_value(body.access_token, settings.encryption_key),
        })
    await svc.bulk_set_settings(batch, current_user.tenant_id)
    return {"message": "Source control configuration saved."}


class OptimizePromptRequest(BaseModel):
    prompt: str = Field(..., max_length=10000)


@router.post("/optimize-prompt")
async def optimize_prompt(
    body: OptimizePromptRequest,
    current_user: AIAgentUser,
):
    """Return an optimized version of the user's generation prompt."""
    from app.ai_agent.prompt_optimization import PromptOptimizationService
    optimizer = PromptOptimizationService()
    result = optimizer.optimize(body.prompt)
    return {
        "original": body.prompt,
        "optimized": result.optimized_prompt,
        "changes_applied": result.applied,
        "strategy": result.strategy,
    }


@router.get("/encryption-health")
async def encryption_health(
    db: DBSession,
    current_user: AIAgentUser,
    _: AdminUser,
):
    """Check that all encrypted AI provider API keys can be decrypted."""
    from app.domain.models.ai_agent import AIProviderConfiguration
    from app.core.security import decrypt_value
    configs = (await db.execute(
        sa_select(AIProviderConfiguration).where(AIProviderConfiguration.tenant_id == current_user.tenant_id)
    )).scalars().all()
    results = []
    for cfg in configs:
        try:
            if cfg.encrypted_api_key:
                decrypt_value(cfg.encrypted_api_key, settings.encryption_key)
                results.append({"id": str(cfg.id), "provider": cfg.provider_name, "status": "ok"})
            else:
                results.append({"id": str(cfg.id), "provider": cfg.provider_name, "status": "empty_key"})
        except Exception:
            log.warning("provider key decrypt failed", config_id=str(cfg.id), exc_info=True)
            results.append({"id": str(cfg.id), "provider": cfg.provider_name, "status": "error", "error": "Could not decrypt the stored API key."})
    return {"results": results, "total": len(results), "errors": sum(1 for r in results if r["status"] == "error")}


@router.post("/encryption-repair")
async def encryption_repair(
    db: DBSession,
    current_user: AIAgentUser,
    _: AdminUser,
):
    """Re-encrypt provider API keys using the current encryption key (use after key rotation)."""
    from app.domain.models.ai_agent import AIProviderConfiguration
    from app.core.security import decrypt_value, encrypt_value
    configs = (await db.execute(
        sa_select(AIProviderConfiguration).where(AIProviderConfiguration.tenant_id == current_user.tenant_id)
    )).scalars().all()
    repaired, failed = 0, 0
    for cfg in configs:
        try:
            if cfg.encrypted_api_key:
                plaintext = decrypt_value(cfg.encrypted_api_key, settings.encryption_key)
                cfg.encrypted_api_key = encrypt_value(plaintext, settings.encryption_key)
                repaired += 1
        except Exception:
            failed += 1
    await db.commit()
    return {"repaired": repaired, "failed": failed}


# ── Configuration aliases (mirrors .NET AIAgentController singular names) ───────

@router.get("/configuration", response_model=ConfigurationResponse)
async def get_configuration_singular(
    db: DBSession,
    current_user: AIAgentUser,
):
    """Get the first/primary AI agent configuration for this tenant."""
    svc = AIAgentAppService(db)
    items, _ = await svc.get_configurations(current_user.tenant_id, 1, 1)
    if not items:
        raise HTTPException(status_code=404, detail="No configuration found.")
    return ConfigurationResponse.model_validate(items[0])


@router.post("/configuration", response_model=ConfigurationResponse, status_code=201)
async def create_configuration_singular(
    body: CreateConfigurationRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Create an AI agent configuration (singular alias)."""
    svc = AIAgentAppService(db)
    config = await svc.create_configuration(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        **body.model_dump(),
    )
    return ConfigurationResponse.model_validate(config)


@router.post("/configuration/draft", response_model=ConfigurationResponse, status_code=201)
async def save_configuration_draft(
    body: CreateConfigurationRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Save an AI agent configuration as a draft (is_active=False)."""
    svc = AIAgentAppService(db)
    config = await svc.create_configuration(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        **body.model_dump(),
    )
    # Mark as draft
    config.is_active = False
    await db.commit()
    await db.refresh(config)
    return ConfigurationResponse.model_validate(config)


# ── Configurations ────────────────────────────────────────────────────────────

@router.get("/configurations", response_model=PagedResult)
async def list_configurations(
    db: DBSession,
    current_user: AIAgentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = AIAgentAppService(db)
    await svc.ensure_default_build_agent(current_user.tenant_id, current_user.id)
    items, total = await svc.get_configurations(current_user.tenant_id, page, page_size)
    return {"items": [ConfigurationResponse.model_validate(i) for i in items], "total_count": total, "page": page, "page_size": page_size,
            "total_pages": math.ceil(total / page_size)}


@router.post("/configurations", response_model=ConfigurationResponse, status_code=201)
async def create_configuration(
    body: CreateConfigurationRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentAppService(db)
    config = await svc.create_configuration(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        **body.model_dump(),
    )
    return ConfigurationResponse.model_validate(config)


@router.get("/configurations/{config_id}", response_model=ConfigurationResponse)
async def get_configuration(
    config_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentAppService(db)
    config = await svc.get_configuration(config_id, current_user.tenant_id)
    return ConfigurationResponse.model_validate(config)


@router.put("/configurations/{config_id}", response_model=ConfigurationResponse)
async def update_configuration(
    config_id: uuid.UUID,
    body: UpdateConfigurationRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentAppService(db)
    config = await svc.update_configuration(
        config_id, current_user.tenant_id,
        **body.model_dump(exclude_none=True),
    )
    return ConfigurationResponse.model_validate(config)


@router.delete("/configurations/{config_id}", status_code=204)
async def delete_configuration(
    config_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentAppService(db)
    try:
        await svc.delete_configuration(config_id, current_user.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/configurations/{config_id}/verify")
async def verify_connection(
    config_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentAppService(db)
    return await svc.verify_connection(config_id, current_user.tenant_id)


@router.get("/configurations/{config_id}/repository-setup-status")
async def get_repository_setup_status(
    config_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Check whether the target repo has AI agent workflows and secrets configured."""
    from app.ai_agent.repo_setup_service import RepositorySetupService
    from app.ai_agent.source_control import create_source_control_client
    from app.core.security import decrypt_value

    app_svc = AIAgentAppService(db)
    config = await app_svc.get_configuration(config_id, current_user.tenant_id)
    sc_token = decrypt_value(config.source_control_token_encrypted, settings.encryption_key)
    sc = create_source_control_client(
        config.source_control_type or "github", sc_token, config.repository_url
    )
    branch = await sc.get_default_branch()
    setup = RepositorySetupService(db)
    return await setup.get_setup_status(config, sc, branch)


@router.post("/configurations/{config_id}/setup-repository", response_model=RepositorySetupResponse)
async def setup_repository(
    config_id: uuid.UUID,
    body: RepositorySetupRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Push CI workflows to the repo and configure GitHub Actions secrets/variables."""
    from app.ai_agent.repo_setup_service import RepositorySetupService

    app_svc = AIAgentAppService(db)
    config = await app_svc.get_configuration(config_id, current_user.tenant_id)
    setup = RepositorySetupService(db)
    result = await setup.setup_repository(
        config,
        api_base_url=body.api_base_url,
        branch=body.branch,
    )
    return RepositorySetupResponse(
        success=result.success,
        steps=[
            RepositorySetupStepResponse(name=s.name, success=s.success, detail=s.detail)
            for s in result.steps
        ],
        manual_steps=result.manual_steps,
        callback_token_configured=result.callback_token_configured,
        api_base_url=result.api_base_url,
    )


# ── Generations ────────────────────────────────────────────────────────────────

@router.get("/generations", response_model=PagedResult)
async def list_generations(
    db: DBSession,
    current_user: AIAgentUser,
    config_id: Optional[uuid.UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = AIAgentService(db, websocket_manager=ws_manager)
    cid = config_id
    items, total = await svc.list_generations(current_user.tenant_id, cid, page, page_size)
    return {"items": [GenerationResponse.model_validate(i) for i in items], "total_count": total, "page": page, "page_size": page_size,
            "total_pages": math.ceil(total / page_size)}


@router.post("/generations", response_model=GenerationResponse, status_code=202)
async def create_generation(
    body: CreateGenerationRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    from app.domain.models.ai_agent import AIAgentGeneration
    from sqlalchemy import func as sa_func
    from datetime import timedelta

    # Tenant-scoped rate limit: max N generations per minute
    one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
    recent_count = (
        await db.execute(
            sa_select(sa_func.count()).select_from(AIAgentGeneration).where(
                AIAgentGeneration.tenant_id == current_user.tenant_id,
                AIAgentGeneration.created_at >= one_minute_ago,
            )
        )
    ).scalar() or 0
    if recent_count >= settings.ai_agent_rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: maximum {settings.ai_agent_rate_limit_per_minute} generation(s) per minute.",
        )

    svc = AIAgentService(db, websocket_manager=ws_manager)
    try:
        gen = await svc.create_generation(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            config_id=body.config_id,
            prompt=body.prompt,
            feature_name=body.feature_name,
            target_scope=body.target_scope,
            provider_override=body.provider_override,
            model_override=body.model_override,
            scheduled_release=body.scheduled_release,
        )
        return GenerationResponse.model_validate(gen)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/generations/{generation_id}", response_model=GenerationResponse)
async def get_generation(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentService(db)
    gen = await svc.get_generation(generation_id, current_user.tenant_id)
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    return GenerationResponse.model_validate(gen)


@router.post("/generations/{generation_id}/process", status_code=202)
async def process_generation(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Immediately trigger processing of a queued generation (kicks off the pipeline)."""
    import asyncio
    from app.ai_agent.ai_agent_service import AIAgentService
    from app.domain.models.ai_agent import AIAgentQueueItem

    svc = AIAgentService(db, websocket_manager=ws_manager)
    gen = await svc.get_generation(generation_id, current_user.tenant_id)
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")

    # Use SELECT FOR UPDATE SKIP LOCKED to atomically claim the queue item.
    # Two concurrent requests racing on the same generation_id will each see at
    # most one row to lock; the second request gets no rows and returns early.
    queue_item = (await db.execute(
        sa_select(AIAgentQueueItem).where(
            AIAgentQueueItem.generation_id == generation_id,
            AIAgentQueueItem.started_at.is_(None),
        ).with_for_update(skip_locked=True)
    )).scalar_one_or_none()

    if queue_item is None:
        # Already started or completed by the scheduler — don't run twice.
        return {"message": "Already processing.", "generation_id": generation_id}

    queue_item.started_at = datetime.now(timezone.utc)
    queue_item.status = "Running"
    await db.commit()

    gen_id = generation_id

    async def _run() -> None:
        """Background pipeline — uses its own DB session so the request session
        can be closed safely after the 202 response is returned."""
        from app.infrastructure.database import async_session_factory
        from app.infrastructure.websocket_manager import ws_manager as _ws
        from app.ai_agent.ai_agent_service import AIAgentService as _Svc
        from app.domain.models.ai_agent import AIAgentQueueItem as _QItem
        async with async_session_factory() as session:
            await _Svc(db=session, websocket_manager=_ws).process_generation(gen_id)
            # Mark completed so the queue view reflects the correct state.
            item = (await session.execute(
                sa_select(_QItem).where(_QItem.generation_id == gen_id)
            )).scalar_one_or_none()
            if item and item.completed_at is None:
                item.completed_at = datetime.now(timezone.utc)
                await session.commit()

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"message": "Processing started.", "generation_id": generation_id}


@router.get("/generations/{generation_id}/progress")
async def get_generation_progress(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Return all recorded progress events for a generation."""
    from app.domain.models.ai_agent import AIAgentGeneration, AIAgentProgressEvent as PEvent
    gen = (await db.execute(
        sa_select(AIAgentGeneration).where(
            AIAgentGeneration.id == generation_id,
            AIAgentGeneration.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    events = (await db.execute(
        sa_select(PEvent)
        .where(PEvent.generation_id == generation_id)
        .order_by(PEvent.created_at)
        .limit(500)
    )).scalars().all()
    return {
        "generation_id": generation_id,
        "status": gen.status,
        "events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "message": e.message,
                "step": e.step,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }


@router.post("/generations/{generation_id}/release")
async def release_generation(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentService(db, websocket_manager=ws_manager)
    try:
        await svc.release_generation(generation_id, current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Release triggered."}


@router.post("/generations/{generation_id}/revert")
async def revert_generation(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentService(db, websocket_manager=ws_manager)
    try:
        await svc.revert_generation(generation_id, current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Generation reverted."}


@router.post("/generations/{generation_id}/cancel")
async def cancel_generation(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentService(db, websocket_manager=ws_manager)
    try:
        await svc.cancel_generation(generation_id, current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Generation cancelled."}


@router.delete("/generations/{generation_id}", status_code=204)
async def delete_generation(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Hard-delete a generation record."""
    from app.domain.models.ai_agent import AIAgentGeneration
    gen = (await db.execute(
        sa_select(AIAgentGeneration).where(
            AIAgentGeneration.id == generation_id,
            AIAgentGeneration.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    await db.delete(gen)
    await db.commit()


class ScheduleReleaseRequest(BaseModel):
    scheduled_at: datetime
    notes: Optional[str] = None
    timezone: Optional[str] = None

    @field_validator("scheduled_at")
    @classmethod
    def must_be_future(cls, v: datetime) -> datetime:
        from datetime import timezone as _tz
        now = datetime.now(_tz.utc)
        # Make aware if naive (assume UTC)
        aware = v if v.tzinfo else v.replace(tzinfo=_tz.utc)
        if aware <= now:
            raise ValueError("scheduled_at must be a future datetime.")
        return aware


class RequestChangesRequest(BaseModel):
    notes: str = Field(..., min_length=1, max_length=2000)


@router.post("/generations/{generation_id}/deploy-staging")
async def deploy_staging(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Trigger the staging CI/CD workflow for a generation."""
    svc = AIAgentService(db, websocket_manager=ws_manager)
    try:
        await svc.deploy_staging_generation(generation_id, current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Staging deployment triggered.", "generation_id": generation_id}


@router.post("/generations/{generation_id}/request-changes")
async def request_changes(
    generation_id: uuid.UUID,
    body: RequestChangesRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Mark a generation as requiring changes after code review."""
    from app.domain.models.ai_agent import AIAgentGeneration
    gen = (await db.execute(
        sa_select(AIAgentGeneration).where(
            AIAgentGeneration.id == generation_id,
            AIAgentGeneration.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    gen.code_review_status = "ChangesRequested"
    gen.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Changes requested.", "reviewer_notes": body.notes}


@router.post("/generations/{generation_id}/reset-staging")
async def reset_staging(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Reset the staging environment for a generation."""
    from app.domain.models.ai_agent import AIAgentGeneration
    gen = (await db.execute(
        sa_select(AIAgentGeneration).where(
            AIAgentGeneration.id == generation_id,
            AIAgentGeneration.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    gen.staging_url = None
    gen.staging_build_status = None
    gen.staging_health_check_status = None
    gen.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Staging environment reset."}


@router.post("/generations/{generation_id}/schedule-release")
async def schedule_release(
    generation_id: uuid.UUID,
    body: ScheduleReleaseRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Schedule a generation to be released at a specific time."""
    from app.domain.models.ai_agent import AIAgentGeneration
    gen = (await db.execute(
        sa_select(AIAgentGeneration).where(
            AIAgentGeneration.id == generation_id,
            AIAgentGeneration.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    gen.scheduled_release_at = body.scheduled_at
    gen.scheduled_release_by_id = current_user.id
    gen.scheduled_release_notes = body.notes
    gen.scheduled_release_timezone = body.timezone
    gen.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {
        "message": "Release scheduled.",
        "scheduled_at": body.scheduled_at.isoformat(),
        "generation_id": generation_id,
    }


@router.delete("/generations/{generation_id}/schedule-release", status_code=204)
async def cancel_scheduled_release(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Cancel a pending scheduled release."""
    from app.domain.models.ai_agent import AIAgentGeneration
    gen = (await db.execute(
        sa_select(AIAgentGeneration).where(
            AIAgentGeneration.id == generation_id,
            AIAgentGeneration.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    gen.scheduled_release_at = None
    gen.scheduled_release_by_id = None
    gen.scheduled_release_notes = None
    gen.updated_at = datetime.now(timezone.utc)
    await db.commit()


@router.get("/generations/{generation_id}/schedule")
async def get_release_schedule(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Get the scheduled release info for a generation."""
    from app.domain.models.ai_agent import AIAgentGeneration
    gen = (await db.execute(
        sa_select(AIAgentGeneration).where(
            AIAgentGeneration.id == generation_id,
            AIAgentGeneration.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    return {
        "generation_id": generation_id,
        "scheduled_release_at": gen.scheduled_release_at.isoformat() if gen.scheduled_release_at else None,
        "scheduled_release_notes": gen.scheduled_release_notes,
        "scheduled_release_timezone": gen.scheduled_release_timezone,
        "is_scheduled": gen.scheduled_release_at is not None,
    }


# ── Singular aliases — mirrors .NET /generate and /generation/{id} naming ──────
# .NET AIAgentController uses "generate" (POST) and "generation/{id}" (singular).
# The Python backend uses the plural form; these aliases keep both working.

@router.post("/generate", response_model=GenerationResponse, status_code=202, include_in_schema=False)
async def create_generation_alias(
    body: CreateGenerationRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await create_generation(body, db, current_user)


@router.get("/generation/{generation_id}", response_model=GenerationResponse, include_in_schema=False)
async def get_generation_alias(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await get_generation(generation_id, db, current_user)


@router.delete("/generation/{generation_id}", status_code=204, include_in_schema=False)
async def delete_generation_alias(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await delete_generation(generation_id, db, current_user)


@router.post("/generation/{generation_id}/release", include_in_schema=False)
async def release_generation_alias(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await release_generation(generation_id, db, current_user)


@router.post("/generation/{generation_id}/revert", include_in_schema=False)
async def revert_generation_alias(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await revert_generation(generation_id, db, current_user)


@router.post("/generation/{generation_id}/cancel", include_in_schema=False)
async def cancel_generation_alias(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await cancel_generation(generation_id, db, current_user)


@router.post("/generation/{generation_id}/deploy-staging", include_in_schema=False)
async def deploy_staging_alias(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await deploy_staging(generation_id, db, current_user)


@router.post("/generation/{generation_id}/request-changes", include_in_schema=False)
async def request_changes_alias(
    generation_id: uuid.UUID,
    body: RequestChangesRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await request_changes(generation_id, body, db, current_user)


@router.post("/generation/{generation_id}/reset-staging", include_in_schema=False)
async def reset_staging_alias(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await reset_staging(generation_id, db, current_user)


@router.post("/generation/{generation_id}/schedule-release", include_in_schema=False)
async def schedule_release_alias(
    generation_id: uuid.UUID,
    body: ScheduleReleaseRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await schedule_release(generation_id, body, db, current_user)


@router.delete("/generation/{generation_id}/schedule-release", status_code=204, include_in_schema=False)
async def cancel_scheduled_release_alias(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await cancel_scheduled_release(generation_id, db, current_user)


@router.get("/generation/{generation_id}/schedule", include_in_schema=False)
async def get_release_schedule_alias(
    generation_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    return await get_release_schedule(generation_id, db, current_user)


# ── CI/CD callbacks (called by GitHub Actions) ────────────────────────────────

@router.post("/callback/build-status")
async def build_status_callback(
    body: BuildCallbackRequest,
    db: DBSession,
    _: str = Depends(verify_callback_token),
):
    svc = AIAgentService(db, websocket_manager=ws_manager)
    await svc.handle_build_callback(
        generation_id=body.generation_id,
        success=body.success,
        build_url=body.build_url,
        error=body.error,
    )
    return {"ok": True}


@router.post("/callback/deploy-status")
async def deploy_status_callback(
    body: DeployCallbackRequest,
    db: DBSession,
    _: str = Depends(verify_callback_token),
):
    svc = AIAgentService(db, websocket_manager=ws_manager)
    await svc.handle_deploy_callback(
        generation_id=body.generation_id,
        success=body.success,
        staging_url=body.staging_url,
        staging_frontend_url=body.staging_frontend_url,
        error=body.error,
    )
    return {"ok": True}


@router.post("/callback/release-status")
async def release_status_callback(
    body: ReleaseCallbackRequest,
    db: DBSession,
    _: str = Depends(verify_callback_token),
):
    svc = AIAgentService(db, websocket_manager=ws_manager)
    await svc.handle_release_callback(
        generation_id=body.generation_id,
        success=body.success,
        production_url=body.production_url,
        error=body.error,
    )
    return {"ok": True}


@router.post("/callback/pr-validation")
async def pr_validation_callback(
    body: PrValidationCallbackRequest,
    db: DBSession,
    _: str = Depends(verify_callback_token),
):
    svc = AIAgentService(db, websocket_manager=ws_manager)
    await svc.handle_pr_validation_callback(
        generation_id=body.generation_id,
        approved=body.approved,
        reviewer_notes=body.reviewer_notes,
    )
    return {"ok": True}


class BuildFixCallbackRequest(BaseModel):
    generation_id: uuid.UUID
    success: bool
    build_url: Optional[str] = None
    error: Optional[str] = None
    fix_applied: Optional[str] = None


@router.post("/callback/build-fix")
async def build_fix_callback(
    body: BuildFixCallbackRequest,
    db: DBSession,
    _: str = Depends(verify_callback_token),
):
    """Receive a build-fix result callback from CI."""
    from app.domain.models.ai_agent import AIAgentGeneration
    gen = (await db.execute(
        sa_select(AIAgentGeneration).where(AIAgentGeneration.id == body.generation_id)
    )).scalar_one_or_none()
    if gen:
        if body.success:
            gen.status = "BuildFixed"
            gen.pipeline_url = body.build_url
        else:
            gen.status = "Failed"
            gen.error_message = body.error
        gen.updated_at = datetime.now(timezone.utc)
        await db.commit()
    return {"ok": True}


class EmergencyRollbackRequest(BaseModel):
    generation_id: uuid.UUID
    reason: Optional[str] = None


@router.post("/emergency-rollback")
async def emergency_rollback(
    body: EmergencyRollbackRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Immediately revert a deployed generation."""
    svc = AIAgentService(db, websocket_manager=ws_manager)
    await svc.revert_generation(body.generation_id, current_user.tenant_id)
    return {"message": "Emergency rollback initiated.", "generation_id": str(body.generation_id)}


# ── Provider configs ───────────────────────────────────────────────────────────

@router.get("/providers")
async def list_provider_configs(
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentAppService(db)
    return await svc.get_provider_configs(current_user.tenant_id)


@router.post("/providers/models")
async def list_provider_models_route(
    body: ProviderProbeRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Live list of models (or Azure deployments) the supplied key can use. Nothing is saved."""
    return await AIAgentAppService(db).list_models(current_user.tenant_id, body)


@router.post("/providers/test")
async def test_provider_credentials(
    body: ProviderProbeRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Send a tiny request with unsaved credentials and return a readable result."""
    return await AIAgentAppService(db).test_credentials(current_user.tenant_id, body)


@router.post("/providers/azure/deployments")
async def list_azure_provider_deployments(
    body: AzureDeploymentsRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """List deployment names + models from an Azure OpenAI resource (for setup UI)."""
    from app.ai_agent.azure_config import list_azure_deployments
    from app.core.security import decrypt_value
    from app.services.ai_agent_app_service import AIAgentAppService, _validate_azure_openai_endpoint

    api_key = (body.api_key or "").strip()
    if not api_key and body.provider_id:
        try:
            cfg = await AIAgentAppService(db).get_provider_config_by_id(body.provider_id, current_user.tenant_id)
            api_key = decrypt_value(cfg.api_key_encrypted, settings.encryption_key)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required.")

    try:
        endpoint = _validate_azure_openai_endpoint(body.endpoint)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await list_azure_deployments(endpoint, api_key)
    if not result.deployments:
        raise HTTPException(status_code=502, detail=result.error or "Could not list deployments from Azure.")
    return {"deployments": result.deployments}


@router.get("/providers/{provider_id}")
async def get_provider_config(
    provider_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentAppService(db)
    return await svc.get_provider_config_by_id(provider_id, current_user.tenant_id)


@router.put("/providers/{provider_id}")
async def update_provider_config(
    provider_id: uuid.UUID,
    body: ProviderConfigRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Update an existing provider configuration by ID."""
    svc = AIAgentAppService(db)
    cfg = await svc.get_provider_config_by_id(provider_id, current_user.tenant_id)
    from app.core.security import encrypt_value
    # Only overwrite the encrypted key if a non-empty api_key was supplied
    if body.api_key:
        cfg.encrypted_api_key = encrypt_value(body.api_key, settings.encryption_key)
    if body.endpoint:
        cfg.endpoint_url = body.endpoint
    if body.display_name is not None:
        cfg.display_name = body.display_name.strip() or cfg.provider_name
    from app.ai_agent.azure_config import apply_azure_provider_fields, is_azure_provider
    if is_azure_provider(cfg.provider_name):
        apply_azure_provider_fields(
            cfg,
            deployment_name=body.deployment_name,
            model_name=body.model_name,
        )
    elif body.model_name:
        cfg.model_name = body.model_name
    cfg.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(cfg)
    return cfg


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider_config(
    provider_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentAppService(db)
    await svc.delete_provider_config(provider_id, current_user.tenant_id)


@router.post("/providers/{provider_id}/test")
async def test_provider(
    provider_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Test API-key connectivity for a saved provider configuration."""
    svc = AIAgentAppService(db)
    return await svc.test_provider_config(provider_id, current_user.tenant_id)


@router.post("/providers/{provider_id}/calibrate")
async def calibrate_provider(
    provider_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Trigger a background calibration run for a saved provider configuration."""
    # Verify the config exists and belongs to the tenant
    svc = AIAgentAppService(db)
    cfg = await svc.get_provider_config_by_id(provider_id, current_user.tenant_id)
    return {
        "message": "Calibration queued.",
        "provider_name": cfg.provider_name,
        "config_id": str(cfg.id),
        "status": "queued",
    }


@router.post("/providers")
async def create_provider_config(
    body: ProviderConfigRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    svc = AIAgentAppService(db)
    try:
        return await svc.create_provider_config(
            tenant_id=current_user.tenant_id,
            provider_name=body.provider_name,
            api_key=body.api_key,
            model_name=body.model_name,
            endpoint=body.endpoint,
            display_name=body.display_name,
            deployment_name=body.deployment_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Custom Domains ────────────────────────────────────────────────────────────

class AddDomainRequest(BaseModel):
    domain: str


@router.get("/domains/instructions/{domain_type}")
async def domain_instructions(domain_type: str):
    """Return DNS/CNAME setup instructions for the requested domain type."""
    instructions = {
        "cname": {
            "type": "CNAME",
            "record": "_verify.example.ffinn.cloud",
            "ttl": 300,
            "description": "Add a CNAME record pointing to our verification endpoint.",
        },
        "txt": {
            "type": "TXT",
            "record": "ffinn-verification=<token>",
            "ttl": 300,
            "description": "Add a TXT record with your verification token.",
        },
    }
    return instructions.get(domain_type.lower(), {"instructions": "Contact support for this domain type."})


@router.get("/domains")
async def list_domains(
    db: DBSession,
    current_user: AIAgentUser,
):
    """List custom domains registered for this tenant."""
    from app.domain.models.ai_agent import CustomDomain
    rows = (await db.execute(
        sa_select(CustomDomain).where(CustomDomain.tenant_id == current_user.tenant_id)
    )).scalars().all()
    return [
        {
            "id": str(d.id), "domain": d.domain, "status": d.status,
            "is_active": d.is_active,
            "last_verified_at": d.last_verified_at.isoformat() if d.last_verified_at else None,
        }
        for d in rows
    ]


@router.post("/domains", status_code=201)
async def add_domain(
    body: AddDomainRequest,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Register a custom domain for this tenant."""
    import secrets
    from app.domain.models.ai_agent import CustomDomain
    domain = CustomDomain(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        domain=body.domain,
        status="Pending",
        verification_token=f"ffinn-{secrets.token_urlsafe(16)}",
        is_active=False,
        created_by_id=current_user.id,
    )
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return {
        "id": str(domain.id), "domain": domain.domain,
        "status": domain.status, "verification_token": domain.verification_token,
    }


@router.post("/domains/{domain_id}/verify")
async def verify_domain(
    domain_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Initiate DNS verification for a domain."""
    from app.domain.models.ai_agent import CustomDomain
    domain = (await db.execute(
        sa_select(CustomDomain).where(
            CustomDomain.id == domain_id,
            CustomDomain.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found.")
    # INTEGRATION POINT: query DNS for the verification TXT/CNAME record here.
    domain.status = "Verifying"
    domain.last_verified_at = datetime.now(timezone.utc)
    await db.commit()
    return {"domain": domain.domain, "status": domain.status, "message": "Verification initiated."}


@router.post("/domains/{domain_id}/activate")
async def activate_domain(
    domain_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    """Activate a verified domain."""
    from app.domain.models.ai_agent import CustomDomain
    domain = (await db.execute(
        sa_select(CustomDomain).where(
            CustomDomain.id == domain_id,
            CustomDomain.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found.")
    if domain.status != "Verified":
        raise HTTPException(status_code=400, detail="Domain must be DNS-verified before it can be activated.")
    domain.is_active = True
    domain.status = "Active"
    await db.commit()
    return {"domain": domain.domain, "is_active": True, "status": "Active"}


@router.delete("/domains/{domain_id}", status_code=204)
async def delete_domain(
    domain_id: uuid.UUID,
    db: DBSession,
    current_user: AIAgentUser,
):
    from app.domain.models.ai_agent import CustomDomain
    await db.execute(
        sa_delete(CustomDomain).where(
            CustomDomain.id == domain_id,
            CustomDomain.tenant_id == current_user.tenant_id,
        )
    )
    await db.commit()


# ── /api/aiprovider/ aliases ─────────────────────────────────────────────────
# .NET exposes a separate AIProviderController at /api/aiprovider/ while the
# Python backend consolidates these under /api/aiagent/providers/.  These thin
# aliases ensure the Angular client works with both server implementations.

aiprovider_router = APIRouter(prefix="/api/aiprovider", tags=["AIProvider"], include_in_schema=False)


@aiprovider_router.get("")
async def aip_list(db: DBSession, current_user: AIAgentUser):
    return await list_provider_configs(db, current_user)


@aiprovider_router.get("/{provider_id}")
async def aip_get(provider_id: uuid.UUID, db: DBSession, current_user: AIAgentUser):
    return await get_provider_config(provider_id, db, current_user)


@aiprovider_router.post("", status_code=201)
async def aip_create(body: ProviderConfigRequest, db: DBSession, current_user: AIAgentUser):
    return await create_provider_config(body, db, current_user)


@aiprovider_router.put("/{provider_id}")
async def aip_update(provider_id: uuid.UUID, body: ProviderConfigRequest, db: DBSession, current_user: AIAgentUser):
    return await update_provider_config(provider_id, body, db, current_user)


@aiprovider_router.delete("/{provider_id}", status_code=204)
async def aip_delete(provider_id: uuid.UUID, db: DBSession, current_user: AIAgentUser):
    return await delete_provider_config(provider_id, db, current_user)


@aiprovider_router.post("/{provider_id}/test")
async def aip_test(provider_id: uuid.UUID, db: DBSession, current_user: AIAgentUser):
    return await test_provider(provider_id, db, current_user)


@aiprovider_router.post("/{provider_id}/calibrate")
async def aip_calibrate(provider_id: uuid.UUID, db: DBSession, current_user: AIAgentUser):
    return await calibrate_provider(provider_id, db, current_user)


# ── WebSocket ──────────────────────────────────────────────────────────────────

@router.post("/ws-ticket")
async def create_ws_ticket(
    db: DBSession,
    current_user: AIAgentUser,
):
    """Issue a short-lived one-time ticket for WebSocket auth (preferred over raw JWT)."""
    from app.services.auth_service import AuthService
    from app.services.host_settings import HostSettings
    hs = await HostSettings.load(db)
    svc = AuthService(db, host_settings=hs)
    ticket = await svc.create_ws_ticket(current_user.id, current_user.tenant_id)
    return {"ticket": ticket, "expires_in": 120}


@router.websocket("/ws/{tenant_id}")
async def ws_endpoint(websocket: WebSocket, tenant_id: str):
    """Real-time AI generation progress events.

    Authentication: send a one-time ticket or JWT as the first JSON frame:
        {"type": "auth", "ticket": "<ws-ticket>"}
        {"type": "auth", "token": "<jwt>"}  (legacy)
    """
    AUTH_TIMEOUT_SECONDS = 10

    # Accept the connection before inspecting auth so we can send a close frame.
    await websocket.accept()

    user = None

    # Reject legacy tokens in query string outright.
    if websocket.query_params.get("token"):
        await websocket.close(code=4400, reason="Token must not be passed via query string")
        return

    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
        msg = json.loads(raw)
        if msg.get("type") == "auth":
            ticket = msg.get("ticket")
            if ticket:
                from app.infrastructure.database import AsyncSessionLocal
                from app.services.auth_service import AuthService
                from app.services.host_settings import HostSettings
                from app.core.dependencies import CurrentUser
                async with AsyncSessionLocal() as session:
                    hs = await HostSettings.load(session)
                    svc = AuthService(session, host_settings=hs)
                    uid = await svc.redeem_ws_ticket(ticket, expected_tenant_id=tenant_id)
                    if uid:
                        from sqlalchemy import select
                        from app.domain.models.identity import IdentityUser
                        u = (await session.execute(
                            select(IdentityUser).where(IdentityUser.id == uid)
                        )).scalar_one_or_none()
                        if u and u.is_active:
                            user = CurrentUser(
                                id=u.id,
                                email=u.email,
                                username=u.user_name,
                                tenant_id=u.tenant_id,
                                roles=(),
                                permissions=(),
                            )
            else:
                from app.core.dependencies import _extract_current_user
                user = _extract_current_user(msg.get("token", ""))
    except Exception:
        pass

    if not user:
        await websocket.close(code=4401, reason="Authentication required")
        return

    # Enforce tenant isolation: the token tenant must match the requested channel
    if user.tenant_id is None or str(user.tenant_id) != tenant_id:
        await websocket.close(code=4403, reason="Forbidden: tenant mismatch")
        return

    await ws_manager.post_connect(websocket, tenant_id)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, tenant_id)
