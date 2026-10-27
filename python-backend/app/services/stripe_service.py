"""Stripe subscription and billing service."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BusinessException, NotFoundException
from app.domain.models.subscription import (
    EnhancedTenantSubscription,
    SubscriptionPlan,
    BillingHistory,
    StripeProcessedEvent,
)

log = structlog.get_logger(__name__)


class StripeService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._stripe = self._get_stripe()

    def _get_stripe(self):
        if not settings.stripe_secret_key:
            return None
        import stripe
        stripe.api_key = settings.stripe_secret_key
        return stripe

    async def create_checkout_session(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        success_url: str,
        cancel_url: str,
        billing_cycle: str = "monthly",
    ) -> str:
        if not self._stripe:
            raise BusinessException("Stripe is not configured.")
        plan = await self._get_plan(plan_id)
        price_id = (
            plan.stripe_price_id_annually
            if billing_cycle == "annual"
            else plan.stripe_price_id_monthly
        )
        if not price_id:
            raise BusinessException("Selected plan has no Stripe price ID configured.")

        session = await asyncio.to_thread(
            lambda: self._stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"tenant_id": str(tenant_id), "user_id": str(user_id), "plan_id": str(plan_id)},
                allow_promotion_codes=True,
            )
        )
        return session.url

    async def create_customer_portal_session(self, tenant_id: uuid.UUID, return_url: str) -> str:
        if not self._stripe:
            raise BusinessException("Stripe is not configured.")
        sub = await self._get_active_sub(tenant_id)
        if not sub or not sub.stripe_customer_id:
            raise NotFoundException("No active Stripe subscription found.")
        session = await asyncio.to_thread(
            lambda: self._stripe.billing_portal.Session.create(
                customer=sub.stripe_customer_id, return_url=return_url
            )
        )
        return session.url

    async def cancel_subscription(self, tenant_id: uuid.UUID) -> None:
        if not self._stripe:
            raise BusinessException("Stripe is not configured.")
        sub = await self._get_active_sub(tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise NotFoundException("No active subscription found.")
        await asyncio.to_thread(
            lambda: self._stripe.Subscription.modify(
                sub.stripe_subscription_id, cancel_at_period_end=True
            )
        )
        sub.cancel_at_period_end = True
        await self._db.commit()

    async def handle_webhook(self, payload: bytes, sig_header: str) -> None:
        if not self._stripe:
            return
        webhook_secret = settings.stripe_webhook_secret
        try:
            event = await asyncio.to_thread(
                lambda: self._stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            )
        except Exception as e:
            log.error("Stripe webhook signature error", error=str(e))
            raise BusinessException("Invalid webhook signature.")

        event_id = event.get("id")
        event_type = event["type"]

        # Idempotency: short-circuit duplicate deliveries (Stripe retries on non-2xx).
        # We try to insert the event_id first; on IntegrityError we treat as duplicate.
        if event_id:
            from sqlalchemy.exc import IntegrityError
            self._db.add(StripeProcessedEvent(event_id=event_id, event_type=event_type))
            try:
                await self._db.flush()
            except IntegrityError:
                await self._db.rollback()
                log.info("Stripe webhook duplicate ignored", event_id=event_id, event_type=event_type)
                return

        data = event["data"]["object"]

        if event_type == "checkout.session.completed":
            await self._handle_checkout_completed(data)
        elif event_type == "invoice.payment_succeeded":
            await self._handle_invoice_paid(data)
        elif event_type == "invoice.payment_failed":
            await self._handle_invoice_failed(data)
        elif event_type in ("customer.subscription.deleted", "customer.subscription.updated"):
            await self._handle_subscription_updated(data)

    async def _handle_checkout_completed(self, session: dict) -> None:
        meta = session.get("metadata", {})
        tenant_id = uuid.UUID(meta["tenant_id"])
        plan_id = uuid.UUID(meta["plan_id"])
        stripe_sub_id = session.get("subscription")
        stripe_customer_id = session.get("customer")

        stripe_sub = await asyncio.to_thread(
            lambda: self._stripe.Subscription.retrieve(stripe_sub_id)
        )

        existing = await self._get_active_sub(tenant_id)
        if existing:
            existing.status = "cancelled"

        sub = EnhancedTenantSubscription(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            plan_id=plan_id,
            stripe_subscription_id=stripe_sub_id,
            stripe_customer_id=stripe_customer_id,
            status="active",
            current_period_start=datetime.fromtimestamp(stripe_sub["current_period_start"], tz=timezone.utc),
            current_period_end=datetime.fromtimestamp(stripe_sub["current_period_end"], tz=timezone.utc),
            cancel_at_period_end=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._db.add(sub)
        await self._db.commit()
        log.info("Subscription activated", tenant_id=str(tenant_id), plan_id=str(plan_id))

    async def _handle_invoice_paid(self, invoice: dict) -> None:
        stripe_sub_id = invoice.get("subscription")
        if not stripe_sub_id:
            return
        result = await self._db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.stripe_subscription_id == stripe_sub_id
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            billing = BillingHistory(
                id=uuid.uuid4(),
                tenant_id=sub.tenant_id,
                subscription_id=sub.id,
                amount=invoice.get("amount_paid", 0) / 100,
                currency=invoice.get("currency", "usd").upper(),
                status="paid",
                stripe_invoice_id=invoice.get("id"),
                created_at=datetime.now(timezone.utc),
            )
            self._db.add(billing)
            await self._db.commit()

    async def _handle_invoice_failed(self, invoice: dict) -> None:
        stripe_sub_id = invoice.get("subscription")
        if not stripe_sub_id:
            return
        result = await self._db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.stripe_subscription_id == stripe_sub_id
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = "past_due"
            await self._db.commit()
            log.warning("Payment failed", tenant_id=str(sub.tenant_id))

    async def _handle_subscription_updated(self, stripe_sub: dict) -> None:
        result = await self._db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.stripe_subscription_id == stripe_sub["id"]
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = stripe_sub["status"]
            sub.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
            sub.current_period_end = datetime.fromtimestamp(
                stripe_sub["current_period_end"], tz=timezone.utc
            )
            sub.updated_at = datetime.now(timezone.utc)
            await self._db.commit()

    async def _get_plan(self, plan_id: uuid.UUID) -> SubscriptionPlan:
        result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
        plan = result.scalar_one_or_none()
        if not plan:
            raise NotFoundException("Subscription plan not found.")
        return plan

    async def _get_active_sub(self, tenant_id: uuid.UUID) -> Optional[EnhancedTenantSubscription]:
        result = await self._db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.tenant_id == tenant_id,
                EnhancedTenantSubscription.status.in_(["active", "trialing"]),
            ).order_by(EnhancedTenantSubscription.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_subscription_status(self, tenant_id: uuid.UUID) -> Optional[dict]:
        sub = await self._get_active_sub(tenant_id)
        if not sub:
            return None
        plan_result = await self._db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id)
        )
        plan = plan_result.scalar_one_or_none()
        return {
            "status": sub.status,
            "planId": str(sub.plan_id) if sub.plan_id else None,
            "planName": plan.display_name if plan else sub.plan_name or "Unknown",
            "plan_name": plan.display_name if plan else sub.plan_name or "Unknown",
            "currentPeriodEnd": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "cancelAtPeriodEnd": sub.cancel_at_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "paymentProvider": "stripe",
            "payment_provider": "stripe",
        }

    async def get_billing_history(
        self, tenant_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[BillingHistory], int]:
        from sqlalchemy import func
        q = select(BillingHistory).where(BillingHistory.tenant_id == tenant_id)
        total = (await self._db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        items = (
            await self._db.execute(
                q.order_by(BillingHistory.billing_date.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return list(items), total

    async def reactivate_subscription(self, tenant_id: uuid.UUID) -> None:
        """Undo a scheduled cancellation (cancel_at_period_end = False)."""
        if not self._stripe:
            raise BusinessException("Stripe is not configured.")
        sub = await self._get_active_sub(tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise NotFoundException("No active subscription found.")
        if not sub.cancel_at_period_end:
            raise BusinessException("Subscription is not scheduled for cancellation.")
        await asyncio.to_thread(
            lambda: self._stripe.Subscription.modify(
                sub.stripe_subscription_id, cancel_at_period_end=False
            )
        )
        sub.cancel_at_period_end = False
        sub.cancelled_at = None
        await self._db.commit()

    async def upgrade_subscription(
        self, tenant_id: uuid.UUID, new_plan_id: uuid.UUID, billing_cycle: str = "monthly"
    ) -> None:
        """Upgrade/downgrade to a different plan via Stripe subscription update."""
        if not self._stripe:
            raise BusinessException("Stripe is not configured.")
        sub = await self._get_active_sub(tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise NotFoundException("No active Stripe subscription found.")
        plan = await self._get_plan(new_plan_id)
        price_id = (
            plan.stripe_price_id_annually
            if billing_cycle == "annual"
            else plan.stripe_price_id_monthly
        )
        if not price_id:
            raise BusinessException("Selected plan has no Stripe price ID configured.")
        stripe_sub = await asyncio.to_thread(
            lambda: self._stripe.Subscription.retrieve(sub.stripe_subscription_id)
        )
        await asyncio.to_thread(
            lambda: self._stripe.Subscription.modify(
                sub.stripe_subscription_id,
                items=[{"id": stripe_sub["items"]["data"][0]["id"], "price": price_id}],
                proration_behavior="create_prorations",
            )
        )
        sub.plan_id = new_plan_id
        sub.plan_name = plan.name
        sub.billing_cycle = billing_cycle
        await self._db.commit()

    async def get_payment_methods(self, tenant_id: uuid.UUID) -> list[dict]:
        """List saved payment methods for a tenant's Stripe customer."""
        if not self._stripe:
            return []
        sub = await self._get_active_sub(tenant_id)
        if not sub or not sub.stripe_customer_id:
            return []
        pms = await asyncio.to_thread(
            lambda: self._stripe.PaymentMethod.list(
                customer=sub.stripe_customer_id, type="card"
            )
        )
        customer = await asyncio.to_thread(
            lambda: self._stripe.Customer.retrieve(sub.stripe_customer_id)
        )
        default_pm = customer.get("invoice_settings", {}).get("default_payment_method")
        return [
            {
                "id": pm["id"],
                "brand": pm["card"]["brand"],
                "last4": pm["card"]["last4"],
                "exp_month": pm["card"]["exp_month"],
                "exp_year": pm["card"]["exp_year"],
                "is_default": pm["id"] == default_pm,
            }
            for pm in pms.get("data", [])
        ]

    async def add_payment_method(self, tenant_id: uuid.UUID, payment_method_id: str) -> None:
        """Attach a payment method to the customer."""
        if not self._stripe:
            raise BusinessException("Stripe is not configured.")
        sub = await self._get_active_sub(tenant_id)
        if not sub or not sub.stripe_customer_id:
            raise NotFoundException("No active subscription found.")
        await asyncio.to_thread(
            lambda: self._stripe.PaymentMethod.attach(
                payment_method_id, customer=sub.stripe_customer_id
            )
        )

    async def _verify_payment_method_owner(
        self, tenant_id: uuid.UUID, payment_method_id: str
    ) -> str:
        """Return stripe_customer_id after verifying the PM belongs to this tenant."""
        sub = await self._get_active_sub(tenant_id)
        if not sub or not sub.stripe_customer_id:
            raise NotFoundException("No active subscription found.")
        pm = await asyncio.to_thread(
            lambda: self._stripe.PaymentMethod.retrieve(payment_method_id)
        )
        if pm.get("customer") != sub.stripe_customer_id:
            raise NotFoundException("Payment method not found.")
        return sub.stripe_customer_id

    async def remove_payment_method(self, tenant_id: uuid.UUID, payment_method_id: str) -> None:
        """Detach (remove) a payment method from the customer."""
        if not self._stripe:
            raise BusinessException("Stripe is not configured.")
        await self._verify_payment_method_owner(tenant_id, payment_method_id)
        await asyncio.to_thread(lambda: self._stripe.PaymentMethod.detach(payment_method_id))

    async def set_default_payment_method(self, tenant_id: uuid.UUID, payment_method_id: str) -> None:
        """Set the default payment method for the Stripe customer."""
        if not self._stripe:
            raise BusinessException("Stripe is not configured.")
        customer_id = await self._verify_payment_method_owner(tenant_id, payment_method_id)
        await asyncio.to_thread(
            lambda: self._stripe.Customer.modify(
                customer_id,
                invoice_settings={"default_payment_method": payment_method_id},
            )
        )
