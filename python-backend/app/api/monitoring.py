"""
Monitoring and diagnostics routes.

Endpoints:
  GET /api/monitoring/health            — basic liveness probe (anonymous)
  GET /api/monitoring/ai-agent/health   — check AI agent service connectivity (admin)
  GET /api/monitoring/system/info       — Python/platform info (admin)
  GET /api/diagnostics/encryption-status — verify JWT config is working (anonymous)
"""
from __future__ import annotations

import platform
import sys
import time
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.dependencies import DBSession, AdminUser, verify_callback_token

router = APIRouter(tags=["Monitoring"])
log = structlog.get_logger(__name__)

# Track startup time for uptime reporting
_START_TIME = time.time()


@router.get("/api/monitoring/health")
async def health():
    """Liveness probe — always returns 200 if the process is alive."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/monitoring/ai-agent/health")
async def ai_agent_health(db: DBSession, _: AdminUser):
    """Check whether the AI agent service is reachable and configured."""
    from sqlalchemy import select as sa_select, func as sa_func
    from app.domain.models.ai_agent import AIProviderConfiguration, AIAgentConfiguration
    try:
        provider_count = (
            await db.execute(sa_select(sa_func.count(AIProviderConfiguration.id)))
        ).scalar() or 0
        config_count = (
            await db.execute(sa_select(sa_func.count(AIAgentConfiguration.id)))
        ).scalar() or 0
        return {
            "status": "ok",
            "provider_count": provider_count,
            "config_count": config_count,
        }
    except Exception:
        log.exception("ai agent health check failed")
        return {
            "status": "degraded",
            "error": "Health check failed; see server logs.",
        }


@router.get("/api/monitoring/system/info")
async def system_info(_: AdminUser):
    """Return basic runtime information about the server process."""
    uptime_seconds = int(time.time() - _START_TIME)
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "uptime_seconds": uptime_seconds,
        "uptime_human": _humanize(uptime_seconds),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/diagnostics/encryption-status")
async def encryption_status(_: AdminUser):
    """
    Verify that JWT signing is configured correctly by issuing and verifying
    a test token.  Returns 200 OK when everything is healthy.
    Requires admin authentication (prevents disclosure of JWT configuration state).
    """
    from app.core.security import create_access_token, decode_token
    import uuid
    test_id = str(uuid.uuid4())
    try:
        token = create_access_token({"sub": test_id, "test": True})
        payload = decode_token(token)
        ok = payload.get("sub") == test_id
    except Exception:
        log.exception("jwt self-test failed")
        return {"status": "error", "detail": "JWT self-test failed; see server logs."}
    return {"status": "ok" if ok else "mismatch"}


@router.get("/api/monitoring/staging-demo-accounts")
async def staging_demo_accounts(db: DBSession, _: AdminUser):
    """List fake staging tenant login accounts for host QA (staging environment only)."""
    from app.staging_demo_seeder import list_staging_demo_accounts, should_seed_staging_demo

    if not should_seed_staging_demo():
        raise HTTPException(status_code=404, detail="Staging demo is not enabled in this environment.")
    return await list_staging_demo_accounts(db)


@router.post("/api/monitoring/seed-staging-demo")
async def seed_staging_demo_endpoint(
    db: DBSession,
    _: bool = Depends(verify_callback_token),
):
    """Re-run staging demo seed (CI callback or manual). Idempotent."""
    from app.staging_demo_seeder import seed_staging_demo, should_seed_staging_demo

    if not should_seed_staging_demo():
        raise HTTPException(status_code=404, detail="Staging demo is not enabled in this environment.")

    try:
        accounts = await seed_staging_demo(db)
    except Exception as exc:
        log.exception("Staging demo seed failed")
        raise HTTPException(status_code=500, detail=f"Seed failed: {exc}") from exc

    return {
        "success": True,
        "tenant_name": settings.staging_demo_tenant_name,
        "account_count": len(accounts),
        "accounts": accounts,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _humanize(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)
