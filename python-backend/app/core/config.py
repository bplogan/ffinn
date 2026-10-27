"""
Application configuration via Pydantic Settings.
Reads from environment variables and .env file.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder and dev/CI secrets that are published in this repository
# (docker-compose.yml, .env.example, .github/workflows/). Anyone can read them,
# so they are refused when ENVIRONMENT=production. Values starting with
# "CHANGE-THIS" are refused too.
KNOWN_PLACEHOLDER_SECRETS: frozenset[str] = frozenset({
    # JWT_SECRET_KEY
    "local-dev-secret-key-change-in-production-32chars",
    "test-ci-key",
    "test-ci-key-that-is-at-least-32-characters",
    "test-ci-key-for-the-deploy-gate-only-123456",
    "test-secret-key-for-ci-only",
    "test-secret-key-for-testing-only-32chars",
    # ENCRYPTION_KEY
    "dGVzdC1lbmNyeXB0aW9uLWtleS0zMmJ5dGJ5dGU=",
    "dGVzdC1lbmNyeXB0aW9uLWtleS0zMmJ5dA==",
    "test-encryption-key-for-tests-only32c",
    # DEFAULT_ADMIN_PASSWORD / STAGING_DEMO_PASSWORD
    "ChangeMe123!",
    "StagingDemo123!",
})


def _is_production(info) -> bool:
    # `environment` is declared before every field that calls this, so pydantic
    # has already validated it and put it in info.data.
    return str((info.data or {}).get("environment", "development")).strip().lower() == "production"


def _reject_placeholder(field: str, v: str, hint: str) -> None:
    if v.startswith("CHANGE-THIS") or v in KNOWN_PLACEHOLDER_SECRETS:
        raise ValueError(
            f"{field} is a placeholder value published in the ffinn repository and "
            f"must not be used with ENVIRONMENT=production. {hint}"
        )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # env vars matched case-insensitively
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "ffinn"
    app_version: str = "1.0.0"
    app_url: str = "http://localhost:3000"       # front-end / base URL for email links
    api_base_url: str = "http://localhost:8000"  # public API URL for CI callbacks
    # Stored as str so pydantic-settings does NOT try to JSON-parse it.
    # Accepts comma-separated URLs or a JSON array string.
    # The actual list is exposed via the `cors_origins` property below.
    cors_origins_raw: str = "http://localhost:3000,https://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        """Parse cors_origins_raw into a list, handling comma-separated or bracketed formats."""
        v = self.cors_origins_raw.strip()
        if v.startswith("["):
            import json as _json
            try:
                parsed = _json.loads(v)
                if isinstance(parsed, list):
                    return [o.strip() for o in parsed if o.strip()]
            except Exception:
                pass
            # Bracketed but not valid JSON — strip brackets then comma-split
            v = v.strip("[]")
        return [o.strip() for o in v.split(",") if o.strip()]
    environment: str = "development"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:localpass@localhost:5433/ffinn"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_echo: bool = False

    # ── JWT ──────────────────────────────────────────────────────────────────
    jwt_secret_key: str = "CHANGE-THIS-TO-YOUR-SECRET-KEY-AT-LEAST-32-CHARACTERS"
    jwt_algorithm: str = "HS256"

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:  # type: ignore[override]
        if _is_production(info):
            _reject_placeholder(
                "jwt_secret_key", v,
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"",
            )
            if len(v) < 32:
                raise ValueError("jwt_secret_key must be at least 32 characters.")
        return v
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # ── Encryption (Fernet/AES-256 for API keys, tokens) ─────────────────────
    encryption_key: str = ""

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str, info) -> str:  # type: ignore[override]
        if _is_production(info):
            hint = (
                "Generate with: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
            if not v or len(v) < 32:
                raise ValueError(f"encryption_key must be set and >= 32 chars in production. {hint}")
            _reject_placeholder("encryption_key", v, hint)
        return v

    # ── Identity ─────────────────────────────────────────────────────────────
    require_email_confirmation: bool = True
    allow_registration: bool = True
    default_admin_email: str = ""
    default_admin_password: str = ""

    @field_validator("default_admin_password")
    @classmethod
    def validate_default_admin_password(cls, v: str, info) -> str:  # type: ignore[override]
        if _is_production(info):
            _reject_placeholder("default_admin_password", v, "Choose a strong, unique password.")
        return v

    # ── Staging demo tenant (QA accounts + sample data) ───────────────────────
    seed_staging_demo: bool = False
    staging_demo_tenant_name: str = "staging"
    staging_demo_password: str = "StagingDemo123!"

    @field_validator("staging_demo_password")
    @classmethod
    def validate_staging_demo_password(cls, v: str, info) -> str:  # type: ignore[override]
        # Only matters when the demo accounts are seeded; in production that
        # happens only if SEED_STAGING_DEMO=true (see staging_demo_seeder).
        if _is_production(info) and (info.data or {}).get("seed_staging_demo"):
            _reject_placeholder("staging_demo_password", v, "Set STAGING_DEMO_PASSWORD to a strong, unique password.")
        return v

    # ── Multi-tenancy ────────────────────────────────────────────────────────
    multi_tenancy_enabled: bool = True

    # ── Email / SMTP ─────────────────────────────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "noreply@ffinn.dev"
    smtp_from_name: str = "ffinn"

    # ── OAuth ────────────────────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = "common"

    # ── Stripe ───────────────────────────────────────────────────────────────
    stripe_enabled: bool = True
    stripe_publishable_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # ── PayPal ───────────────────────────────────────────────────────────────
    paypal_enabled: bool = False
    paypal_mode: str = "sandbox"
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""

    # ── Subscription ─────────────────────────────────────────────────────────
    subscription_expiration_warning_days: int = 7
    subscription_notification_days: str = "7,3,1"
    subscription_auto_deactivate_expired: bool = True
    subscription_enable_email_notifications: bool = True

    # ── File Storage ─────────────────────────────────────────────────────────
    file_storage_backend: str = "local"           # "local" | "azure" | "s3"
    local_storage_path: str = "./uploads"
    # Chat attachments are private: served only through an authenticated endpoint.
    agent_attachments_path: str = "./agent_uploads"
    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = "logos"
    azure_storage_account_name: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket_name: str = ""

    # ── AI Agent ─────────────────────────────────────────────────────────────
    ai_agent_rate_limit_per_minute: int = 10
    ai_agent_max_concurrent: int = 3
    ai_agent_max_prompt_length: int = 10000
    ai_agent_max_retries: int = 3
    ai_agent_timeout_minutes: int = 15
    callback_token: str = ""                       # X-Callback-Token for CI/CD
    ai_agent_timeout_seconds: int = 900

    @field_validator("callback_token")
    @classmethod
    def validate_callback_token(cls, v: str, info) -> str:  # type: ignore[override]
        if _is_production(info):
            _reject_placeholder(
                "callback_token", v,
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"",
            )
        return v

    # ── Source Control Defaults ───────────────────────────────────────────────
    default_source_control_provider: str = "github"
    default_branch_prefix: str = "ai-feature/"

    # ── Monitoring ───────────────────────────────────────────────────────────
    sentry_dsn: str = ""
    log_level: str = "INFO"

    # ── Rate Limiting ────────────────────────────────────────────────────────
    rate_limit_default_per_minute: int = 120
    rate_limit_auth_per_minute: int = 10      # stricter for login/register
    rate_limit_storage_uri: str = ""          # empty → in-memory; set redis://... in prod

    # ── Request Security ─────────────────────────────────────────────────────
    max_request_body_mb: int = 10             # 413 above this size
    force_https: bool = False                 # set True in production to add HSTS
    # Optional regex for additional CORS origins (e.g. specific Azure SWA hostname).
    # Leave empty by default so the explicit cors_origins list is the source of truth.
    cors_origin_regex: str = ""
    # Whether the backend sits behind a trusted reverse proxy (e.g. Azure Front Door).
    # When False, X-Forwarded-For is ignored for rate-limit keying to prevent spoofing.
    trust_forwarded_headers: bool = False

    # ── Password Policy ──────────────────────────────────────────────────────
    password_min_length: int = 8
    password_require_digit: bool = True
    password_require_uppercase: bool = True
    password_require_special: bool = True

    # ── Token Security ───────────────────────────────────────────────────────
    jwt_issuer: str = "ffinn-api"              # iss claim
    jwt_audience: str = "ffinn-client"         # aud claim

    @property
    def subscription_notification_days_list(self) -> list[int]:
        return [int(d.strip()) for d in self.subscription_notification_days.split(",") if d.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in ("development", "dev", "local", "test")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
