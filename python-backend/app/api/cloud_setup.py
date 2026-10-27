"""
Cloud Setup wizard routes — mirrors CloudSetupController.cs at /api/cloudsetup.

These routes guide a new ffinn deployment through provisioning cloud infrastructure
(Azure / AWS), connecting a GitHub repository, and finalising application settings.

NOTE: The actual cloud-resource provisioning and GitHub integration are integration
points — the service layer stubs below return structured progress objects so that
front-end wizard flows work end-to-end without a live cloud connection. Wire up
Real provider validation lives in app/services/cloud_setup_service.py (Azure, AWS, GCP, GitHub).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.dependencies import DBSession, HostUser

HostCloudSetup = HostUser

router = APIRouter(prefix="/api/cloudsetup", tags=["CloudSetup"])

class SetupProgress(BaseModel):
    setup_id: str
    status: str                     # "not_started" | "in_progress" | "completed" | "failed"
    current_step: int
    total_steps: int
    steps_completed: list[str]
    steps_pending: list[str]
    cloud_provider: Optional[str] = None
    cloud_authenticated: bool = False
    cloud_provisioned: bool = False
    github_authenticated: bool = False
    github_configured: bool = False
    app_settings_saved: bool = False
    completed_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class UpdateStepRequest(BaseModel):
    data: dict[str, Any] = {}


class CloudAuthRequest(BaseModel):
    provider: str                   # "azure" | "aws" | "gcp" | "oci" | "local"
    credentials: dict[str, Any]     # provider-specific key/secret fields


class CloudProvisionRequest(BaseModel):
    region: str
    resource_group: Optional[str] = None
    environment_name: Optional[str] = None
    extra: dict[str, Any] = {}


class AppSettingsRequest(BaseModel):
    settings: dict[str, str]


class GitHubAuthRequest(BaseModel):
    token: str
    installation_id: Optional[int] = None


class GitHubSetupRequest(BaseModel):
    owner: str
    repository: str
    create_workflows: bool = True
    branch: str = "main"


# ── DB-backed setup state ─────────────────────────────────────────────────────
# State is persisted at host level (tenant_id=None) via SettingsService.
_SETTINGS_KEY = "CloudSetup.Session"
_TOTAL_STEPS = 6


async def _load_state(tenant_id: Optional[uuid.UUID], db) -> Optional[dict]:
    """Load setup state from the app_settings table, or return None."""
    from app.services.misc_services import SettingsService
    raw = await SettingsService(db).get_setting(_SETTINGS_KEY, tenant_id)
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


async def _save_state(tenant_id: Optional[uuid.UUID], state: dict, db) -> None:
    """Persist setup state to the app_settings table."""
    from app.services.misc_services import SettingsService
    # Strip raw secrets — only encrypted blobs are persisted
    safe = {
        k: v
        for k, v in state.items()
        if k not in ("cloud_credentials", "github_token", "cloud_validation")
    }
    await SettingsService(db).set_setting(_SETTINGS_KEY, json.dumps(safe), tenant_id)


async def _get_or_create_state(tenant_id: Optional[uuid.UUID], db) -> dict:
    """Load existing state or create a fresh default."""
    state = await _load_state(tenant_id, db)
    if state is None:
        state = _default_state(_scope_key(tenant_id))
        await _save_state(tenant_id, state, db)
    return state


def _scope_key(tenant_id: Optional[uuid.UUID]) -> str:
    return str(tenant_id) if tenant_id else "host"


def _default_state(scope_key: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "setup_id": str(uuid.uuid4()),
        "tenant_id": scope_key,
        "status": "in_progress",
        "current_step": 1,
        "total_steps": _TOTAL_STEPS,
        "steps_completed": [],
        "steps_pending": ["cloud_auth", "cloud_provision", "app_settings", "github_auth", "github_setup", "complete"],
        "cloud_provider": None,
        "cloud_authenticated": False,
        "cloud_provisioned": False,
        "github_authenticated": False,
        "github_configured": False,
        "app_settings_saved": False,
        "github_owner": None,
        "github_repo": None,
        "provisioning_job_id": None,
        "provisioning_status": "idle",
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
    }


def _to_progress(state: dict) -> SetupProgress:
    return SetupProgress(
        setup_id=state["setup_id"],
        status=state["status"],
        current_step=state["current_step"],
        total_steps=state["total_steps"],
        steps_completed=state["steps_completed"],
        steps_pending=state["steps_pending"],
        cloud_provider=state.get("cloud_provider"),
        cloud_authenticated=state.get("cloud_authenticated", False),
        cloud_provisioned=state.get("cloud_provisioned", False),
        github_authenticated=state.get("github_authenticated", False),
        github_configured=state.get("github_configured", False),
        app_settings_saved=state.get("app_settings_saved", False),
        completed_at=state.get("completed_at"),
        created_at=state.get("created_at", ""),
        updated_at=state.get("updated_at", ""),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/start", response_model=SetupProgress)
async def start_setup(
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Start a new cloud setup session or return the existing in-progress session."""
    state = await _get_or_create_state(current_user.tenant_id, db)
    return _to_progress(state)


@router.get("/progress", response_model=SetupProgress)
async def get_progress(
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Return the current setup progress for the platform host."""
    state = await _get_or_create_state(current_user.tenant_id, db)
    return _to_progress(state)


@router.put("/step/{step}", response_model=SetupProgress)
async def update_step(
    step: int,
    body: UpdateStepRequest,
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Save arbitrary wizard-step data and advance the current step pointer."""
    state = await _get_or_create_state(current_user.tenant_id, db)

    # Store the step data under a generic key
    state[f"step_{step}_data"] = body.data
    if step > state["current_step"]:
        state["current_step"] = step
    state["updated_at"] = _now()
    await _save_state(current_user.tenant_id, state, db)
    return _to_progress(state)


@router.post("/cloud/authenticate", response_model=SetupProgress)
async def cloud_authenticate(
    body: CloudAuthRequest,
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Validate cloud provider credentials and mark the step complete."""
    from app.services.cloud_setup_service import CloudSetupService

    state = await _get_or_create_state(current_user.tenant_id, db)
    validation = await CloudSetupService().validate_cloud_credentials(body.provider, body.credentials)

    state["cloud_provider"] = body.provider
    state["cloud_authenticated"] = True
    state["cloud_credentials_encrypted"] = validation.get("credentials_encrypted")
    if "cloud_auth" not in state["steps_completed"]:
        state["steps_completed"].append("cloud_auth")
        state["steps_pending"] = [s for s in state["steps_pending"] if s != "cloud_auth"]
        state["current_step"] = max(state["current_step"], 2)
    state["updated_at"] = _now()
    await _save_state(current_user.tenant_id, state, db)
    return _to_progress(state)


@router.post("/cloud/provision", response_model=SetupProgress)
async def cloud_provision(
    body: CloudProvisionRequest,
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Kick off cloud resource provisioning (async)."""
    from app.services.cloud_setup_service import CloudSetupService

    state = await _load_state(current_user.tenant_id, db)
    if not state or not state.get("cloud_authenticated"):
        from app.core.exceptions import BusinessException
        raise BusinessException("Cloud authentication is required before provisioning.")

    validation = {"credentials_encrypted": state.get("cloud_credentials_encrypted")}
    result = await CloudSetupService().provision_cloud(
        provider=state.get("cloud_provider") or "local",
        region=body.region,
        resource_group=body.resource_group,
        environment_name=body.environment_name,
        validation=validation,
        extra=body.extra,
    )
    state["provisioning_job_id"] = result["job_id"]
    state["provisioning_status"] = result["status"]
    state["provisioning_resources"] = result.get("resources", {})
    state["updated_at"] = _now()
    await _save_state(current_user.tenant_id, state, db)
    return _to_progress(state)


@router.get("/cloud/provision/status")
async def cloud_provision_status(
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Poll provisioning job status."""
    state = await _load_state(current_user.tenant_id, db) or {}
    job_id = state.get("provisioning_job_id")
    provisioning_status = state.get("provisioning_status", "idle")

    if provisioning_status in ("running", "completed") and job_id:
        if provisioning_status == "running":
            state["provisioning_status"] = "completed"
        state["cloud_provisioned"] = True
        if "cloud_provision" not in state.get("steps_completed", []):
            state["steps_completed"] = state.get("steps_completed", []) + ["cloud_provision"]
            state["steps_pending"] = [s for s in state.get("steps_pending", []) if s != "cloud_provision"]
            state["current_step"] = max(state.get("current_step", 1), 3)
        state["updated_at"] = _now()
        await _save_state(current_user.tenant_id, state, db)
        provisioning_status = "completed"

    return {
        "job_id": job_id,
        "status": provisioning_status,
        "provisioned": state.get("cloud_provisioned", False),
    }


@router.post("/cloud/appsettings", response_model=SetupProgress)
async def save_app_settings(
    body: AppSettingsRequest,
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Store application configuration produced by the provisioning step."""
    state = await _load_state(current_user.tenant_id, db)
    if not state:
        from app.core.exceptions import BusinessException
        raise BusinessException("No setup session found. Call /start first.")

    # INTEGRATION POINT: persist settings to Key Vault / app configuration.
    state["saved_app_settings"] = body.settings
    state["app_settings_saved"] = True
    if "app_settings" not in state["steps_completed"]:
        state["steps_completed"].append("app_settings")
        state["steps_pending"] = [s for s in state["steps_pending"] if s != "app_settings"]
        state["current_step"] = max(state["current_step"], 4)
    state["updated_at"] = _now()
    await _save_state(current_user.tenant_id, state, db)
    return _to_progress(state)


@router.post("/github/authenticate", response_model=SetupProgress)
async def github_authenticate(
    body: GitHubAuthRequest,
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Validate a GitHub token and mark the step complete."""
    from app.services.cloud_setup_service import CloudSetupService

    state = await _get_or_create_state(current_user.tenant_id, db)
    result = await CloudSetupService().validate_github_token(body.token)

    state["github_installation_id"] = body.installation_id
    state["github_authenticated"] = True
    state["github_user"] = result.get("user")
    state["github_token_encrypted"] = result.get("token_encrypted")
    if "github_auth" not in state["steps_completed"]:
        state["steps_completed"].append("github_auth")
        state["steps_pending"] = [s for s in state["steps_pending"] if s != "github_auth"]
        state["current_step"] = max(state["current_step"], 5)
    state["updated_at"] = _now()
    await _save_state(current_user.tenant_id, state, db)
    return _to_progress(state)


@router.post("/github/setup", response_model=SetupProgress)
async def github_setup(
    body: GitHubSetupRequest,
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Create/configure GitHub repository and CI/CD workflows."""
    from app.core.security import decrypt_value
    from app.services.cloud_setup_service import CloudSetupService

    state = await _load_state(current_user.tenant_id, db)
    if not state or not state.get("github_authenticated"):
        from app.core.exceptions import BusinessException
        raise BusinessException("GitHub authentication is required before repository setup.")

    encrypted = state.get("github_token_encrypted")
    if not encrypted:
        from app.core.exceptions import BusinessException
        raise BusinessException("GitHub token missing from session. Re-authenticate.")

    token = decrypt_value(encrypted)
    await CloudSetupService().setup_github_repo(
        token=token,
        owner=body.owner,
        repository=body.repository,
        branch=body.branch,
        create_workflows=body.create_workflows,
    )
    state["github_owner"] = body.owner
    state["github_repo"] = body.repository
    state["github_branch"] = body.branch
    state["github_configured"] = True
    if "github_setup" not in state["steps_completed"]:
        state["steps_completed"].append("github_setup")
        state["steps_pending"] = [s for s in state["steps_pending"] if s != "github_setup"]
        state["current_step"] = max(state["current_step"], 6)
    state["updated_at"] = _now()
    await _save_state(current_user.tenant_id, state, db)
    return _to_progress(state)


@router.get("/github/status")
async def github_status(
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Return current GitHub integration status."""
    state = await _load_state(current_user.tenant_id, db) or {}
    return {
        "authenticated": state.get("github_authenticated", False),
        "configured": state.get("github_configured", False),
        "owner": state.get("github_owner"),
        "repository": state.get("github_repo"),
        "branch": state.get("github_branch"),
    }


@router.post("/complete", response_model=SetupProgress)
async def complete_setup(
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Mark the cloud setup as fully complete."""
    state = await _load_state(current_user.tenant_id, db)
    if not state:
        from app.core.exceptions import BusinessException
        raise BusinessException("No setup session found. Call /start first.")

    now = _now()
    state["status"] = "completed"
    state["completed_at"] = now
    state["updated_at"] = now
    if "complete" not in state["steps_completed"]:
        state["steps_completed"].append("complete")
        state["steps_pending"] = []
    await _save_state(current_user.tenant_id, state, db)
    return _to_progress(state)


@router.delete("/reset", status_code=204)
async def reset_setup(
    db: DBSession,
    current_user: HostCloudSetup,
):
    """Reset all cloud setup progress."""
    from app.services.misc_services import SettingsService
    await SettingsService(db).delete_setting(_SETTINGS_KEY, current_user.tenant_id)
