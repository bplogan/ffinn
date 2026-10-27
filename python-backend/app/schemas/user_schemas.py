"""User management schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    user_name: str
    email: str
    # IdentityUser stores name/surname; expose as first_name/last_name in the API
    first_name: str | None = Field(None, validation_alias="name")
    last_name: str | None = Field(None, validation_alias="surname")
    full_name: str | None = None
    tenant_id: str | None = None
    is_active: bool = True
    is_email_confirmed: bool = True
    lockout_enabled: bool = False
    profile_picture_url: str | None = None
    roles: list[str] = []
    created_at: datetime | None = None

    @field_validator("id", "tenant_id", mode="before")
    @classmethod
    def _coerce_uuid_to_str(cls, v: Any) -> str | None:
        """Allow UUID or str for id/tenant_id — coerce to str."""
        if v is None:
            return None
        return str(v)

    @field_validator("roles", mode="before")
    @classmethod
    def _coerce_roles(cls, v: Any) -> list[str]:
        """Accept either a list of strings or a list of IdentityUserRole ORM objects."""
        if not v:
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append(item)
            elif hasattr(item, "role") and item.role is not None:
                result.append(item.role.name)
            elif hasattr(item, "name"):
                result.append(item.name)
        return result


class CreateUserRequest(BaseModel):
    user_name: str
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    role_names: list[str] = []


class UpdateUserRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    profile_picture_url: str | None = None


class UpdateUserAdminRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool | None = None
    role_names: list[str] | None = None


class PagedResult(BaseModel):
    items: list
    total_count: int
    page: int
    page_size: int
    total_pages: int
