"""
Identity-related services: two-factor auth, permissions, user delegations.
"""
from __future__ import annotations

import base64
import io
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

import pyotp
import qrcode
import structlog
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, BusinessException, UnauthorizedException
from app.core.security import hash_token, encrypt_value, decrypt_value
from app.domain.models.identity import (
    IdentityUser,
    TwoFactorAuth,
    PermissionGrant,
    UserDelegation,
)

log = structlog.get_logger(__name__)


# ── Two-Factor Auth Service ───────────────────────────────────────────────────

class TwoFactorService:
    def __init__(self, db: AsyncSession):
        self._db = db

    @staticmethod
    def _encrypt_secret(secret: str) -> str:
        return encrypt_value(secret)

    @staticmethod
    def _decrypt_secret(stored: str) -> str:
        if not stored:
            return stored
        try:
            return decrypt_value(stored)
        except ValueError:
            return stored  # legacy plaintext secret

    async def _sync_user_flag(self, user_id: uuid.UUID, enabled: bool) -> None:
        user = (await self._db.execute(
            select(IdentityUser).where(IdentityUser.id == user_id)
        )).scalar_one_or_none()
        if user:
            user.two_factor_enabled = enabled

    async def _get_record(self, user_id: uuid.UUID) -> Optional[TwoFactorAuth]:
        return (await self._db.execute(
            select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id)
        )).scalar_one_or_none()

    async def get_status(self, user_id: uuid.UUID) -> dict:
        record = await self._get_record(user_id)
        return {
            "is_enabled": record.is_enabled if record else False,
            "has_backup_codes": bool(record and record.backup_codes),
        }

    async def setup(self, user_id: uuid.UUID) -> dict:
        """Generate a TOTP secret and QR code URI (does NOT enable 2FA yet)."""
        user = (await self._db.execute(
            select(IdentityUser).where(IdentityUser.id == user_id)
        )).scalar_one_or_none()
        if not user:
            raise NotFoundException("User", str(user_id))

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        issuer = "ffinn"
        label = user.email or str(user_id)
        uri = totp.provisioning_uri(name=label, issuer_name=issuer)

        # Generate QR code as base64 PNG
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode()

        # Store the pending secret (not enabled yet)
        enc_secret = self._encrypt_secret(secret)
        record = await self._get_record(user_id)
        if record:
            record.secret_key = enc_secret
            record.is_enabled = False
        else:
            record = TwoFactorAuth(
                id=uuid.uuid4(),
                user_id=user_id,
                secret_key=enc_secret,
                is_enabled=False,
            )
            self._db.add(record)

        await self._db.commit()
        return {"secret": secret, "qr_uri": uri, "qr_image_base64": qr_b64}

    async def verify_and_enable(self, user_id: uuid.UUID, code: str) -> list[str] | None:
        """Verify a TOTP code and enable 2FA if valid. Returns plaintext backup codes on success, None on failure."""
        record = await self._get_record(user_id)
        if not record:
            raise BusinessException("2FA setup has not been initiated. Call /setup first.")

        totp = pyotp.TOTP(self._decrypt_secret(record.secret_key))
        if not totp.verify(code, valid_window=1):
            return None

        backup_codes = [secrets.token_hex(5).upper() for _ in range(8)]
        record.backup_codes = json.dumps([hash_token(c) for c in backup_codes])
        record.is_enabled = True
        record.enabled_at = datetime.now(timezone.utc)
        await self._sync_user_flag(user_id, True)
        await self._db.commit()
        return backup_codes  # plaintext — route returns them once, never again stored in clear

    async def disable(self, user_id: uuid.UUID, password: str) -> bool:
        """Disable 2FA after verifying the user's password."""
        from app.core.security import verify_password
        user = (await self._db.execute(
            select(IdentityUser).where(IdentityUser.id == user_id)
        )).scalar_one_or_none()
        if not user:
            raise NotFoundException("User", str(user_id))
        if not verify_password(password, user.password_hash or ""):
            raise UnauthorizedException("Invalid password.")

        record = await self._get_record(user_id)
        if not record or not record.is_enabled:
            raise BusinessException("Two-factor authentication is not currently enabled.")

        record.is_enabled = False
        record.backup_codes = None
        await self._sync_user_flag(user_id, False)
        await self._db.commit()
        return True

    async def disable_with_code(self, user_id: uuid.UUID, code: str) -> bool:
        """Disable 2FA after verifying a TOTP code (preferred over password)."""
        record = await self._get_record(user_id)
        if not record or not record.is_enabled:
            raise BusinessException("Two-factor authentication is not currently enabled.")

        totp = pyotp.TOTP(self._decrypt_secret(record.secret_key))
        if not totp.verify(code, valid_window=1):
            return False

        record.is_enabled = False
        record.backup_codes = None
        await self._sync_user_flag(user_id, False)
        await self._db.commit()
        return True

    async def regenerate_backup_codes(self, user_id: uuid.UUID, *, totp_code: str | None = None) -> list[str]:
        """Regenerate backup codes for a user with 2FA enabled. Requires TOTP re-auth."""
        record = await self._get_record(user_id)
        if not record or not record.is_enabled:
            raise BusinessException("Two-factor authentication is not enabled.")
        if totp_code:
            totp = pyotp.TOTP(self._decrypt_secret(record.secret_key))
            if not totp.verify(totp_code, valid_window=1):
                raise UnauthorizedException("Invalid verification code.")

        backup_codes = [secrets.token_hex(5).upper() for _ in range(8)]
        record.backup_codes = json.dumps([hash_token(c) for c in backup_codes])
        await self._db.commit()
        return backup_codes

    async def verify_login_code(self, user_id: uuid.UUID, code: str, is_recovery: bool = False) -> bool:
        """Verify a 2FA code during login (TOTP or backup code)."""
        record = await self._get_record(user_id)
        if not record or not record.is_enabled:
            return False

        if is_recovery:
            if not record.backup_codes:
                return False
            hashed_codes: list[str] = json.loads(record.backup_codes)
            code_hash = hash_token(code.strip().upper())
            if code_hash not in hashed_codes:
                return False
            # Consume the backup code
            hashed_codes.remove(code_hash)
            record.backup_codes = json.dumps(hashed_codes)
            await self._db.commit()
            return True

        totp = pyotp.TOTP(self._decrypt_secret(record.secret_key))
        return totp.verify(code, valid_window=1)


# ── Permissions Service ───────────────────────────────────────────────────────

class PermissionsService:
    """Manage fine-grained permission grants for roles and users."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_grants_for_role(self, role_id: uuid.UUID) -> list[PermissionGrant]:
        return list((await self._db.execute(
            select(PermissionGrant).where(PermissionGrant.role_id == role_id)
        )).scalars().all())

    async def get_grants_for_user(self, user_id: uuid.UUID, tenant_id: Optional[uuid.UUID] = None):
        stmt = select(PermissionGrant).where(PermissionGrant.user_id == user_id)
        if tenant_id is not None:
            stmt = stmt.where(PermissionGrant.tenant_id == tenant_id)
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_all_permission_names(self) -> list[str]:
        """Return distinct permission names currently in use."""
        rows = (await self._db.execute(
            select(PermissionGrant.permission_name).distinct()
        )).scalars().all()
        return sorted(rows)

    async def update_role_grants(
        self,
        role_id: uuid.UUID,
        permissions: list[str],
        tenant_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Replace all permission grants for a role."""
        await self._db.execute(
            delete(PermissionGrant).where(PermissionGrant.role_id == role_id)
        )
        for perm in permissions:
            self._db.add(PermissionGrant(
                id=uuid.uuid4(),
                role_id=role_id,
                tenant_id=tenant_id,
                permission_name=perm,
                is_granted=True,
            ))
        await self._db.commit()

    async def update_user_grants(
        self,
        user_id: uuid.UUID,
        permissions: list[dict],  # [{name, is_granted}]
        tenant_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Replace all explicit user permission grants."""
        await self._db.execute(
            delete(PermissionGrant).where(
                PermissionGrant.user_id == user_id,
                PermissionGrant.tenant_id == tenant_id,
            )
        )
        for p in permissions:
            self._db.add(PermissionGrant(
                id=uuid.uuid4(),
                user_id=user_id,
                tenant_id=tenant_id,
                permission_name=p["name"],
                is_granted=p.get("is_granted", True),
            ))
        await self._db.commit()


# ── Delegation Service ────────────────────────────────────────────────────────

class DelegationService:
    """Manage user-to-user delegations (temporary impersonation grants)."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_my_delegations(self, user_id: uuid.UUID) -> list[UserDelegation]:
        """Delegations created BY this user."""
        return list((await self._db.execute(
            select(UserDelegation).where(UserDelegation.source_user_id == user_id)
        )).scalars().all())

    async def get_delegations_to_me(self, user_id: uuid.UUID) -> list[UserDelegation]:
        """Delegations assigned TO this user."""
        return list((await self._db.execute(
            select(UserDelegation).where(UserDelegation.target_user_id == user_id)
        )).scalars().all())

    async def get_all(self, tenant_id: Optional[uuid.UUID] = None) -> list[UserDelegation]:
        stmt = select(UserDelegation)
        if tenant_id:
            stmt = stmt.where(UserDelegation.tenant_id == tenant_id)
        return list((await self._db.execute(stmt)).scalars().all())

    async def get(self, delegation_id: uuid.UUID) -> UserDelegation:
        d = (await self._db.execute(
            select(UserDelegation).where(UserDelegation.id == delegation_id)
        )).scalar_one_or_none()
        if not d:
            raise NotFoundException("UserDelegation", str(delegation_id))
        return d

    async def create(
        self,
        source_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        tenant_id: Optional[uuid.UUID] = None,
    ) -> UserDelegation:
        if end_time <= start_time:
            raise BusinessException("end_time must be after start_time.")
        target = (await self._db.execute(
            select(IdentityUser).where(IdentityUser.id == target_user_id)
        )).scalar_one_or_none()
        if not target:
            raise NotFoundException("User", str(target_user_id))
        if tenant_id is not None and target.tenant_id != tenant_id:
            raise BusinessException("Target user does not belong to this tenant.")
        d = UserDelegation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            source_user_id=source_user_id,
            target_user_id=target_user_id,
            start_time=start_time,
            end_time=end_time,
        )
        self._db.add(d)
        await self._db.commit()
        await self._db.refresh(d)
        return d

    async def update(
        self,
        delegation_id: uuid.UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> UserDelegation:
        d = await self.get(delegation_id)
        if start_time:
            d.start_time = start_time
        if end_time:
            d.end_time = end_time
        await self._db.commit()
        await self._db.refresh(d)
        return d

    async def delete(self, delegation_id: uuid.UUID) -> None:
        d = await self.get(delegation_id)
        await self._db.delete(d)
        await self._db.commit()
