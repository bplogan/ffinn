"""Auth request/response schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from pydantic.alias_generators import to_camel


# Password policy enforcement happens in the service layer (via HostSettings),
# NOT in the schema layer, so that DB-stored rules are respected.
# We keep only a trivial non-empty guard here.
def _require_password(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Password must not be empty.")
    return v


class LoginRequest(BaseModel):
    username_or_email: str
    password: str
    tenant_name: Optional[str] = None


class RegisterRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    user_name: Optional[str] = None
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    tenant_name: Optional[str] = None
    edition_id: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        return _require_password(v)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int


class TenantChoice(BaseModel):
    name: str


class LoginResponse(BaseModel):
    """One of three shapes: tokens, a two-factor challenge, or organizations to choose from."""
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    requires_two_factor: Optional[bool] = None
    user_id: Optional[str] = None
    tenants: Optional[list[TenantChoice]] = None


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None  # omit body when using HttpOnly cookie


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        return _require_password(v)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        return _require_password(v)


class ConfirmEmailRequest(BaseModel):
    token: str


class AuthUserInfo(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )

    id: str
    email: str
    user_name: str
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    roles: list[str] = []
    permissions: list[str] = []
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    is_email_confirmed: bool = True
    two_factor_enabled: bool = False
    is_impersonating: bool = False
    impersonator_user_id: Optional[str] = None
    impersonator_user_name: Optional[str] = None
