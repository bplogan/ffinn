"""
APScheduler background workers:
- Subscription expiry notifications & deactivation
- AI agent generation queue processor
- Scheduled generation release
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.config import settings
from app.infrastructure.database import async_session_factory

log = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


# ── Subscription expiry worker ─────────────────────────────────────────────────
@scheduler.scheduled_job("cron", hour=1, minute=0, id="subscription_expiry_check")
async def check_subscription_expiry() -> None:
    """Notify tenants nearing expiry and disable expired subscriptions."""
    from app.domain.models.subscription import EnhancedTenantSubscription
    from app.domain.models.identity import IdentityUser, IdentityUserRole, IdentityRole

    async with async_session_factory() as db:
        from app.services.host_settings import HostSettings
        hs = await HostSettings.load(db)
        email_svc = hs.build_email_service()

        now = datetime.now(timezone.utc)
        notify_days = settings.subscription_notification_days_list  # e.g. [7, 3, 1]

        for days_before in notify_days:
            target_date = now + timedelta(days=days_before)
            result = await db.execute(
                select(EnhancedTenantSubscription).where(
                    EnhancedTenantSubscription.status == "active",
                    EnhancedTenantSubscription.current_period_end.between(
                        target_date.replace(hour=0, minute=0, second=0),
                        target_date.replace(hour=23, minute=59, second=59),
                    ),
                )
            )
            subscriptions = result.scalars().all()
            for sub in subscriptions:
                # Get tenant admin — query via role membership (no is_admin column)
                admin = await db.execute(
                    select(IdentityUser)
                    .join(IdentityUser.roles)
                    .join(IdentityUserRole.role)
                    .where(
                        IdentityUser.tenant_id == sub.tenant_id,
                        IdentityRole.normalized_name == "ADMIN",
                    )
                    .limit(1)
                )
                user = admin.scalar_one_or_none()
                if user and user.email:
                    await email_svc.send_subscription_expiry(
                        to=user.email,
                        name=user.full_name or user.user_name,
                        expiry_date=sub.current_period_end.strftime("%B %d, %Y"),
                    )
                    log.info("Expiry notif sent", tenant_id=str(sub.tenant_id), days=days_before)

        # Deactivate past-due subscriptions
        expired_result = await db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.status == "active",
                EnhancedTenantSubscription.current_period_end < now,
                EnhancedTenantSubscription.cancel_at_period_end is True,
            )
        )
        for sub in expired_result.scalars().all():
            sub.status = "expired"
            log.info("Subscription expired", tenant_id=str(sub.tenant_id))
        await db.commit()


# ── AI Generation queue processor ─────────────────────────────────────────────
@scheduler.scheduled_job("interval", seconds=30, id="ai_generation_queue")
async def process_ai_generation_queue() -> None:
    """Pick up queued AI generations and process them.

    Each generation is processed in its own DB session so that a failure in
    one does not contaminate the session state for the others.  We claim all
    items atomically (FOR UPDATE SKIP LOCKED) in a single short-lived session
    before spawning per-item work.
    """
    from app.domain.models.ai_agent import AIAgentQueueItem

    # Claim up to 3 items atomically, skipping any already locked by the
    # /process endpoint or a concurrent scheduler invocation.
    claimed_gen_ids: list = []
    async with async_session_factory() as db:
        result = await db.execute(
            select(AIAgentQueueItem)
            .where(AIAgentQueueItem.started_at.is_(None))
            .order_by(AIAgentQueueItem.priority.desc(), AIAgentQueueItem.queued_at.asc())
            .limit(3)
            .with_for_update(skip_locked=True)
        )
        queue_items = result.scalars().all()
        for item in queue_items:
            item.started_at = datetime.now(timezone.utc)
            item.status = "Running"
            claimed_gen_ids.append(item.generation_id)
        if claimed_gen_ids:
            await db.commit()

    # Process each claimed generation in its own isolated session.
    for gen_id in claimed_gen_ids:
        try:
            async with async_session_factory() as session:
                from app.ai_agent.ai_agent_service import AIAgentService
                from app.infrastructure.websocket_manager import ws_manager
                from app.domain.models.ai_agent import AIAgentQueueItem as QItem
                await AIAgentService(db=session, websocket_manager=ws_manager).process_generation(gen_id)
                q = (await session.execute(
                    select(QItem).where(QItem.generation_id == gen_id)
                )).scalar_one_or_none()
                if q and q.completed_at is None:
                    q.completed_at = datetime.now(timezone.utc)
                    await session.commit()
        except Exception as exc:
            log.error("Queue processing error", generation_id=str(gen_id), error=str(exc))


# ── Scheduled release processor ───────────────────────────────────────────────
@scheduler.scheduled_job("interval", minutes=5, id="scheduled_release")
async def process_scheduled_releases() -> None:
    """Release generations that have reached their scheduled release time."""
    from app.domain.models.ai_agent import AIAgentGeneration
    from app.ai_agent.ai_agent_service import AIAgentService, GenerationStatus
    from app.infrastructure.websocket_manager import ws_manager

    async with async_session_factory() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(AIAgentGeneration).where(
                AIAgentGeneration.status.in_(
                    [GenerationStatus.READY, GenerationStatus.STAGING]
                ),
                AIAgentGeneration.scheduled_release_at <= now,
                AIAgentGeneration.scheduled_release_at.is_not(None),
            )
        )
        generations = result.scalars().all()
        service = AIAgentService(db=db, websocket_manager=ws_manager)
        for gen in generations:
            try:
                await service.release_generation(gen.id, gen.tenant_id)
                log.info("Scheduled release triggered", generation_id=str(gen.id))
            except Exception as exc:
                log.error("Scheduled release failed", generation_id=str(gen.id), error=str(exc))


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()
        log.info("APScheduler started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("APScheduler stopped")
