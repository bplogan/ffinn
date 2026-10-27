"""
Security utilities: JWT tokens, password hashing, AES-256 encryption.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
import jwt
from jwt import PyJWTError as JWTError
from passlib.context import CryptContext
from app.core.config import settings

# ── Password hashing ──────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────
def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({
        "exp": expire,
        "type": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": str(uuid.uuid4()),
    })
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict[str, Any]) -> tuple[str, datetime]:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    })
    token = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expire


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """
    Decode and validate JWT.
    - Rejects the 'none' algorithm.
    - Validates issuer, audience, and token-type claim.
    Raises JWTError on failure.
    """
    # Prevent algorithm confusion attacks by only allowing configured algorithm
    allowed = [settings.jwt_algorithm]
    if settings.jwt_algorithm not in ("RS256", "ES256"):  # symmetric key algos
        # Explicitly block public-key algorithms when using symmetric key
        options = {
            "verify_signature": True,
            "verify_aud": bool(settings.jwt_audience),
        }
    else:
        options = {"verify_signature": True}

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=allowed,
        options=options,
        audience=settings.jwt_audience or None,
        issuer=settings.jwt_issuer or None,
    )

    # Check token type (prevents refresh tokens from being used as access tokens)
    token_type = payload.get("type")
    if token_type and token_type != expected_type:
        raise JWTError(f"Wrong token type: expected '{expected_type}', got '{token_type}'")

    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode a refresh token specifically."""
    return decode_token(token, expected_type="refresh")


def hash_token(token: str) -> str:
    """One-way SHA-256 hash of a token for safe at-rest storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── Encryption (Fernet = AES-128-CBC + HMAC-SHA256) ──────────────────────────
def _get_fernet(key: Optional[str] = None) -> Fernet:
    """Return Fernet instance from the given key or configured ENCRYPTION_KEY.

    The key can be:
    - A base64url Fernet key (43 chars), used as-is
    - Any other string, which is SHA-256 hashed then base64-encoded into a valid key
    """
    k = key or settings.encryption_key
    if not k:
        raise RuntimeError(
            "encryption_key must be set. "
            "Generate with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    # Try to use as-is (proper Fernet key)
    try:
        decoded = base64.urlsafe_b64decode(k + "==")
        if len(decoded) == 32:
            return Fernet(k.encode() if isinstance(k, str) else k)
    except Exception:
        pass

    # Derive a 32-byte key from the passphrase via SHA-256
    derived = hashlib.sha256(k.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def encrypt_value(plaintext: str, key: Optional[str] = None) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext."""
    if not plaintext:
        return plaintext
    f = _get_fernet(key)
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str, key: Optional[str] = None) -> str:
    """Decrypt a string value. Raises ValueError if decryption fails."""
    if not ciphertext:
        return ciphertext
    f = _get_fernet(key)
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise ValueError("Failed to decrypt value — check encryption_key") from e


# ── Secure token generation ───────────────────────────────────────────────────
def generate_secure_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def generate_email_confirmation_token() -> str:
    return secrets.token_urlsafe(48)


# ── HMAC signature for webhooks (Stripe, etc.) ────────────────────────────────
def compute_hmac_sha256(key: str, data: str) -> str:
    import hmac
    sig = hmac.new(key.encode(), data.encode(), hashlib.sha256)
    return sig.hexdigest()


# ── Password policy ───────────────────────────────────────────────────────────

def validate_password_strength(
    password: str,
    *,
    min_length: Optional[int] = None,
    require_digit: Optional[bool] = None,
    require_lowercase: Optional[bool] = None,
    require_uppercase: Optional[bool] = None,
    require_special: Optional[bool] = None,
) -> list[str]:
    """
    Validate password against the configured policy.
    Optional keyword arguments override the env-var defaults so callers can pass
    DB-sourced policy values (e.g. from HostSettings).
    Returns a list of violation messages (empty = password is acceptable).
    """
    from app.core.config import settings  # late import to avoid circular dependency issues

    eff_min = min_length if min_length is not None else settings.password_min_length
    eff_digit = require_digit if require_digit is not None else settings.password_require_digit
    eff_lower = require_lowercase if require_lowercase is not None else True
    eff_upper = require_uppercase if require_uppercase is not None else settings.password_require_uppercase
    eff_special = require_special if require_special is not None else settings.password_require_special

    errors: list[str] = []
    if len(password) < eff_min:
        errors.append(f"Password must be at least {eff_min} characters.")
    if eff_digit and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit.")
    if eff_lower and not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter.")
    if eff_upper and not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter.")
    if eff_special:
        specials = set(r'!@#$%^&*()_+-=[]{}|;:,.<>?')
        if not any(c in specials for c in password):
            errors.append("Password must contain at least one special character.")
    # Reject obvious weak passwords / common patterns
    lower = password.lower()
    for weak in ("password", "123456", "qwerty", "letmein", "welcome", "admin"):
        if weak in lower:
            errors.append("Password is too common or easily guessed.")
            break
    return errors
