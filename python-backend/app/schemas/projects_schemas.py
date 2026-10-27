
from __future__ import annotations

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from pydantic import ConfigDict


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class FileAttachmentSchema(BaseModel):
    id: UUID
    file_name: Optional[str] = None
    url: Optional[str] = None
    label: Optional[str] = None

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ProjectBase(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ProjectCreate(ProjectBase):
    title: str
    description: Optional[str] = None
    status: Optional[str] = "active"
    attachment_ids: Optional[List[UUID]] = None

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ProjectUpdate(ProjectBase):
    # Partial update fields — if None they will not be updated
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    attachment_ids: Optional[List[UUID]] = None

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ProjectRead(BaseModel):
    id: UUID
    tenant_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    attachments: List[FileAttachmentSchema] = []

    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
