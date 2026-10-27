"""Tests that ENVIRONMENT=production refuses the placeholder secrets published in this repo."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import KNOWN_PLACEHOLDER_SECRETS, Settings

STRONG_JWT = "q3Jx9mT2vLwP8sYk4RnB7cZa1HfE6uGd0VoMiNtQrXy"
STRONG_FERNET = "x7Kp2Vb9Qw4Ls8Nd3Rf6Tg1Yh5Jm0Zc2Ae9Ui4Ok7Pl="

# Every env var these tests set through Settings(...), so values from the
# developer's shell or CI cannot leak in and change the outcome.
_ENV_VARS = (
    "ENVIRONMENT",
    "JWT_SECRET_KEY",
    "ENCRYPTION_KEY",
    "CALLBACK_TOKEN",
    "DEFAULT_ADMIN_PASSWORD",
    "STAGING_DEMO_PASSWORD",
    "SEED_STAGING_DEMO",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _production(**overrides) -> Settings:
    values = {
        "environment": "production",
        "jwt_secret_key": STRONG_JWT,
        "encryption_key": STRONG_FERNET,
        "staging_demo_password": "a-unique-staging-password-9!",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_environment_is_declared_before_validated_secrets():
    # The secret validators read `environment` from info.data, which only holds
    # fields declared (and validated) earlier in the class.
    fields = list(Settings.model_fields)
    env_index = fields.index("environment")
    for name in (
        "jwt_secret_key",
        "encryption_key",
        "default_admin_password",
        "seed_staging_demo",
        "staging_demo_password",
        "callback_token",
    ):
        assert fields.index(name) > env_index, name
    assert fields.index("seed_staging_demo") < fields.index("staging_demo_password")


def test_production_accepts_strong_values():
    s = _production(callback_token="a-real-random-callback-token", default_admin_password="Unique-Admin-Pass-42")
    assert s.is_production


@pytest.mark.parametrize(
    "value",
    [
        "local-dev-secret-key-change-in-production-32chars",  # docker-compose.yml
        "test-ci-key-that-is-at-least-32-characters",          # CI workflow
        "test-ci-key-for-the-deploy-gate-only-123456",         # CI workflow
        "CHANGE-THIS-TO-YOUR-SECRET-KEY-AT-LEAST-32-CHARACTERS",  # .env.example / default
    ],
)
def test_production_rejects_known_jwt_secret(value):
    with pytest.raises(ValidationError, match="jwt_secret_key is a placeholder"):
        _production(jwt_secret_key=value)


def test_production_rejects_short_jwt_secret():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        _production(jwt_secret_key="short-but-not-a-placeholder")


@pytest.mark.parametrize(
    "value",
    [
        "dGVzdC1lbmNyeXB0aW9uLWtleS0zMmJ5dGJ5dGU=",         # docker-compose.yml
        "dGVzdC1lbmNyeXB0aW9uLWtleS0zMmJ5dA==",             # CI workflows
        "CHANGE-THIS-TO-A-FERNET-KEY-GENERATE-WITH-PYTHON",  # .env.example
    ],
)
def test_production_rejects_known_encryption_key(value):
    with pytest.raises(ValidationError, match="encryption_key is a placeholder"):
        _production(encryption_key=value)


def test_production_rejects_empty_encryption_key():
    with pytest.raises(ValidationError, match="encryption_key must be set"):
        _production(encryption_key="")


def test_production_rejects_placeholder_callback_token():
    with pytest.raises(ValidationError, match="callback_token is a placeholder"):
        _production(callback_token="CHANGE-THIS-TO-A-RANDOM-SECRET")


def test_production_allows_empty_callback_token():
    # Empty means "use the token stored in the database settings".
    assert _production(callback_token="").callback_token == ""


def test_production_rejects_default_admin_password():
    with pytest.raises(ValidationError, match="default_admin_password is a placeholder"):
        _production(default_admin_password="ChangeMe123!")


def test_production_rejects_default_staging_demo_password_when_seeding():
    with pytest.raises(ValidationError, match="staging_demo_password is a placeholder"):
        _production(seed_staging_demo=True, staging_demo_password="StagingDemo123!")


def test_production_ignores_staging_demo_password_when_not_seeding():
    # The field has a public default; production deployments that never seed
    # the demo tenant must still start.
    s = Settings(_env_file=None, environment="production", jwt_secret_key=STRONG_JWT, encryption_key=STRONG_FERNET)
    assert s.staging_demo_password == "StagingDemo123!"


def test_environment_match_is_case_insensitive():
    with pytest.raises(ValidationError, match="jwt_secret_key is a placeholder"):
        _production(environment=" Production ", jwt_secret_key="local-dev-secret-key-change-in-production-32chars")


@pytest.mark.parametrize("environment", ["development", "test", "staging"])
def test_non_production_accepts_dev_values(environment):
    s = Settings(
        _env_file=None,
        environment=environment,
        jwt_secret_key="local-dev-secret-key-change-in-production-32chars",
        encryption_key="dGVzdC1lbmNyeXB0aW9uLWtleS0zMmJ5dGJ5dGU=",
        callback_token="CHANGE-THIS-TO-A-RANDOM-SECRET",
        default_admin_password="ChangeMe123!",
        seed_staging_demo=True,
    )
    assert s.default_admin_password == "ChangeMe123!"


def test_known_values_include_docker_compose_and_env_example():
    # Guard against the list drifting from the files people copy values from.
    root = Path(__file__).resolve().parents[2]
    sources = [root / "docker-compose.yml", root / "python-backend" / ".env.example"]
    pattern = re.compile(
        r"^\s*(JWT_SECRET_KEY|ENCRYPTION_KEY|CALLBACK_TOKEN|DEFAULT_ADMIN_PASSWORD|STAGING_DEMO_PASSWORD)"
        r"\s*[:=]\s*(\S+)",
        re.MULTILINE,
    )
    found = [m for src in sources if src.exists() for m in pattern.finditer(src.read_text(encoding="utf-8"))]
    if not found:
        pytest.skip("docker-compose.yml / .env.example not available")
    for m in found:
        value = m.group(2)
        assert value.startswith("CHANGE-THIS") or value in KNOWN_PLACEHOLDER_SECRETS, m.group(0)
