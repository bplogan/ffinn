"""
Host-level settings loaded from the app_settings table at request time.

Usage:
    hs = await HostSettings.load(db)
    svc = AuthService(db, host_settings=hs)

Falls back to env-var config.Settings for every key not yet persisted in the DB.
"""
from __future__ import annotations

import time
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as cfg

log = structlog.get_logger(__name__)

# Module-level TTL cache — avoids a DB round-trip per auth request for rarely-changing rows.
# Call HostSettings.invalidate_cache() after admin saves app_settings.
_HS_CACHE: tuple[dict[str, str], float] | None = None
_HS_TTL: float = 30.0  # seconds


class HostSettings:
    """In-request snapshot of global (tenant_id IS NULL) app_settings rows."""

    def __init__(self, rows: dict[str, str]) -> None:
        self._rows = rows

    # ── Construction ─────────────────────────────────────────────────────────

    @classmethod
    async def load(cls, db: AsyncSession) -> "HostSettings":
        """Async factory — returns a 30-second cached snapshot, or fetches from DB."""
        global _HS_CACHE
        now = time.monotonic()
        if _HS_CACHE is not None and (now - _HS_CACHE[1]) < _HS_TTL:
            return cls(_HS_CACHE[0])

        from sqlalchemy import select
        from app.domain.models.misc import AppSetting

        result = await db.execute(
            select(AppSetting).where(AppSetting.tenant_id.is_(None))
        )
        rows: dict[str, str] = {r.key: (r.value or "") for r in result.scalars()}
        _HS_CACHE = (rows, now)
        return cls(rows)

    @classmethod
    def invalidate_cache(cls) -> None:
        """Invalidate the TTL cache immediately (call after admin saves settings)."""
        global _HS_CACHE
        _HS_CACHE = None

    # ── Low-level helpers ─────────────────────────────────────────────────────

    def _str(self, key: str, default: str = "") -> str:
        v = self._rows.get(key)
        return v if v is not None else default

    def _bool(self, key: str, default: bool = False) -> bool:
        v = self._rows.get(key)
        if v is None:
            return default
        return v.strip().lower() in ("true", "1", "yes")

    def _int(self, key: str, default: int = 0) -> int:
        v = self._rows.get(key)
        if v is None:
            return default
        try:
            return int(v)
        except (ValueError, TypeError):
            return default

    # ── General ───────────────────────────────────────────────────────────────

    @property
    def app_name(self) -> str:
        return self._str("general.app_name", cfg.app_name)

    @property
    def app_url(self) -> str:
        return self._str("general.app_url", cfg.app_url)

    @property
    def support_email(self) -> str:
        return self._str("general.support_email", cfg.smtp_from_address)

    # ── Registration ──────────────────────────────────────────────────────────

    @property
    def allow_registration(self) -> bool:
        return self._bool("registration.allow_user_registration", cfg.allow_registration)

    @property
    def allow_tenant_registration(self) -> bool:
        return self._bool("registration.allow_tenant_registration", cfg.allow_registration)

    @property
    def new_users_active_by_default(self) -> bool:
        return self._bool("registration.new_users_active_by_default", True)

    @property
    def require_email_confirmation(self) -> bool:
        return self._bool("registration.require_email_confirmation", cfg.require_email_confirmation)

    @property
    def restricted_email_domains_enabled(self) -> bool:
        return self._bool("registration.restricted_email_domains_enabled", False)

    @property
    def allowed_email_domains(self) -> list[str]:
        raw = self._str("registration.allowed_email_domains", "")
        return [d.strip().lower() for d in raw.split(",") if d.strip()]

    @property
    def signups_get_cloud_setup(self) -> bool:
        """When True, people who sign up on the platform itself (no tenant) get the
        Deployer role: Cloud Setup only, instead of the User role."""
        return self._bool("registration.signups_get_cloud_setup", False)

    @property
    def paywall_enabled(self) -> bool:
        """When True, tenants must select an edition during self-registration."""
        return self._bool("registration.paywall_enabled", False)

    # ── Security — password ───────────────────────────────────────────────────

    @property
    def password_min_length(self) -> int:
        return self._int("security.password_min_length", cfg.password_min_length)

    @property
    def password_require_digit(self) -> bool:
        return self._bool("security.password_require_digit", cfg.password_require_digit)

    @property
    def password_require_lowercase(self) -> bool:
        return self._bool("security.password_require_lowercase", True)

    @property
    def password_require_uppercase(self) -> bool:
        return self._bool("security.password_require_uppercase", cfg.password_require_uppercase)

    @property
    def password_require_special(self) -> bool:
        return self._bool("security.password_require_special", cfg.password_require_special)

    # ── Security — lockout ────────────────────────────────────────────────────

    @property
    def lockout_enabled(self) -> bool:
        return self._bool("security.lockout_enabled", True)

    @property
    def lockout_max_attempts(self) -> int:
        return self._int("security.lockout_max_attempts", 5)

    @property
    def lockout_duration_seconds(self) -> int:
        return self._int("security.lockout_duration_seconds", 300)

    # ── Security — 2FA / JWT ──────────────────────────────────────────────────

    @property
    def two_factor_enabled(self) -> bool:
        return self._bool("security.two_factor_enabled", False)

    @property
    def jwt_access_minutes(self) -> int:
        return self._int("security.jwt_access_minutes", cfg.jwt_access_token_expire_minutes)

    @property
    def jwt_refresh_days(self) -> int:
        return self._int("security.jwt_refresh_days", cfg.jwt_refresh_token_expire_days)

    # ── SMTP / email ──────────────────────────────────────────────────────────

    def build_email_service(self):
        """Return an EmailService configured from DB SMTP settings (env-var fallback)."""
        from app.core.app_url import resolve_frontend_url
        from app.infrastructure.email import EmailService
        return EmailService.from_config(
            host=self._str("smtp.host", cfg.smtp_host),
            port=self._int("smtp.port", cfg.smtp_port),
            use_ssl=self._bool("smtp.use_ssl", cfg.smtp_use_tls),
            username=self._str("smtp.username", cfg.smtp_username),
            password=self._str("smtp.password", cfg.smtp_password),
            from_address=self._str("smtp.from_address", cfg.smtp_from_address),
            from_name=self._str("smtp.from_name", cfg.smtp_from_name),
            app_url=resolve_frontend_url(host_settings=self),
            app_name=self.app_name,
        )
