"""
Tenant notification configuration — SMS (Twilio) and push (Firebase FCM or Twilio Notify).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.database import Base


class NotificationConfiguration(Base):
    """Per-tenant SMS and push provider settings. Secrets stored encrypted."""

    __tablename__ = "notification_configurations"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_notification_configurations_tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # ── SMS (Twilio) ─────────────────────────────────────────────────────────
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    twilio_account_sid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    twilio_auth_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    twilio_from_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # ── Push ───────────────────────────────────────────────────────────────────
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # firebase | twilio
    push_provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Firebase Cloud Messaging
    firebase_project_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    firebase_credentials_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Twilio Notify (uses same account SID + auth token as SMS)
    twilio_notify_service_sid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
