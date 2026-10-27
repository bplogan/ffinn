"""
Subscription, editions, and billing domain models.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Numeric, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.database import Base


class Edition(Base):
    __tablename__ = "editions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    price_monthly: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    price_annually: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    trial_day_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_trial_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    features: Mapped[list["EditionFeature"]] = relationship("EditionFeature", back_populates="edition", lazy="selectin", order_by="EditionFeature.sort_order")


class EditionFeature(Base):
    """A feature/capability associated with an Edition tier."""
    __tablename__ = "edition_features"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("editions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_name: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    feature_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_included: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    edition: Mapped["Edition"] = relationship("Edition", back_populates="features")


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_monthly: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    price_annually: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    stripe_price_id_monthly: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    stripe_price_id_annually: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    paypal_plan_id_monthly: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    paypal_plan_id_annually: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    stripe_product_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    max_users: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_storage_gb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    features: Mapped[list["PlanFeature"]] = relationship("PlanFeature", back_populates="plan", lazy="selectin")


class PlanFeature(Base):
    __tablename__ = "plan_features"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id", ondelete="CASCADE"), nullable=False
    )
    feature_name: Mapped[str] = mapped_column(String(200), nullable=False)
    feature_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_included: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="features")


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    edition_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    start_date_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date_utc: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    last_payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EnhancedTenantSubscription(Base):
    __tablename__ = "enhanced_tenant_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=True
    )
    plan_name: Mapped[str] = mapped_column(String(200), default="free")
    billing_cycle: Mapped[str] = mapped_column(String(50), default="monthly")  # monthly, annual
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, cancelled, expired, trial
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, unique=True)
    paypal_subscription_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    payment_provider: Mapped[str] = mapped_column(String(32), default="stripe")  # stripe | paypal
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    plan: Mapped[Optional["SubscriptionPlan"]] = relationship("SubscriptionPlan", lazy="selectin")


class BillingHistory(Base):
    __tablename__ = "billing_histories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enhanced_tenant_subscriptions.id"), nullable=True
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # paid, failed, refunded, pending
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    stripe_invoice_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    invoice_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    invoice_pdf_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    billing_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period_start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    external_payment_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvoiceInfo(Base):
    __tablename__ = "invoice_infos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tax_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class StripeProcessedEvent(Base):
    """Idempotency ledger for Stripe webhook events.

    Stripe retries webhook deliveries on non-2xx responses. The event_id is
    inserted (PK) at the start of handling; a duplicate insert short-circuits
    the handler so we never double-process a single Stripe event.
    """
    __tablename__ = "stripe_processed_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaypalProcessedEvent(Base):
    """Idempotency ledger for PayPal webhook events."""
    __tablename__ = "paypal_processed_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
