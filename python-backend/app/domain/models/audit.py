"""
Audit log domain model.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    service: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    method_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    parameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    return_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exceptions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    browser_info: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    client_ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    http_method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    execution_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ms
    entity_type: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    changes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
