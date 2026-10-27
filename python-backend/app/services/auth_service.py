"""Authentication service — login, register, refresh tokens, email confirmation."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import BusinessException, UnauthorizedException, ConflictException, NotFoundException
from app.core.permissions import Roles
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, hash_token,
    generate_secure_token, generate_email_confirmation_token,
    validate_password_strength,
)
from app.domain.models.identity import (
    IdentityUser, IdentityRole, IdentityUserRole,
    IdentityUserToken, EmailConfirmationToken, PasswordResetToken, PermissionGrant,
    TwoFactorAuth,
)
from app.domain.models.tenant import Tenant
from app.infrastructure.email import EmailService

log = structlog.get_logger(__name__)

# Used for constant-time login when the user does not exist (mitigates timing enumeration).
_DUMMY_PASSWORD_HASH = hash_password("__ffinn_timing_sentinel__")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        email_service: Optional[EmailService] = None,
        host_settings=None,  # Optional[HostSettings] — avoid circular import at class level
    ):
        self._db = db
        self._email = email_service  # None is OK; _send_confirmation_email guards against it
        self._hs = host_settings  # HostSettings instance (may be None)

    # ── Login ─────────────────────────────────────────────────────────────────
    async def login(
        self,
        username_or_email: str,
        password: str,
        tenant_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """Authenticate user and return JWT + refresh token.

        Without a tenant, a host account is tried first. Failing that, the same sign-in is
        looked up across active organizations: one match signs in, and several whose password
        matches return ``{"tenants": [{"name": ...}]}`` so the caller can ask which to use.
        """
        if not username_or_email or not password:
            raise BusinessException("Username/email and password are required")

        normalized = username_or_email.upper()
        user = (await self._db.execute(
            self._login_user_query(normalized).where(IdentityUser.tenant_id == tenant_id)
        )).scalar_one_or_none()

        if not user and tenant_id is None:
            candidates = (await self._db.execute(
                self._login_user_query(normalized)
                .add_columns(Tenant.name)
                .join(Tenant, Tenant.id == IdentityUser.tenant_id)
                .where(Tenant.is_active == True)  # noqa: E712
            )).all()
            if len(candidates) == 1:
                user = candidates[0][0]
            elif candidates:
                # Only check accounts that could sign in, so a locked or inactive one never
                # reveals whether its password matched.
                usable = [
                    (u, name) for u, name in candidates
                    if u.is_active and not (u.lockout_enabled and u.lockout_end and _ensure_utc(u.lockout_end) > _utc_now())
                ]
                matches = [(u, name) for u, name in usable if u.password_hash and verify_password(password, u.password_hash)]
                if not matches:
                    for u, _ in usable:
                        self._record_failed_login(u)
                    await self._db.commit()
                    raise UnauthorizedException("Invalid username/email or password")
                if len(matches) > 1:
                    return {"tenants": [{"name": name} for _, name in sorted(matches, key=lambda m: m[1].lower())]}
                user = matches[0][0]

        if not user:
            verify_password(password, _DUMMY_PASSWORD_HASH)
            raise UnauthorizedException("Invalid username/email or password")

        if not user.is_active:
            raise UnauthorizedException("Your account is inactive. Contact an administrator.")

        hs = self._hs
        require_email_conf = hs.require_email_confirmation if hs else settings.require_email_confirmation

        if require_email_conf and not user.email_confirmed:
            raise BusinessException(
                "Email address has not been confirmed.",
                code="EMAIL_NOT_CONFIRMED",
            )

        if user.lockout_enabled and user.lockout_end and _ensure_utc(user.lockout_end) > _utc_now():
            raise UnauthorizedException(f"Account locked until {user.lockout_end.strftime('%Y-%m-%d %H:%M')} UTC")

        if not user.password_hash or not verify_password(password, user.password_hash):
            # Commit immediately — intentional early commit so that lockout state is
            # persisted even if the request errors later.
            self._record_failed_login(user)
            await self._db.commit()
            raise UnauthorizedException("Invalid username/email or password")

        # Reset failed count on success
        user.access_failed_count = 0
        user.lockout_end = None
        user.last_login_at = datetime.now(timezone.utc)
        await self._db.commit()

        tfa = (await self._db.execute(
            select(TwoFactorAuth).where(
                TwoFactorAuth.user_id == user.id,
                TwoFactorAuth.is_enabled == True,  # noqa: E712
            )
        )).scalar_one_or_none()
        if tfa:
            return {
                "requires_two_factor": True,
                "user_id": str(user.id),
            }

        return await self._build_auth_response(user)

    @staticmethod
    def _login_user_query(normalized: str):
        """Users whose user name or email matches, with what login needs loaded."""
        return (
            select(IdentityUser)
            .options(
                selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role),
                selectinload(IdentityUser.tokens),
            )
            .where(
                (IdentityUser.normalized_user_name == normalized)
                | (IdentityUser.normalized_email == normalized),
            )
        )

    def _record_failed_login(self, user: IdentityUser) -> None:
        """Count a failed password and lock the account once the configured limit is hit."""
        hs = self._hs
        lockout_enabled = hs.lockout_enabled if hs else True
        lockout_max = hs.lockout_max_attempts if hs else 5
        lockout_secs = hs.lockout_duration_seconds if hs else 300
        user.access_failed_count += 1
        if lockout_enabled and user.access_failed_count >= lockout_max:
            user.lockout_end = datetime.now(timezone.utc) + timedelta(seconds=lockout_secs)
            user.lockout_enabled = True

    # ── Register ──────────────────────────────────────────────────────────────
    async def register(
        self,
        email: str,
        password: str,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        tenant_name: Optional[str] = None,
        edition_id=None,
        base_url: str = "",
        **kwargs,
    ) -> dict:
        hs = self._hs
        allow_reg = hs.allow_registration if hs else settings.allow_registration
        if not allow_reg and not kwargs.get("bypass_registration_check", False):
            raise BusinessException("Registration is currently disabled")

        # Domain restriction check
        if hs and hs.restricted_email_domains_enabled and hs.allowed_email_domains:
            email_domain = email.lower().split("@")[-1]
            if email_domain not in hs.allowed_email_domains:
                allowed = ", ".join(hs.allowed_email_domains)
                raise BusinessException(f"Registration is restricted to: {allowed}")

        normalized_email = email.upper()

        # Resolve or create tenant
        tenant_id: Optional[uuid.UUID] = None
        created_new_tenant = False
        if tenant_name:
            tenant_result = await self._db.execute(
                select(Tenant).where(Tenant.normalized_name == tenant_name.lower())
            )
            tenant = tenant_result.scalar_one_or_none()
            if tenant is None:
                tenant = Tenant(
                    id=uuid.uuid4(),
                    name=tenant_name,
                    normalized_name=tenant_name.lower(),
                    is_active=True,
                    is_available=True,
                    admin_email_address=email,
                    edition_id=edition_id,
                )
                self._db.add(tenant)
                await self._db.flush()
                # Seed Admin and User system roles for the new tenant
                from app.services.role_service import seed_tenant_system_roles
                await seed_tenant_system_roles(self._db, tenant.id)
                created_new_tenant = True
            tenant_id = tenant.id

        # Check uniqueness. Only a username the person chose can clash; one derived
        # from the email gets a number added instead (brad, brad2, ...).
        exists = await self._db.execute(
            select(IdentityUser.id).where(
                IdentityUser.tenant_id == tenant_id,
                IdentityUser.normalized_email == normalized_email,
            )
        )
        if exists.first():
            raise ConflictException("An account with this email already exists")
        if username:
            taken = await self._db.execute(
                select(IdentityUser.id).where(
                    IdentityUser.tenant_id == tenant_id,
                    IdentityUser.normalized_user_name == username.upper(),
                )
            )
            if taken.first():
                raise ConflictException("That username is already taken")
        else:
            username = await self._free_username(email.split("@")[0], tenant_id)
        normalized_username = username.upper()

        # Validate password policy before creating the user
        hs = self._hs
        pw_errors = validate_password_strength(
            password,
            min_length=hs.password_min_length if hs else None,
            require_digit=hs.password_require_digit if hs else None,
            require_lowercase=hs.password_require_lowercase if hs else None,
            require_uppercase=hs.password_require_uppercase if hs else None,
            require_special=hs.password_require_special if hs else None,
        )
        if pw_errors:
            raise BusinessException("; ".join(pw_errors))

        require_email_conf = hs.require_email_confirmation if hs else settings.require_email_confirmation
        new_users_active = hs.new_users_active_by_default if hs else True

        user = IdentityUser(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_name=username,
            normalized_user_name=normalized_username,
            email=email,
            normalized_email=normalized_email,
            password_hash=hash_password(password),
            name=first_name,
            surname=last_name,
            is_active=new_users_active,
            email_confirmed=not require_email_conf,
            security_stamp=generate_secure_token(16),
            concurrency_stamp=generate_secure_token(16),
        )
        self._db.add(user)

        # Tenant creator (signup/payment flow) becomes the tenant admin
        if created_new_tenant:
            await self._assign_role(user, tenant_id, Roles.ADMIN)
        else:
            await self._assign_default_role(user, tenant_id)

        await self._db.flush()  # Get user.id

        if require_email_conf:
            await self._send_confirmation_email(user, base_url)
            try:
                await self._db.commit()
            except IntegrityError:
                await self._db.rollback()
                raise ConflictException("Email or username is already in use")
            return {
                "success": True,
                "message": "Registration successful. Please check your email to confirm your account.",
                "email_confirmation_required": True,
                "user_id": str(user.id),
            }

        try:
            await self._db.commit()
        except IntegrityError:
            await self._db.rollback()
            raise ConflictException("Email or username is already in use")
        return {
            "success": True,
            "message": "Registration successful.",
            "email_confirmation_required": False,
            "user_id": str(user.id),
        }

    async def _free_username(self, base: str, tenant_id: Optional[uuid.UUID]) -> str:
        """Return `base`, or `base2`, `base3`, ... whichever is unused in the tenant."""
        rows = await self._db.execute(
            select(IdentityUser.normalized_user_name).where(
                IdentityUser.tenant_id == tenant_id,
                IdentityUser.normalized_user_name.startswith(base.upper(), autoescape=True),
            )
        )
        used = set(rows.scalars())
        candidate, n = base, 1
        while candidate.upper() in used:
            n += 1
            candidate = f"{base}{n}"
        return candidate

    # ── Refresh token ─────────────────────────────────────────────────────────
    async def refresh_token(self, refresh_token: str) -> dict:
        """Validate, rotate, and return a new refresh token.

        Reuse-detection: when a refresh token is rotated the original row is
        retained for a short grace window with its `name` suffixed by
        `:rotated`. If a client presents a token whose stored row is already
        marked rotated we treat that as a leaked-token replay attack and
        revoke every refresh token for the user (token-family invalidation).
        """
        token_hash = hash_token(refresh_token)
        result = await self._db.execute(
            select(IdentityUserToken)
            .where(
                IdentityUserToken.login_provider == "ffinn",
                IdentityUserToken.name.like("refresh_token:%"),
                IdentityUserToken.value == token_hash,
            )
            .with_for_update()
        )
        rows = list(result.scalars().all())
        if not rows:
            raise UnauthorizedException("Invalid refresh token")

        active_rows = [r for r in rows if not r.name.endswith(":rotated")]
        if not active_rows:
            await self.revoke_refresh_token_for_user(rows[0].user_id)
            raise UnauthorizedException("Refresh token reuse detected; session revoked.")

        token_record = active_rows[0]

        if token_record.expires_at and _ensure_utc(token_record.expires_at) < _utc_now():
            await self._db.delete(token_record)
            await self._db.commit()
            raise UnauthorizedException("Refresh token expired")

        user_result = await self._db.execute(
            select(IdentityUser)
            .options(
                selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role),
                selectinload(IdentityUser.tokens),
            )
            .where(IdentityUser.id == token_record.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active:
            raise UnauthorizedException("User not found or inactive")

        # Rotate refresh token — store hash at rest, return plaintext to client.
        # Mark the previous row as rotated and keep it for a short grace window
        # so a replay can be detected; the new row gets a fresh name & value.
        new_token, new_expires = create_refresh_token({"sub": str(user.id)})
        from datetime import timedelta as _td
        token_record.name = f"{token_record.name}:rotated"
        token_record.expires_at = datetime.now(timezone.utc) + _td(minutes=5)
        new_record = IdentityUserToken(
            user_id=user.id,
            login_provider="ffinn",
            name=f"refresh_token:{uuid.uuid4()}",
            value=hash_token(new_token),
            expires_at=new_expires,
        )
        self._db.add(new_record)
        await self._db.commit()

        response = await self._build_auth_response(user)
        response["refresh_token"] = new_token
        return response

    async def issue_refresh_token(self, user_id: uuid.UUID, tenant_id: Optional[uuid.UUID]) -> str:
        token_value, expires = create_refresh_token({"sub": str(user_id)})
        token = IdentityUserToken(
            user_id=user_id,
            login_provider="ffinn",
            name=f"refresh_token:{uuid.uuid4()}",
            value=hash_token(token_value),   # store hash; return plaintext to caller
            expires_at=expires,
        )
        self._db.add(token)
        await self._db.commit()
        return token_value

    async def revoke_refresh_token(self, user_id: uuid.UUID, refresh_token: str) -> None:
        result = await self._db.execute(
            select(IdentityUserToken).where(
                IdentityUserToken.user_id == user_id,
                IdentityUserToken.value == hash_token(refresh_token),
            )
        )
        tokens = result.scalars().all()
        for token in tokens:
            await self._db.delete(token)
        if tokens:
            await self._db.commit()

    async def revoke_refresh_token_for_user(self, user_id: uuid.UUID) -> None:
        """Revoke all refresh tokens for a user (used on logout)."""
        result = await self._db.execute(
            select(IdentityUserToken).where(
                IdentityUserToken.user_id == user_id,
                IdentityUserToken.login_provider == "ffinn",
                IdentityUserToken.name.like("refresh_token:%"),
            )
        )
        tokens = result.scalars().all()
        for token in tokens:
            await self._db.delete(token)
        if tokens:
            await self._db.commit()

    # ── Email confirmation ────────────────────────────────────────────────────
    async def confirm_email(self, token: str) -> bool:
        result = await self._db.execute(
            select(EmailConfirmationToken).where(EmailConfirmationToken.token == hash_token(token))
        )
        confirmation = result.scalar_one_or_none()
        if not confirmation:
            raise BusinessException("Invalid confirmation token")
        if _ensure_utc(confirmation.expires_at) < _utc_now():
            raise BusinessException("Confirmation token expired. Please request a new one.")
        if confirmation.used_at:
            raise BusinessException("Confirmation token already used")

        user_result = await self._db.execute(
            select(IdentityUser).where(IdentityUser.id == confirmation.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise BusinessException("User not found")

        user.email_confirmed = True
        confirmation.used_at = datetime.now(timezone.utc)
        await self._db.commit()
        return True

    async def resend_confirmation_email(self, email: str, base_url: str) -> bool:
        result = await self._db.execute(
            select(IdentityUser).where(IdentityUser.normalized_email == email.upper())
        )
        user = result.scalar_one_or_none()
        if not user:
            return True  # Don't reveal if email exists
        if user.email_confirmed:
            return True
        await self._send_confirmation_email(user, base_url)
        await self._db.commit()
        return True

    # ── Password reset ────────────────────────────────────────────────────────
    async def forgot_password(self, email: str, base_url: str) -> bool:
        result = await self._db.execute(
            select(IdentityUser).where(IdentityUser.normalized_email == email.upper())
        )
        user = result.scalar_one_or_none()
        if not user:
            return True  # Don't reveal existence

        token_value = generate_secure_token(48)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=hash_token(token_value),  # store hash; send plaintext in email link
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self._db.add(reset_token)
        await self._db.commit()

        email_svc = self._email or (self._hs.build_email_service() if self._hs else None)
        if email_svc:
            await email_svc.send_password_reset(
                user.email, user.full_name, token_value, base_url=base_url or None
            )
        return True

    async def reset_password(self, token: str, new_password: str) -> bool:
        result = await self._db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token == hash_token(token))
        )
        reset_token = result.scalar_one_or_none()
        if not reset_token:
            raise BusinessException("Invalid reset token")
        if _ensure_utc(reset_token.expires_at) < _utc_now():
            raise BusinessException("Reset token expired. Please request a new one.")
        if reset_token.used_at:
            raise BusinessException("Reset token already used")

        user_result = await self._db.execute(
            select(IdentityUser).where(IdentityUser.id == reset_token.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise BusinessException("User not found")

        hs = self._hs
        pw_errors = validate_password_strength(
            new_password,
            min_length=hs.password_min_length if hs else None,
            require_digit=hs.password_require_digit if hs else None,
            require_lowercase=hs.password_require_lowercase if hs else None,
            require_uppercase=hs.password_require_uppercase if hs else None,
            require_special=hs.password_require_special if hs else None,
        )
        if pw_errors:
            raise BusinessException("; ".join(pw_errors))

        user.password_hash = hash_password(new_password)
        user.security_stamp = generate_secure_token(16)
        reset_token.used_at = datetime.now(timezone.utc)
        await self.revoke_refresh_token_for_user(user.id)
        await self._db.commit()
        return True

    async def change_password(
        self,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
    ) -> bool:
        result = await self._db.execute(
            select(IdentityUser).where(IdentityUser.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise BusinessException("User not found")
        if not user.password_hash or not verify_password(current_password, user.password_hash):
            raise BusinessException("Current password is incorrect")

        hs = self._hs
        pw_errors = validate_password_strength(
            new_password,
            min_length=hs.password_min_length if hs else None,
            require_digit=hs.password_require_digit if hs else None,
            require_lowercase=hs.password_require_lowercase if hs else None,
            require_uppercase=hs.password_require_uppercase if hs else None,
            require_special=hs.password_require_special if hs else None,
        )
        if pw_errors:
            raise BusinessException("; ".join(pw_errors))

        user.password_hash = hash_password(new_password)
        user.security_stamp = generate_secure_token(16)
        await self.revoke_refresh_token_for_user(user.id)
        await self._db.commit()
        return True

    # ── Impersonation ─────────────────────────────────────────────────────────
    async def impersonate(
        self,
        actor_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        expected_tenant_id: uuid.UUID | None = None,
        *,
        actor_is_impersonating: bool = False,
        actor_impersonator_id: uuid.UUID | None = None,
    ) -> dict:
        """Issue a short-lived JWT scoped to target_user, recording impersonator."""
        from app.core.exceptions import ForbiddenException

        if actor_is_impersonating:
            raise ForbiddenException("Cannot impersonate while already impersonating another user.")

        effective_actor_id = actor_impersonator_id or actor_user_id

        if effective_actor_id == target_user_id:
            raise BusinessException("Cannot impersonate yourself")

        actor_result = await self._db.execute(
            select(IdentityUser)
            .options(selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role))
            .where(IdentityUser.id == effective_actor_id)
        )
        actor = actor_result.scalar_one_or_none()
        if not actor:
            raise UnauthorizedException()
        actor_roles = [ur.role.name for ur in actor.roles if ur.role]
        from app.core.permissions import Roles as RolesConfig
        actor_perms: set[str] = set()
        for rn in actor_roles:
            actor_perms.update(RolesConfig.DEFAULT_ROLE_PERMISSIONS.get(rn, []))
        perms_result = await self._db.execute(
            select(PermissionGrant).where(
                PermissionGrant.user_id == effective_actor_id,
                PermissionGrant.is_granted == True,  # noqa: E712
            )
        )
        actor_perms.update(pg.permission_name for pg in perms_result.scalars())
        if "Admin" not in actor_roles and "User.Impersonate" not in actor_perms:
            raise ForbiddenException("User.Impersonate permission required to impersonate users.")

        target_result = await self._db.execute(
            select(IdentityUser)
            .options(selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role))
            .where(IdentityUser.id == target_user_id)
        )
        target = target_result.scalar_one_or_none()
        if not target:
            raise NotFoundException("User", str(target_user_id))
        if not target.is_active:
            raise BusinessException("Target user is inactive")

        if actor.tenant_id is not None:
            if target.tenant_id != actor.tenant_id:
                raise ForbiddenException("Cannot impersonate users outside your tenant")
        elif expected_tenant_id is not None:
            if target.tenant_id != expected_tenant_id:
                raise BusinessException("User does not belong to the selected tenant")

        from app.core.permissions import Roles as RolesConfig
        role_names = [ur.role.name for ur in target.roles if ur.role]
        perms_result = await self._db.execute(
            select(PermissionGrant).where(
                PermissionGrant.user_id == target.id,
                PermissionGrant.is_granted == True,  # noqa: E712
            )
        )
        all_permissions = list({pg.permission_name for pg in perms_result.scalars()})
        for rn in role_names:
            all_permissions.extend(RolesConfig.DEFAULT_ROLE_PERMISSIONS.get(rn, []))
        all_permissions = list(set(all_permissions))

        token_data = {
            "sub": str(target.id),
            "email": target.email,
            "username": target.user_name,
            "tenant_id": str(target.tenant_id) if target.tenant_id else None,
            "roles": role_names,
            "permissions": all_permissions,
            "impersonating": True,
            "impersonator_id": str(effective_actor_id),
            "impersonated_by": str(effective_actor_id),
            "sec": target.security_stamp or "",
        }
        from datetime import timedelta
        access_token = create_access_token(token_data, expires_delta=timedelta(hours=1))
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "is_impersonation": True,
            "user_id": str(target.id),
            "username": target.user_name,
            "impersonated_by": str(effective_actor_id),
        }

    async def validate_invitation_token(self, token: str) -> dict:
        """Validate a password-reset / invitation token and return user info."""
        result = await self._db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token == hash_token(token))
        )
        reset_token = result.scalar_one_or_none()
        if not reset_token:
            raise BusinessException("Invalid or expired token")
        if _ensure_utc(reset_token.expires_at) < _utc_now():
            raise BusinessException("Token expired. Please request a new invitation.")
        if reset_token.used_at:
            raise BusinessException("Token already used")

        user_result = await self._db.execute(
            select(IdentityUser).where(IdentityUser.id == reset_token.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise BusinessException("User not found")

        return {
            "email": user.email,
            "user_name": user.user_name,
            "name": user.name,
            "surname": user.surname,
            "is_valid": True,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────
    async def login_or_provision_sso_user(
        self,
        *,
        email: str,
        tenant_id: Optional[uuid.UUID],
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        auto_provision: bool = True,
        default_role: Optional[str] = None,
    ) -> IdentityUser:
        """Find or create an external SSO user and return the loaded user."""
        from sqlalchemy.orm import selectinload

        norm_email = email.strip().lower()
        q = (
            select(IdentityUser)
            .options(selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role))
            .where(IdentityUser.normalized_email == norm_email.upper())
        )
        if tenant_id is not None:
            q = q.where(IdentityUser.tenant_id == tenant_id)
        user = (await self._db.execute(q)).scalar_one_or_none()
        if user:
            if not user.is_active:
                raise BusinessException("User account is disabled.")
            user.is_external = True
            user.last_login_at = datetime.now(timezone.utc)
            await self._db.commit()
            await self._db.refresh(user)
            return user

        if not auto_provision:
            raise BusinessException("No account exists for this email. Contact your administrator.")

        username_base = norm_email.split("@")[0]
        username = username_base
        suffix = 1
        while (
            await self._db.execute(
                select(IdentityUser).where(
                    IdentityUser.normalized_user_name == username.upper(),
                    IdentityUser.tenant_id == tenant_id if tenant_id else IdentityUser.tenant_id.is_(None),
                )
            )
        ).scalar_one_or_none():
            username = f"{username_base}{suffix}"
            suffix += 1

        user = IdentityUser(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_name=username,
            normalized_user_name=username.upper(),
            email=norm_email,
            normalized_email=norm_email.upper(),
            email_confirmed=True,
            password_hash=None,
            name=first_name,
            surname=last_name,
            is_active=True,
            is_external=True,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(user)
        await self._db.flush()

        role_name = default_role or Roles.USER
        role = (
            await self._db.execute(
                select(IdentityRole).where(
                    IdentityRole.tenant_id == tenant_id,
                    IdentityRole.normalized_name == role_name.upper(),
                )
            )
        ).scalar_one_or_none()
        if role is None and tenant_id is not None:
            role = (
                await self._db.execute(
                    select(IdentityRole).where(
                        IdentityRole.tenant_id.is_(None),
                        IdentityRole.normalized_name == role_name.upper(),
                    )
                )
            ).scalar_one_or_none()
        if role:
            self._db.add(IdentityUserRole(user_id=user.id, role_id=role.id))
        else:
            await self._assign_default_role(user, tenant_id)

        await self._db.commit()
        result = await self._db.execute(
            select(IdentityUser)
            .options(selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role))
            .where(IdentityUser.id == user.id)
        )
        return result.scalar_one()

    async def create_ws_ticket(self, user_id: uuid.UUID, tenant_id: Optional[uuid.UUID]) -> str:
        """Short-lived one-time ticket for WebSocket authentication."""
        ticket = generate_secure_token(32)
        self._db.add(IdentityUserToken(
            user_id=user_id,
            login_provider="ffinn",
            name=f"ws_ticket:{ticket}",
            value=str(tenant_id) if tenant_id else "",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
        ))
        await self._db.commit()
        return ticket

    async def redeem_ws_ticket(self, ticket: str, expected_tenant_id: Optional[str] = None) -> Optional[uuid.UUID]:
        row = (await self._db.execute(
            select(IdentityUserToken).where(
                IdentityUserToken.login_provider == "ffinn",
                IdentityUserToken.name == f"ws_ticket:{ticket}",
            )
        )).scalar_one_or_none()
        if not row or not row.expires_at or _ensure_utc(row.expires_at) < _utc_now():
            return None
        if expected_tenant_id and row.value and row.value != expected_tenant_id:
            return None
        user_id = row.user_id
        await self._db.delete(row)
        await self._db.commit()
        return user_id

    async def _build_auth_response(self, user: IdentityUser) -> dict:
        role_names = [ur.role.name for ur in user.roles if ur.role]

        # Get explicit permission grants for user
        perms_result = await self._db.execute(
            select(PermissionGrant).where(
                PermissionGrant.user_id == user.id,
                PermissionGrant.is_granted == True,  # noqa: E712
            )
        )
        user_permissions = [pg.permission_name for pg in perms_result.scalars()]

        # Get role permissions
        from app.core.permissions import Roles as RolesConfig
        role_permissions: list[str] = []
        for role_name in role_names:
            role_permissions.extend(RolesConfig.DEFAULT_ROLE_PERMISSIONS.get(role_name, []))

        all_permissions = list(set(role_permissions + user_permissions))

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "username": user.user_name,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "roles": role_names,
            "permissions": all_permissions,
            "sec": user.security_stamp or "",
        }
        access_token = create_access_token(token_data)
        refresh_token = await self.issue_refresh_token(user.id, user.tenant_id)

        hs = self._hs
        jwt_minutes = hs.jwt_access_minutes if hs else settings.jwt_access_token_expire_minutes
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": jwt_minutes * 60,
            "user_id": str(user.id),
            "username": user.user_name,
            "email": user.email,
            "name": user.name,
            "surname": user.surname,
            "roles": role_names,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        }

    async def create_sso_exchange_code(self, user_id: uuid.UUID) -> str:
        """One-time code for SSO login exchange (avoids tokens in redirect URLs)."""
        code = generate_secure_token(32)
        self._db.add(IdentityUserToken(
            user_id=user_id,
            login_provider="ffinn",
            name=f"sso_exchange:{code}",
            value="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        ))
        await self._db.commit()
        return code

    async def exchange_sso_code(self, code: str) -> dict:
        """Redeem a one-time SSO exchange code for auth tokens."""
        result = await self._db.execute(
            select(IdentityUserToken).where(
                IdentityUserToken.login_provider == "ffinn",
                IdentityUserToken.name == f"sso_exchange:{code}",
            )
        )
        row = result.scalar_one_or_none()
        if not row or not row.expires_at or _ensure_utc(row.expires_at) < _utc_now():
            raise UnauthorizedException("Invalid or expired SSO exchange code.")
        await self._db.delete(row)
        user_result = await self._db.execute(
            select(IdentityUser)
            .options(selectinload(IdentityUser.roles).selectinload(IdentityUserRole.role))
            .where(IdentityUser.id == row.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active:
            raise UnauthorizedException("User not found or inactive.")
        await self._db.commit()
        return await self._build_auth_response(user)

    async def revoke_impersonation_jti(self, actor_user_id: uuid.UUID, jti: str) -> None:
        self._db.add(IdentityUserToken(
            user_id=actor_user_id,
            login_provider="ffinn",
            name=f"impersonation_revoked:{jti}",
            value="revoked",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        ))
        try:
            await self._db.commit()
        except IntegrityError:
            await self._db.rollback()

    async def is_impersonation_jti_revoked(self, jti: str) -> bool:
        if not jti:
            return False
        row = (await self._db.execute(
            select(IdentityUserToken).where(
                IdentityUserToken.login_provider == "ffinn",
                IdentityUserToken.name == f"impersonation_revoked:{jti}",
            )
        )).scalar_one_or_none()
        return row is not None

    async def _assign_role(
        self, user: IdentityUser, tenant_id: Optional[uuid.UUID], role_name: str
    ) -> None:
        result = await self._db.execute(
            select(IdentityRole).where(
                IdentityRole.tenant_id == tenant_id,
                IdentityRole.normalized_name == role_name.upper(),
            )
        )
        role = result.scalar_one_or_none()
        if role is None and tenant_id is not None:
            result = await self._db.execute(
                select(IdentityRole).where(
                    IdentityRole.tenant_id.is_(None),
                    IdentityRole.normalized_name == role_name.upper(),
                )
            )
            role = result.scalar_one_or_none()
        if role:
            self._db.add(IdentityUserRole(user_id=user.id, role_id=role.id))

    async def _assign_default_role(self, user: IdentityUser, tenant_id: Optional[uuid.UUID]) -> None:
        if tenant_id is None and self._hs is not None and self._hs.signups_get_cloud_setup:
            await self._assign_role(user, tenant_id, Roles.DEPLOYER)
            return
        await self._assign_role(user, tenant_id, Roles.USER)

    async def _send_confirmation_email(self, user: IdentityUser, base_url: str) -> None:
        token_value = generate_email_confirmation_token()
        confirmation = EmailConfirmationToken(
            user_id=user.id,
            token=hash_token(token_value),  # store hash; send plaintext in email link
            email=user.email,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        self._db.add(confirmation)
        email_svc = self._email
        if email_svc is None and self._hs is not None:
            email_svc = self._hs.build_email_service()
        if email_svc is None:
            return  # No email service configured; token stored but email not sent
        await email_svc.send_email_confirmation(
            user.email, user.full_name, token_value, base_url=base_url or None
        )
