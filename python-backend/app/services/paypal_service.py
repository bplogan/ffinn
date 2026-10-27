"""PayPal Subscriptions billing service — mirrors StripeService patterns."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BusinessException, NotFoundException
from app.domain.models.subscription import (
    BillingHistory,
    EnhancedTenantSubscription,
    PaypalProcessedEvent,
    SubscriptionPlan,
)

log = structlog.get_logger(__name__)


class PayPalService:
    def __init__(self, db: AsyncSession):
        self._db = db

    def _api_base(self) -> str:
        return (
            "https://api-m.sandbox.paypal.com"
            if settings.paypal_mode.lower() == "sandbox"
            else "https://api-m.paypal.com"
        )

    def _web_base(self) -> str:
        return (
            "https://www.sandbox.paypal.com"
            if settings.paypal_mode.lower() == "sandbox"
            else "https://www.paypal.com"
        )

    async def _load_credentials(self) -> tuple[str, str]:
        from app.services.misc_services import SettingsService

        svc = SettingsService(self._db)
        client_id = await svc.get_setting("payments.paypal_client_id", None) or settings.paypal_client_id
        client_secret = await svc.get_setting("payments.paypal_client_secret", None) or settings.paypal_client_secret
        if not client_id or not client_secret:
            raise BusinessException("PayPal is not configured.")
        return client_id, client_secret

    async def _load_webhook_id(self) -> str:
        from app.services.misc_services import SettingsService

        svc = SettingsService(self._db)
        return await svc.get_setting("payments.paypal_webhook_id", None) or settings.paypal_webhook_id or ""

    async def _access_token(self) -> str:
        client_id, client_secret = await self._load_credentials()
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self._api_base()}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                headers={"Accept": "application/json"},
            )
            if resp.status_code >= 400:
                raise BusinessException("PayPal authentication failed.")
            return resp.json()["access_token"]

    async def _verify_webhook_signature(self, payload: bytes, headers: dict[str, str]) -> None:
        webhook_id = await self._load_webhook_id()
        if not webhook_id:
            if settings.environment.lower() in ("production", "prod"):
                raise BusinessException("PayPal webhook ID is not configured.")
            log.warning("PayPal webhook signature verification skipped (no webhook ID)")
            return

        def _header(name: str) -> str:
            for k, v in headers.items():
                if k.lower() == name.lower():
                    return v
            return ""

        transmission_id = _header("paypal-transmission-id")
        transmission_time = _header("paypal-transmission-time")
        transmission_sig = _header("paypal-transmission-sig")
        cert_url = _header("paypal-cert-url")
        auth_algo = _header("paypal-auth-algo")
        if not all([transmission_id, transmission_time, transmission_sig, cert_url, auth_algo]):
            raise BusinessException("Missing PayPal webhook signature headers.")

        token = await self._access_token()
        body = json.loads(payload.decode())
        verify_payload = {
            "auth_algo": auth_algo,
            "cert_url": cert_url,
            "transmission_id": transmission_id,
            "transmission_sig": transmission_sig,
            "transmission_time": transmission_time,
            "webhook_id": webhook_id,
            "webhook_event": body,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self._api_base()}/v1/notifications/verify-webhook-signature",
                json=verify_payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            if resp.status_code >= 400:
                log.warning("PayPal webhook verify HTTP error", status=resp.status_code, body=resp.text[:300])
                raise BusinessException("PayPal webhook verification failed.")
            data = resp.json()
            if data.get("verification_status") != "SUCCESS":
                raise BusinessException("Invalid PayPal webhook signature.")

    async def create_subscription_checkout(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        billing_cycle: str,
        return_url: str,
        cancel_url: str,
    ) -> str:
        plan = await self._get_plan(plan_id)
        paypal_plan_id = (
            plan.paypal_plan_id_annually if billing_cycle == "annual" else plan.paypal_plan_id_monthly
        )
        if not paypal_plan_id:
            raise BusinessException("Selected plan has no PayPal plan ID configured.")

        token = await self._access_token()
        payload = {
            "plan_id": paypal_plan_id,
            "application_context": {
                "brand_name": settings.app_name,
                "user_action": "SUBSCRIBE_NOW",
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
            "custom_id": f"{tenant_id}|{user_id}|{plan_id}|{billing_cycle}",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._api_base()}/v1/billing/subscriptions",
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            if resp.status_code >= 400:
                log.warning("PayPal subscription create failed", body=resp.text[:400])
                raise BusinessException("PayPal checkout creation failed.")
            data = resp.json()

        for link in data.get("links", []):
            if link.get("rel") == "approve":
                return link["href"]
        raise BusinessException("PayPal did not return an approval URL.")

    async def confirm_subscription(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        subscription_id: str,
    ) -> dict:
        """Activate local subscription after user approves on PayPal (return URL handler)."""
        existing = await self._db.execute(
            select(EnhancedTenantSubscription).where(
                EnhancedTenantSubscription.paypal_subscription_id == subscription_id,
            )
        )
        if existing.scalar_one_or_none():
            raise BusinessException("This PayPal subscription is already linked to an account.")

        token = await self._access_token()
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{self._api_base()}/v1/billing/subscriptions/{subscription_id}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            if resp.status_code >= 400:
                raise BusinessException("Could not verify PayPal subscription.")
            resource = resp.json()

        custom_id = resource.get("custom_id") or ""
        parts = custom_id.split("|")
        if len(parts) < 4:
            raise BusinessException("PayPal subscription is missing required metadata.")
        if str(tenant_id) != parts[0] or str(user_id) != parts[1]:
            raise BusinessException("PayPal subscription does not belong to this account.")

        status = resource.get("status", "").upper()
        if status not in ("ACTIVE", "APPROVED"):
            return {"status": status.lower(), "activated": False}

        await self._upsert_subscription_from_resource(resource, tenant_id)
        return {"status": "active", "activated": True, "subscription_id": subscription_id}

    async def cancel_subscription(self, tenant_id: uuid.UUID) -> None:
        sub = await self._get_active_sub(tenant_id, provider="paypal")
        if not sub or not sub.paypal_subscription_id:
            raise NotFoundException("No active PayPal subscription found.")
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self._api_base()}/v1/billing/subscriptions/{sub.paypal_subscription_id}/cancel",
                json={"reason": "Customer requested cancellation"},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            if resp.status_code >= 400:
                raise BusinessException("PayPal cancellation failed.")
        sub.cancel_at_period_end = True
        sub.status = "cancelled"
        sub.cancelled_at = datetime.now(timezone.utc)
        await self._db.commit()

    async def reactivate_subscription(self, tenant_id: uuid.UUID) -> None:
        sub = await self._get_active_sub(tenant_id, provider="paypal")
        if not sub or not sub.paypal_subscription_id:
            raise NotFoundException("No PayPal subscription found to reactivate.")
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self._api_base()}/v1/billing/subscriptions/{sub.paypal_subscription_id}/activate",
                json={"reason": "Customer reactivated subscription"},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            if resp.status_code >= 400:
                raise BusinessException("PayPal reactivation failed.")
        sub.status = "active"
        sub.cancel_at_period_end = False
        sub.cancelled_at = None
        await self._db.commit()

    async def create_management_url(self, tenant_id: uuid.UUID) -> str:
        sub = await self._get_active_sub(tenant_id, provider="paypal")
        if not sub or not sub.paypal_subscription_id:
            raise NotFoundException("No active PayPal subscription found.")
        return f"{self._web_base()}/myaccount/autopay/connect/{sub.paypal_subscription_id}"

    async def handle_webhook(self, payload: bytes, headers: dict[str, str]) -> None:
        await self._verify_webhook_signature(payload, headers)
        event = json.loads(payload.decode())
        event_id = event.get("id")
        event_type = event.get("event_type", "")

        if event_id:
            self._db.add(PaypalProcessedEvent(event_id=event_id, event_type=event_type))
            try:
                await self._db.flush()
            except IntegrityError:
                await self._db.rollback()
                return

        resource = event.get("resource", {})
        try:
            if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
                await self._handle_subscription_activated(resource)
            elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
                await self._handle_subscription_cancelled(resource)
            elif event_type == "BILLING.SUBSCRIPTION.SUSPENDED":
                await self._handle_subscription_suspended(resource)
            elif event_type == "BILLING.SUBSCRIPTION.UPDATED":
                await self._handle_subscription_updated(resource)
            elif event_type == "PAYMENT.SALE.COMPLETED":
                await self._handle_payment_completed(resource)
            await self._db.commit()
        except Exception:
            await self._db.rollback()
            raise

    async def _upsert_subscription_from_resource(
        self,
        resource: dict[str, Any],
        tenant_id: Optional[uuid.UUID] = None,
    ) -> None:
        sub_id = resource.get("id")
        custom_id = resource.get("custom_id") or ""
        parts = custom_id.split("|")
        if len(parts) < 4:
            log.warning("PayPal subscription missing custom_id", subscription_id=sub_id)
            return

        resolved_tenant = tenant_id or uuid.UUID(parts[0])
        plan_id = uuid.UUID(parts[2])
        billing_cycle = parts[3]
        status_raw = (resource.get("status") or "ACTIVE").lower()
        status = "active" if status_raw in ("active", "approved") else status_raw

        existing = await self._get_active_sub(resolved_tenant)
        if existing and existing.paypal_subscription_id != sub_id:
            existing.status = "cancelled"

        row = (
            await self._db.execute(
                select(EnhancedTenantSubscription).where(
                    EnhancedTenantSubscription.paypal_subscription_id == sub_id
                )
            )
        ).scalar_one_or_none()

        plan = await self._get_plan(plan_id)
        billing_info = resource.get("billing_info") or {}
        next_billing = billing_info.get("next_billing_time")

        if row:
            row.status = status
            row.plan_id = plan_id
            row.plan_name = plan.name
            row.billing_cycle = billing_cycle
            row.payment_provider = "paypal"
            row.updated_at = datetime.now(timezone.utc)
            if next_billing:
                row.current_period_end = datetime.fromisoformat(next_billing.replace("Z", "+00:00"))
        else:
            period_end = None
            if next_billing:
                period_end = datetime.fromisoformat(next_billing.replace("Z", "+00:00"))
            self._db.add(
                EnhancedTenantSubscription(
                    id=uuid.uuid4(),
                    tenant_id=resolved_tenant,
                    plan_id=plan_id,
                    plan_name=plan.name,
                    billing_cycle=billing_cycle,
                    payment_provider="paypal",
                    paypal_subscription_id=sub_id,
                    status=status,
                    current_period_start=datetime.now(timezone.utc),
                    current_period_end=period_end,
                    cancel_at_period_end=False,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
        await self._db.commit()

    async def _handle_subscription_activated(self, resource: dict) -> None:
        await self._upsert_subscription_from_resource(resource)

    async def _handle_subscription_cancelled(self, resource: dict) -> None:
        sub_id = resource.get("id")
        if not sub_id:
            return
        row = (
            await self._db.execute(
                select(EnhancedTenantSubscription).where(
                    EnhancedTenantSubscription.paypal_subscription_id == sub_id
                )
            )
        ).scalar_one_or_none()
        if row:
            row.status = "cancelled"
            row.cancelled_at = datetime.now(timezone.utc)
            await self._db.commit()

    async def _handle_subscription_suspended(self, resource: dict) -> None:
        sub_id = resource.get("id")
        if not sub_id:
            return
        row = (
            await self._db.execute(
                select(EnhancedTenantSubscription).where(
                    EnhancedTenantSubscription.paypal_subscription_id == sub_id
                )
            )
        ).scalar_one_or_none()
        if row:
            row.status = "past_due"
            await self._db.commit()

    async def _handle_subscription_updated(self, resource: dict) -> None:
        sub_id = resource.get("id")
        if not sub_id:
            return
        row = (
            await self._db.execute(
                select(EnhancedTenantSubscription).where(
                    EnhancedTenantSubscription.paypal_subscription_id == sub_id
                )
            )
        ).scalar_one_or_none()
        if not row:
            return
        status_raw = (resource.get("status") or row.status).lower()
        row.status = "active" if status_raw in ("active", "approved") else status_raw
        billing_info = resource.get("billing_info") or {}
        next_billing = billing_info.get("next_billing_time")
        if next_billing:
            row.current_period_end = datetime.fromisoformat(next_billing.replace("Z", "+00:00"))
        row.updated_at = datetime.now(timezone.utc)
        await self._db.commit()

    async def _handle_payment_completed(self, resource: dict) -> None:
        billing_agreement_id = resource.get("billing_agreement_id")
        if not billing_agreement_id:
            return
        row = (
            await self._db.execute(
                select(EnhancedTenantSubscription).where(
                    EnhancedTenantSubscription.paypal_subscription_id == billing_agreement_id
                )
            )
        ).scalar_one_or_none()
        if not row:
            return
        amount = float(resource.get("amount", {}).get("total", 0))
        currency = resource.get("amount", {}).get("currency", "USD")
        self._db.add(
            BillingHistory(
                id=uuid.uuid4(),
                tenant_id=row.tenant_id,
                subscription_id=row.id,
                amount=amount,
                currency=currency,
                status="paid",
                description="PayPal subscription payment",
                payment_method="paypal",
                created_at=datetime.now(timezone.utc),
            )
        )
        await self._db.commit()

    async def _get_plan(self, plan_id: uuid.UUID) -> SubscriptionPlan:
        plan = (
            await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
        ).scalar_one_or_none()
        if not plan:
            raise NotFoundException("Subscription plan not found.")
        return plan

    async def _get_active_sub(
        self, tenant_id: uuid.UUID, provider: Optional[str] = None
    ) -> Optional[EnhancedTenantSubscription]:
        q = select(EnhancedTenantSubscription).where(
            EnhancedTenantSubscription.tenant_id == tenant_id,
            EnhancedTenantSubscription.status.in_(["active", "trialing", "past_due"]),
        )
        if provider:
            q = q.where(EnhancedTenantSubscription.payment_provider == provider)
        return (
            await self._db.execute(q.order_by(EnhancedTenantSubscription.created_at.desc()).limit(1))
        ).scalar_one_or_none()

    async def get_subscription_status(self, tenant_id: uuid.UUID) -> Optional[dict]:
        sub = await self._get_active_sub(tenant_id, provider="paypal")
        if not sub:
            return None
        plan = await self._get_plan(sub.plan_id) if sub.plan_id else None
        return {
            "id": str(sub.id),
            "status": sub.status,
            "planId": str(sub.plan_id) if sub.plan_id else None,
            "planName": plan.display_name if plan else sub.plan_name,
            "plan_name": plan.display_name if plan else sub.plan_name,
            "currentPeriodEnd": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "cancelAtPeriodEnd": sub.cancel_at_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "paymentProvider": "paypal",
            "payment_provider": "paypal",
        }

    async def get_billing_history(
        self, tenant_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        q = select(BillingHistory).where(
            BillingHistory.tenant_id == tenant_id,
            BillingHistory.payment_method == "paypal",
        )
        total = (await self._db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        items = (
            await self._db.execute(
                q.order_by(BillingHistory.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [
            {
                "id": str(i.id),
                "amount": float(i.amount),
                "currency": i.currency,
                "status": i.status,
                "description": i.description,
                "paymentMethod": i.payment_method,
                "createdAt": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ], total
