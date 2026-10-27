
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.infrastructure.database import Base


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(
            ProjectStatus,
            name="project_status",
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ProjectStatus.DRAFT,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now(), nullable=False)

    # relationships — lazy="selectin" avoids MissingGreenlet in async SQLAlchemy
    attachments: Mapped[list["ProjectFile"]] = relationship(
        "ProjectFile", back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )


class ProjectFile(Base):
    """
    Association table between Project and FileUpload. FileUpload model exists in app.domain.models.misc.
    This allows attaching multiple uploaded files (images/docs) to a project.
    """
    __tablename__ = "project_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("file_uploads.id", ondelete="CASCADE"), nullable=False, index=True)

    # optional: store a display name or role (image / document)
    label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="attachments", lazy="selectin")
    # Note: FileUpload model lives in app.domain.models.misc and is imported via string relationship when needed by higher-level queries
