"""
Tenant onboarding routes.

Endpoints:
  GET  /api/onboarding/config                        — (public) step definitions
  GET  /api/onboarding/status                        — current onboarding status
  POST /api/onboarding/start                         — initialise onboarding record
  POST /api/onboarding/steps/{step_name}/complete    — mark a step complete
  POST /api/onboarding/skip                          — skip all remaining steps
  POST /api/onboarding/complete                      — mark onboarding complete
  POST /api/onboarding/reset                         — reset (admin)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import DBSession, get_current_user, CurrentUser, AdminUser
from app.services.misc_services import OnboardingService

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


@router.get("/config")
async def get_config():
    """Return onboarding step definitions (no auth required)."""
    svc = OnboardingService(None)  # type: ignore[arg-type]
    return {"steps": svc.get_config()}


@router.get("/status")
async def get_status(db: DBSession, current_user: CurrentUser = Depends(get_current_user)):
    svc = OnboardingService(db)
    return await svc.get_status(current_user.tenant_id, current_user.id)


@router.post("/start")
async def start(db: DBSession, current_user: CurrentUser = Depends(get_current_user)):
    svc = OnboardingService(db)
    return await svc.start(current_user.tenant_id, current_user.id)


@router.post("/steps/{step_name}/complete")
async def complete_step(
    step_name: str,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
):
    svc = OnboardingService(db)
    return await svc.complete_step(current_user.tenant_id, current_user.id, step_name)


@router.post("/skip")
async def skip(db: DBSession, current_user: CurrentUser = Depends(get_current_user)):
    svc = OnboardingService(db)
    return await svc.skip(current_user.tenant_id, current_user.id)


@router.post("/complete")
async def mark_complete(db: DBSession, current_user: CurrentUser = Depends(get_current_user)):
    svc = OnboardingService(db)
    return await svc.mark_complete(current_user.tenant_id, current_user.id)


@router.post("/steps/{step_number}")
async def complete_step_by_number(
    step_number: int,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Mark a numbered wizard step complete (alternative to name-based endpoint)."""
    svc = OnboardingService(db)
    step_name = f"step_{step_number}"
    return await svc.complete_step(current_user.tenant_id, current_user.id, step_name)


@router.post("/reset")
async def reset(db: DBSession, current_user: AdminUser):
    svc = OnboardingService(db)
    return await svc.reset(current_user.tenant_id)
