"""
Main API router — registers all route modules.

IMPORTANT: This file is a bounded core file.
When adding AI-generated feature routers, insert them below the marker comment.
Do NOT remove the existing imports or routers.
"""
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.ai_agent import router as ai_agent_router, aiprovider_router
from app.api.ai_agent_chat import router as ai_agent_chat_router
from app.api.files import router as files_router
from app.api.management import (
    tenants_router,
    tenant_registration_router,
    roles_router,
    subscription_plans_router,
    subscriptions_router,
    settings_router,
    feature_flags_router,
    invitations_router,
    audit_router,
    dashboard_router,
)
from app.api.two_factor import router as two_factor_router
from app.api.permissions import router as permissions_router
from app.api.onboarding import router as onboarding_router
from app.api.editions import router as editions_router
from app.api.delegations import router as delegations_router
from app.api.monitoring import router as monitoring_router
from app.api.tenant_logo import router as tenant_logo_router
from app.api.features import router as features_router
from app.api.paywall import router as paywall_router
from app.api.sso import router as sso_router
from app.api.cloud_setup import router as cloud_setup_router
from app.api.notifications import router as notifications_router

api_router = APIRouter()

# ── Core framework routers ────────────────────────────────────────────────────
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(ai_agent_router)
api_router.include_router(aiprovider_router)
api_router.include_router(ai_agent_chat_router)
api_router.include_router(files_router)
api_router.include_router(tenants_router)
api_router.include_router(tenant_registration_router)
api_router.include_router(roles_router)
api_router.include_router(subscription_plans_router)
api_router.include_router(subscriptions_router)
api_router.include_router(settings_router)
api_router.include_router(feature_flags_router)
api_router.include_router(invitations_router)
api_router.include_router(audit_router)
api_router.include_router(dashboard_router)
api_router.include_router(two_factor_router)
api_router.include_router(permissions_router)
api_router.include_router(onboarding_router)
api_router.include_router(editions_router)
api_router.include_router(delegations_router)
api_router.include_router(monitoring_router)
api_router.include_router(tenant_logo_router)
api_router.include_router(features_router)
api_router.include_router(paywall_router)
api_router.include_router(sso_router)
api_router.include_router(cloud_setup_router)
api_router.include_router(notifications_router)

# AI-generated routers — DO NOT REMOVE THIS COMMENT
from app.api.projects import router as projects_router  # noqa: E402
api_router.include_router(projects_router)

# (new feature routers are appended here by the AI agent merge helper)
