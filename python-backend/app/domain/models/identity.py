"""
Identity and user domain models.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.database import Base


class IdentityUser(Base):
    __tablename__ = "identity_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    user_name: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_user_name: Mapped[str] = mapped_column(String(256), nullable=False)
    email: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(256), nullable=False)
    email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    phone_number_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    surname: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    profile_picture_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    lockout_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    lockout_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    access_failed_count: Mapped[int] = mapped_column(Integer, default=0)
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    concurrency_stamp: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    security_stamp: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    timezone_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships — all use "selectin" to avoid MissingGreenlet in async context
    roles: Mapped[list["IdentityUserRole"]] = relationship(
        "IdentityUserRole", back_populates="user", lazy="selectin"
    )
    claims: Mapped[list["IdentityUserClaim"]] = relationship(
        "IdentityUserClaim", back_populates="user", lazy="selectin"
    )
    tokens: Mapped[list["IdentityUserToken"]] = relationship(
        "IdentityUserToken", back_populates="user", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_user_name", name="uq_users_tenant_username"),
        UniqueConstraint("tenant_id", "normalized_email", name="uq_users_tenant_email"),
        Index("ix_users_tenant_id", "tenant_id"),
    )

    @property
    def full_name(self) -> str:
        parts = [p for p in [self.name, self.surname] if p]
        return " ".join(parts) if parts else self.user_name


class IdentityRole(Base):
    __tablename__ = "identity_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    concurrency_stamp: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["IdentityUserRole"]] = relationship(
        "IdentityUserRole", back_populates="role", lazy="select"
    )
    claims: Mapped[list["IdentityRoleClaim"]] = relationship(
        "IdentityRoleClaim", back_populates="role", lazy="selectin"
    )
    permission_grants: Mapped[list["PermissionGrant"]] = relationship(
        "PermissionGrant", back_populates="role", lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_name", name="uq_roles_tenant_name"),
    )


class IdentityUserRole(Base):
    __tablename__ = "identity_user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_roles.id", ondelete="CASCADE"), primary_key=True
    )

    user: Mapped["IdentityUser"] = relationship("IdentityUser", back_populates="roles")
    role: Mapped["IdentityRole"] = relationship("IdentityRole", back_populates="users")


class IdentityUserClaim(Base):
    __tablename__ = "identity_user_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), nullable=False
    )
    claim_type: Mapped[str] = mapped_column(String(512), nullable=False)
    claim_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["IdentityUser"] = relationship("IdentityUser", back_populates="claims")


class IdentityUserToken(Base):
    __tablename__ = "identity_user_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), primary_key=True
    )
    login_provider: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["IdentityUser"] = relationship("IdentityUser", back_populates="tokens")


class IdentityRoleClaim(Base):
    __tablename__ = "identity_role_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_roles.id", ondelete="CASCADE"), nullable=False
    )
    claim_type: Mapped[str] = mapped_column(String(512), nullable=False)
    claim_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    role: Mapped["IdentityRole"] = relationship("IdentityRole", back_populates="claims")


class PermissionGrant(Base):
    __tablename__ = "permission_grants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    role_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_roles.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), nullable=True
    )
    permission_name: Mapped[str] = mapped_column(String(512), nullable=False)
    is_granted: Mapped[bool] = mapped_column(Boolean, default=True)

    role: Mapped[Optional["IdentityRole"]] = relationship("IdentityRole", back_populates="permission_grants")


class EmailConfirmationToken(Base):
    __tablename__ = "email_confirmation_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SsoConfiguration(Base):
    __tablename__ = "sso_configurations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # SAML, OIDC
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    client_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    client_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # encrypted
    metadata_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    metadata_xml: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_provision_users: Mapped[bool] = mapped_column(Boolean, default=True)
    default_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class SsoAuthState(Base):
    """Short-lived PKCE/state for in-flight OIDC logins."""

    __tablename__ = "sso_auth_states"

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sso_configurations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_verifier: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    return_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TwoFactorAuth(Base):
    __tablename__ = "two_factor_auths"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("identity_users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    secret_key: Mapped[str] = mapped_column(String(512), nullable=False)  # encrypted TOTP secret
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array, encrypted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    enabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class UserDelegation(Base):
    __tablename__ = "user_delegations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
