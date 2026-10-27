"""
ffinn Python Backend — FastAPI application entry point.
"""
from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.security_middleware import (
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
    RequestLoggingMiddleware,
    rate_limiter,
)
from app.infrastructure.database import init_db, close_db, async_session_factory
from app.api.router import api_router
from app.infrastructure.background_tasks import scheduler
from app.data_seeder import seed_roles, seed_admin_user, seed_subscription_plans, seed_feature_flags, seed_app_settings

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup → yield → shutdown."""
    # ── Startup ──────────────────────────────────────────────────────────────
    log.info("=== ffinn Python API Starting ===", environment=settings.environment)

    await init_db()

    # Seed default data (idempotent — safe to run on every startup)
    async with async_session_factory() as db:
        await seed_roles(db)
        await seed_admin_user(db)
        await seed_subscription_plans(db)
        await seed_feature_flags(db)
        await seed_app_settings(db)
        from app.staging_demo_seeder import (
            seed_staging_demo,
            should_seed_staging_demo,
            repair_staging_demo_users_if_missing,
        )
        if should_seed_staging_demo():
            try:
                accounts = await seed_staging_demo(db)
                if accounts:
                    log.info(
                        "Staging demo accounts ready",
                        tenant=settings.staging_demo_tenant_name,
                        roles=[a["role"] for a in accounts],
                    )
            except Exception as exc:
                log.exception("Staging demo seed failed on startup", error=str(exc))
        else:
            try:
                accounts = await repair_staging_demo_users_if_missing(db)
                if accounts:
                    log.info(
                        "Staging demo tenant repaired with role users",
                        tenant=settings.staging_demo_tenant_name,
                        roles=[a["role"] for a in accounts],
                    )
            except Exception as exc:
                log.exception("Staging demo repair failed on startup", error=str(exc))
    log.info("Database seeding complete")

    # Reset AI generation queue items that were in-flight when the app last shut down.
    # Any item with started_at set but no completed_at older than ai_agent_timeout_minutes
    # is assumed to be stuck and is returned to "Queued" so the scheduler re-processes it.
    async with async_session_factory() as db:
        from sqlalchemy import select as _select
        from datetime import timedelta
        from app.domain.models.ai_agent import AIAgentQueueItem
        timeout_ago = datetime.now(timezone.utc) - timedelta(minutes=settings.ai_agent_timeout_minutes)
        stuck_items = (
            await db.execute(
                _select(AIAgentQueueItem).where(
                    AIAgentQueueItem.started_at.is_not(None),
                    AIAgentQueueItem.completed_at.is_(None),
                    AIAgentQueueItem.started_at <= timeout_ago,
                )
            )
        ).scalars().all()
        for item in stuck_items:
            item.started_at = None
            item.status = "Queued"
        if stuck_items:
            await db.commit()
            log.warning("Reset stuck AI generation queue items", count=len(stuck_items))

    # Start background schedulers (disabled in pytest via DISABLE_BACKGROUND_SCHEDULER)
    if os.environ.get("DISABLE_BACKGROUND_SCHEDULER") != "true":
        scheduler.start()
        log.info("Background scheduler started")

    # Ensure upload directory exists
    os.makedirs(settings.local_storage_path, exist_ok=True)

    log.info(
        "ffinn API ready",
        base_url=settings.app_url,
        docs_url="/docs",
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    if os.environ.get("DISABLE_BACKGROUND_SCHEDULER") != "true":
        scheduler.shutdown(wait=False)
    await close_db()
    log.info("ffinn API stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="ffinn API",
        description=(
            "ffinn Application Framework — Python Backend. "
            "Multi-tenant applications with AI agent code generation."
        ),
        version=settings.app_version,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    # Rate limiter state (must be on app.state for slowapi)
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    app.state.limiter = rate_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Request size limit (before other middleware reads the body)
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_bytes=settings.max_request_body_mb * 1_048_576,
    )

    # OWASP security headers
    app.add_middleware(
        SecurityHeadersMiddleware,
        force_https=settings.force_https,
    )

    # Structured request logging (strips auth headers)
    app.add_middleware(RequestLoggingMiddleware)

    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # CORS — explicit allow-list only. With allow_credentials=True, a wildcard or
    # broad regex would allow ANY site to make authenticated requests. Configure
    # additional origins via CORS_ORIGINS_RAW or CORS_ORIGIN_REGEX env vars.
    cors_origins = list(settings.cors_origins)
    if settings.app_url and settings.app_url not in cors_origins:
        cors_origins.append(settings.app_url)
    cors_kwargs: dict = dict(
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-Id", "X-Request-Id", "Accept"],
        expose_headers=["X-Total-Count", "X-Request-Id"],
    )
    if settings.cors_origin_regex:
        cors_kwargs["allow_origin_regex"] = settings.cors_origin_regex
    elif settings.is_development:
        # In dev, also allow localhost on any port without forcing the user to list each one.
        cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    app.add_middleware(CORSMiddleware, **cors_kwargs)

    # Request timing / tracing middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routes ───────────────────────────────────────────────────────────────
    app.include_router(api_router)

    # ── Static files (uploaded logos, etc.) ──────────────────────────────────
    uploads_path = settings.local_storage_path
    os.makedirs(uploads_path, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")

    # ── Stripe webhook URL alias (/api/webhooks/stripe mirrors .NET route) ─────
    from typing import Annotated
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import Depends as _Depends
    from app.core.dependencies import get_db

    @app.post("/api/webhooks/stripe", tags=["Webhooks"], include_in_schema=False)
    async def stripe_webhook_alias(
        request: Request,
        db: Annotated[AsyncSession, _Depends(get_db)],
    ):
        """URL alias for .NET StripeWebhookController — delegates to the Stripe service."""
        from app.services.stripe_service import StripeService
        payload = await request.body()
        sig = request.headers.get("stripe-signature", "")
        await StripeService(db).handle_webhook(payload, sig)
        return {"received": True}

    # ── Health check ─────────────────────────────────────────────────────────
    @app.get("/health", tags=["health"], include_in_schema=False)
    async def health():
        return {"status": "healthy", "version": settings.app_version}

    @app.get("/", tags=["health"], include_in_schema=False)
    async def root():
        return {
            "name": "ffinn API",
            "version": settings.app_version,
            "docs": "/docs",
        }

    return app


app = create_app()
